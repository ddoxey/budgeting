#!/usr/bin/env python3
from pprint import pprint

import os
import re
import csv
import sys
import cmd
import math
import glob
import pickle
import inflect
import readline  # MAC
from datetime import datetime
from operator import itemgetter
from ui import Printer
from budget import Budget
from colors import STYLES


if 'libedit' in readline.__doc__:
    readline.parse_and_bind('bind ^I rl_complete')  # MAC
else:
    readline.parse_and_bind('tab: complete')  # Linux

CACHE_DIR = os.path.join(os.environ["HOME"], '.cache', 'budget')
DOWNLOAD_DIR = os.path.join(os.environ["HOME"], 'Downloads')
TRANSACTIONS_PKL = 'transactions.pkl'
EXCEPTIONS_PKL = 'exceptions.pkl'
THEMES_PKL = 'themes.pkl'


class Repetition:

    REGEX = re.compile((
        r'\A'
        r'(Sun|Mon|Tue|Wed|Thu|Fri|Sat|\d{1,2})'
        r'(?:[/](\d+))?'
        r'\Z'), re.X|re.M|re.S)

    @staticmethod
    def parse(text):
        m = Repetition.REGEX.match(text)
        if m is None:
            return None
        return {'when': m.group(1),
                'repeater': 1 if m.group(2) is None else int(m.group(2))}

    def __init__(self, text):
        data = self.parse(text)
        if data is None:
            raise ValueError(f'Invalid repetition string: {text}')
        self.when = data['when']
        self.repeater = data['repeater']

    def __str__(self):
        when = self.when
        repeats = 'every'
        inflector = inflect.engine()
        if self.repeater > 1:
            repeats = f'every {inflector.ordinal(self.repeater)}'
        if when.isdigit():
            when = inflector.ordinal(int(when))
            if repeats == 'every':
                return f'{when} monthly'
        return f'{repeats} {when}'


class Money:

    REGEX = re.compile(r'^([$]?[-]?|[-]?[$]?)[0-9]+([.][0-9]+)?$')

    @staticmethod
    def parse(text):
        if isinstance(text, float):
            return text
        m = Money.REGEX.match(text.strip())
        if m is None:
            return None
        return float(text.replace('$', "").replace(',', ""))

    def __init__(self, amount):
        data = self.parse(amount)
        if data is None:
            raise ValueError(f'{amount} should resemble: $1.00')
        self.amount = data

    def __float__(self):
        return self.amount

    def __str__(self):
        dollars, cents = f'{self.amount:0.2f}'.split('.')
        return f'${int(dollars):,d}.{cents}'


class History:

    @staticmethod
    def find_transactions_csv():
        search_path = os.path.join(DOWNLOAD_DIR, 'transactions*.CSV')
        filenames = [{'path': filename,
                    'mtime': os.stat(filename).st_mtime}
                    for filename in glob.glob(search_path)]
        if len(filenames) == 0:
            raise RuntimeError(f'transactions.CSV not in {DOWNLOAD_DIR}')
        csv_files = sorted(filenames, key=lambda fn: fn['mtime'])
        if 'DEBUG' in os.environ and os.environ['DEBUG']:
            print('chosen CSV:', csv_files[-1]['path'])
        return csv_files[-1]['path']

    @staticmethod
    def read_transaction_history():
        csv_file = History.find_transactions_csv()
        history = []
        with open(csv_file, encoding='UTF-8') as csv_fh:
            csv_doc = csv.reader(csv_fh)
            headers = [header.lower().replace('.', "")
                    for header in next(csv_doc)]
            for row in csv_doc:
                event = {}
                for header_i in range(len(headers)):
                    event[headers[header_i]] = row[header_i]
                history.append(event)
        return history


class Table:

    def __init__(self, themes):
        self.themes = themes

    def get(self, key):
        if key in self.themes:
            return self.themes[key]
        return {'fg': 105, 'bg': 121, 'style': 'bold'}

    def projection_table(self, opening_balance, budget, chokepoints=False):
        p = Printer([10, '*', 10, 10])
        p.banner(f'Opening Balance: {opening_balance}')
        p.table_header('date', 'category', 'amount', 'balance')
        last_mon = None
        for event in budget:
            if event.get('amount') != 0:
                this_mon = event.get('datetime').strftime('%m')
                if last_mon is None:
                    last_mon = this_mon
                if this_mon != last_mon:
                    p.table_boundary(weight='lite')
                last_mon = this_mon
                theme = self.get(event.get('category'))
                p.set_theme(**theme)
                p.table_row(
                    event.get('date'),
                    event.get('category'),
                    f'{event.get("amount"):0.2f}',
                    f'{event.get("balance"):0.2f}'
                )
        p.table_close()

        if chokepoints:
            chokepoints = budget.get_chokepoints()

            p = Printer([10, 30])
            p.table_header(
                'date',
                'balance',
                title="Eye of the needle: " + str(chokepoints.eye()))

            theme = [
                {'fg': 'black', 'bg': 230},
                {'fg': 'black', 'bg': 'white'},
            ]
            n = 0

            for chokepoint in chokepoints:
                p.set_theme(**theme[n % 2])
                n += 1
                p.table_row(
                    chokepoint.get('date'),
                    f'{chokepoint.get("balance"):0.2f}'
                )
            p.table_close()

        days = budget.get_days()
        months_elapsed = int(days / 30)
        days = days - int(months_elapsed * 30)

        if months_elapsed > 0:
            print(f'{months_elapsed} months, {days} days elapsed\n')
        elif days > 0:
            print(f'{days} days\n')

        return 0

    def category_table(self, categories: list):
        """Print the table of categories.
        """
        columns_n = 3
        rows_n = math.ceil(len(categories) / columns_n)

        ptr = Printer([15 for n in range(columns_n)])

        ptr.table_header(title='Categories')

        def get(r_n, c_n):
            idx = r_n + (c_n * rows_n)
            if idx >= len(categories):
                return None, None
            return idx+1, categories[idx]

        for row_n in range(rows_n):
            row = []
            themes = []
            for col_n in range(columns_n):
                idx, cat = get(row_n, col_n)
                if idx is None:
                    row.append("")
                else:
                    row.append(f'{idx:2d}. {cat}')
                themes.append(self.get(cat))
            ptr.set_themes(themes)
            ptr.table_row(*row)
        ptr.table_close()

    def exceptions_table(self, exceptions: list):
        """Display the exceptions table.
        """
        ptr = Printer([10, '*', 10])
        ptr.table_header(title='Exceptions')

        for exception in exceptions:
            theme = self.get(exception.get('category'))
            ptr.set_theme(**theme)
            ptr.table_row(
                exception.get('date'),
                exception.get('category'),
                f'{exception.get("amount"):0.2f}')
        ptr.table_close()

    def transactions_table(self, transactions, abbreviated=False):
        """Display the transaction types table.
        """
        col_sizes = ['10', 14,  10, '*', 12]
        col_headers = ['Category', 'Repeats', 'Amount', 'Match Description', 'Match Amount']

        if abbreviated:
            col_sizes = ['10', 14,  10]
            col_headers = ['Category', 'Repeats', 'Amount']

        ptr = Printer(col_sizes)
        ptr.table_header(title='Transaction Types')
        ptr.table_row(*col_headers)
        ptr.table_boundary(weight='lite')

        records = sorted(transactions, key=itemgetter('amount'))

        for trans in records:
            theme = self.get(trans.get('category'))
            ptr.set_theme(**theme)
            if abbreviated:
                ptr.table_row(
                    trans.get('category'),
                    str(Repetition(trans.get('repetition'))),
                    f'{trans.get("amount"):0.2f}')
            else:
                ptr.table_row(
                    trans.get('category'),
                    str(Repetition(trans.get('repetition'))),
                    f'{trans.get("amount"):0.2f}',
                    trans.get('conditions').get('description'),
                    trans.get('conditions').get('debit'))
        ptr.table_close()

    def theme_table(self, themes):
        """Display the theme table.
        """
        ptr = Printer(['*', 10,  10, 10])
        ptr.table_header(title='Themes')

        ptr.table_row('Category', 'FG', 'BG', 'Style')
        ptr.table_boundary(weight='lite')

        categories = sorted(themes.keys())

        for category in categories:
            theme = themes.get(category)
            ptr.set_theme(**theme)
            ptr.table_row(
                category,
                str(theme.get('fg')),
                str(theme.get('bg')),
                theme.get('style'))
        ptr.table_close()


class Data:

    @staticmethod
    def cache_file(filename):
        if not os.path.exists(CACHE_DIR):
            os.makedirs(CACHE_DIR, mode=0o700, exist_ok=True)
        return os.path.join(CACHE_DIR, filename)

    @staticmethod
    def read_exception(categories):
        """Read the exceptions data from the Pickle datafile.
        """
        exceptions = None
        with open(Data.cache_file(EXCEPTIONS_PKL), 'rb') as pkl_file:
            exceptions = pickle.load(pkl_file)

        if exceptions is None:
            raise RuntimeError(f'Unable to read: {EXCEPTIONS_PKL}')

        def update_epoch(exc: dict):
            """Add an 'epoch' Property.
            """
            date = datetime.strptime(exc['date'], '%m-%d-%Y')
            exc['epoch'] = int(date.strftime('%s'))
            return exc

        threshold = 15
        records = sorted([update_epoch(record) for record in exceptions],
                         key=itemgetter('epoch'))

        return [exc for exc in records
                if exc['epoch'] >= threshold
                and exc.get('category') in categories]

    @staticmethod
    def update_exception(exceptions: list):
        """Save the updated Exceptions list to the db.
        """
        if len(exceptions) > 0:
            with open(Data.cache_file(EXCEPTIONS_PKL), 'wb') as pkl_file:
                pickle.dump(exceptions, pkl_file)
            print(f'Updated: {EXCEPTIONS_PKL}')

    @staticmethod
    def read_transaction_type():
        """Read the transactions data from the Pickle datafile.
        """
        transactions = None
        with open(Data.cache_file(TRANSACTIONS_PKL), 'rb') as pkl_file:
            transactions = pickle.load(pkl_file)
        if transactions is None:
            raise RuntimeError(f'Unable to read: {TRANSACTIONS_PKL}')
        return transactions

    @staticmethod
    def update_transaction_type(transactions: list):
        """Save the updated transactions list to the db.
        """
        if len(transactions) > 0:
            with open(Data.cache_file(TRANSACTIONS_PKL), 'wb') as pkl_file:
                pickle.dump(transactions, pkl_file)
            print(f'Updated: {TRANSACTIONS_PKL}')

    @staticmethod
    def read_theme():
        """Read the themes data from the Pickle datafile.
        """
        themes = None
        with open(Data.cache_file(THEMES_PKL), 'rb') as pkl_file:
            themes = pickle.load(pkl_file)
        if themes is None:
            raise RuntimeError(f'Unable to read: {THEMES_PKL}')
        return themes

    @staticmethod
    def update_theme(themes: list):
        """Save the updated themes list to the db.
        """
        if len(themes) > 0:
            with open(Data.cache_file(THEMES_PKL), 'wb') as pkl_file:
                pickle.dump(themes, pkl_file)
            print(f'Updated: {THEMES_PKL}')

class BudgetShell(cmd.Cmd):
    intro = 'Type help or ? to list commands.'
    prompt = 'Budget: '

    def __init__(self, completekey='tab', stdin=None, stdout=None):
        super().__init__(completekey, stdin, stdout)
        self.themes_changed = False
        self.transaction_types_changed = False
        self.exceptions_changed = False
        self.balance = 0.0
        self.table = Table(Data.read_theme())
        self.transaction_types = Data.read_transaction_type()
        self.categories = sorted([trans['category']
                                 for trans in self.transaction_types])
        self.exceptions = Data.read_exception(self.categories)
        self.history = History.read_transaction_history()

    def get_predicted_dates(self, cat):
        budget = Budget(0,
                        self.transaction_types,
                        self.exceptions,
                        self.history,
                        365)
        events = budget.get_events(category=cat)
        return [event.get('date') for event in events]

    def update_theme(self, arg_str):
        update_theme_regex = re.compile((
            r'\A'
            r'   (\w+) \s+ '
            r'   (\d{1,3}) \s+ '
            r'   (\d{1,3}) \s+ '
            r'   (\w+) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = update_theme_regex.match(arg_str)
        if m is None:
            print(f'Unable parse theme update: {arg_str}')
            return
        cat = m.group(1)
        if cat not in self.categories:
            print(f'Unrecognized category: {cat}', file=sys.stderr)
            return
        fg = m.group(2)
        if not fg.isdigit():
            print(f'Forground value {fg} is not an int')
        bg = m.group(3)
        if not bg.isdigit():
            print(f'Background value {bg} is not an int')
        style = m.group(4)
        if style not in STYLES:
            print(f'Unrecognized style: {style}', file=sys.stderr)
            print(f'Choose from: {", ".join(STYLES)}')
            return
        if cat in self.table.themes:
            print(f'Update theme {cat}: {fg}, {bg}, {style}')
            self.table.themes[cat]['fg'] = int(fg)
            self.table.themes[cat]['bg'] = int(bg)
            self.table.themes[cat]['style'] = style
            self.themes_changed = True
            return
        print(f'Add theme {cat}: {fg}, {bg}, {style}')
        self.table.themes[cat] = {'fg': int(fg),
                                  'bg': int(bg),
                                  'style': style}
        self.themes_changed = True
        return

    def update_exception(self, arg_str):
        update_exception_regex = re.compile((
            r'\A'
            r'   (\w+) \s+ '
            r'   (\d{2}[-]\d{2}[-]\d{4}) \s+ '
            r'   ([-]? [$]? \d+ (?: [.]\d+ )?) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = update_exception_regex.match(arg_str)
        if m is None:
            print(f'Unable parse exception update: {arg_str}')
            return
        cat = m.group(1)
        if cat not in self.categories:
            print(f'Unrecognized category: {cat}', file=sys.stderr)
            return
        date = m.group(2)
        amount = m.group(3)
        for exception in self.exceptions:
            if exception['category'] == cat and exception['date'] == date:
                print(f'Update exception {cat}: {amount} on {date}')
                exception['amount'] = float(Money(amount))
                self.exceptions_changed = True
                return
        print(f'Add exception {cat}: {amount} on {date}')
        self.exceptions.append({'date': date,
                                'category': cat,
                                'amount': float(Money(amount))})
        self.exceptions_changed = True
        return

    def update_transaction(self, arg_str):
        update_transaction_regex = re.compile((
            r'\A'
            r'   (\w+) \s+ '
            r'   (\S+) \s+ '
            r'   ([-]? [$]? \d+ (?: [.]\d+ )?) \s* '
            r"   (?: r'( [^']+ )' \s* )? "
            r"   (?: r'( [^']+ )')? "
            r'\Z'), re.X | re.M | re.S | re.I)
        m = update_transaction_regex.match(arg_str)
        if m is None:
            print(f'Unable parse transaction update: {arg_str}')
            return
        cat = m.group(1)
        if cat not in self.categories:
            if not re.match(r'\A\w+\Z', cat):
                print(f'Bad category name: {cat}', file=sys.stderr)
                return
        repetition = m.group(2)
        if Repetition.parse(repetition) is None:
            print(f'Invalid repetition pattern: {repetition}')
            return
        amount = m.group(3)
        if Money.parse(amount) is None:
            print(f'Invalid monetary value: {amount}')
            return
        description_regex = "" if m.group(4) is None else m.group(4)
        debit_regex = "" if m.group(5) is None else m.group(5)
        for transaction_type in self.transaction_types:
            if transaction_type['category'] == cat:
                print(f'Update transaction {cat}: {amount} on {repetition}')
                transaction_type['repetition'] = repetition
                transaction_type['amount'] = float(Money(amount))
                transaction_type['conditions']['description'] = description_regex
                transaction_type['conditions']['debit'] = debit_regex
                self.transaction_types_changed = True
                return
        print(f'Add new transaction {cat}: {amount} on {repetition}')
        self.transaction_types.append({'category': cat,
                                        'repetition': repetition,
                                        'amount': float(Money(amount)),
                                        'conditions': {
                                            'description': description_regex,
                                            'debit': debit_regex
                                        }})
        self.categories = sorted([trans['category']
                                 for trans in self.transaction_types])
        self.transaction_types_changed = True
        return

    def do_update(self, arg_str):
        if ' ' not in arg_str:
            print(f'Invalid update command: {arg_str}', file=sys.stderr)
            return
        update_type, arg_str = re.split(r'\s+', arg_str.strip(), 1)
        if update_type == 'theme':
            self.update_theme(arg_str)
            return
        if update_type == 'exception':
            self.update_exception(arg_str)
            return
        if update_type == 'transaction':
            self.update_transaction(arg_str)
            return
        print(f'Invalid update type: {update_type}', file=sys.stderr)
        return

    def complete_update(self, text, state, begidx, endidx):
        update_types = ['transaction', 'exception', 'theme']
        tokens = re.split(r'\s+', state.strip())
        if len(tokens) == 1:
            return update_types
        update_type = tokens[1]
        if len(tokens) == 2:
            if update_type not in update_types:
                return [opt for opt in update_types
                        if opt.startswith(update_type)]
            return self.categories
        if len(tokens) == 3:
            cat = tokens[2]
            if cat not in self.categories:
                return [opt for opt in self.categories
                        if opt.startswith(cat)]
            if update_type in ['theme', 'exception']:
                return self.get_predicted_dates(cat)
        if len(tokens) == 4:
            cat, date = tokens[2:4]
            if update_type == 'exception':
                cat_dates = self.get_predicted_dates(cat)
                if date not in cat_dates:
                    return [cat_date for cat_date in cat_dates
                            if cat_date.startswith(date)]
        if len(tokens) == 5:
            if update_type == 'theme':
                return STYLES
        if len(tokens) == 6:
            if update_type == 'theme':
                theme_style = tokens[5]
                if theme_style not in STYLES:
                    return [style for style in STYLES
                            if style.startswith(theme_style)]
        return None

    def do_save(self, arg_str):
        save_types = [save_type
                      for save_type in re.split(r'\s+', arg_str.strip())
                      if len(save_type) > 0]
        if len(save_types) == 0:
            save_types = ['themes', 'transactions', 'exceptions']
        for save_type in save_types:
            if save_type == 'themes':
                if self.themes_changed:
                    Data.update_theme(self.table.themes)
                continue
            if save_type == 'exceptions':
                if self.exceptions_changed:
                    Data.update_exception(self.exceptions)
                continue
            if save_type == 'transactions':
                if self.transaction_types_changed:
                    Data.update_transaction_type(self.transaction_types)
                continue
            print(f'Unrecognized save type: {save_type}', file=sys.stderr)

    def complete_save(self, text, state, begidx, endidx):
        save_types = ['themes', 'transactions', 'exceptions']
        tokens = re.split(r'\s+', state.strip())
        if len(tokens) == 1:
            return save_types
        if len(tokens) == 2:
            save_type = tokens[1]
            if save_type not in save_types:
                return [opt for opt in save_types
                        if opt.startswith(save_type)]
        return None

    def delete_theme(self, arg_str):
        del_theme_regex = re.compile((
            r'\A'
            r'   (\w+|[*]) '
            r'   ( \s+ -f )? '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = del_theme_regex.match(arg_str)
        if m is not None:
            cat = m.group(1)
            force = m.group(2)
            if cat == '*':
                if force is None:
                    print('Cannot del all themes without the force (-f) flag',
                          file=sys.stdout)
                    return
                self.table.themes = {}
                print('Removed all themes')
                self.themes_changed = True
                return
            if cat in self.table.themes:
                del self.table.themes[cat]
                print(f'Removed {cat} theme')
                self.themes_changed = True
            return
        print(f'Invalid theme del command: {arg_str}', file=sys.stderr)

    def delete_exception(self, arg_str):
        del_exception_regex = re.compile((
            r'\A'
            r'   (\w+) \s+ '
            r'   (\d{2}[-]\d{2}[-]\d{4}|[*]) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = del_exception_regex.match(arg_str)
        if m is not None:
            cat = m.group(1)
            if cat not in self.categories:
                print(f'Unrecognized category: {cat}', file=sys.stderr)
                return
            date = m.group(2)
            if date == '*':
                self.exceptions = [exception
                                for exception in self.exceptions
                                if exception['category'] != cat]
                print(f'Removed all {cat} exceptions')
            else:
                self.exceptions = [exception
                                for exception in self.exceptions
                                if not (exception['category'] == cat and exception['date'] == date)]
                print(f'Removed {cat} exception for {date}')
            self.exceptions_changed = True
            return
        print(f'Invalid exception del command: {arg_str}', file=sys.stderr)

    def delete_transaction(self, arg_str):
        del_transaction_regex = re.compile((
            r'\A'
            r'   (\w+) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = del_transaction_regex.match(arg_str)
        if m is not None:
            cat = m.group(1)
            if cat not in self.categories:
                print(f'Unrecognized category: {cat}', file=sys.stderr)
                return
            self.transaction_types = [transaction_type
                                      for transaction_type in self.transaction_types
                                      if transaction_type['category'] != cat]
            self.delete_theme(cat)
            self.delete_exception(f'{cat} *')
            self.categories = sorted([trans['category']
                                     for trans in self.transaction_types])
            print(f'Removed {cat} transaction')
            self.transaction_types_changed = True
            return
        print(f'Invalid transactions del command: {arg_str}', file=sys.stderr)

    def do_del(self, arg_str):
        if ' ' not in arg_str:
            print(f'Invalid del command: {arg_str}', file=sys.stderr)
            return
        del_type, arg_str = re.split(r'\s+', arg_str.strip(), 1)
        if del_type == 'theme':
            self.delete_theme(arg_str)
            return
        if del_type == 'exception':
            self.delete_exception(arg_str)
            return
        if del_type == 'transaction':
            self.delete_transaction(arg_str)
            return
        print(f'Unrecognized del type: {del_type}', file=sys.stderr)

    def complete_del(self, text, state, begidx, endidx):
        del_types = ['transaction', 'theme', 'exception']
        tokens = re.split(r'\s+', state.strip())
        if len(tokens) == 1:
            return del_types
        del_type = tokens[1]
        if len(tokens) == 2:
            if del_type not in del_types:
                return [opt for opt in del_types
                        if opt.startswith(del_type)]
            return self.categories
        cat = tokens[2]
        if len(tokens) == 3:
            if cat not in self.categories:
                return [opt for opt in self.categories
                        if opt.startswith(cat)]
            return self.get_predicted_dates(cat)
        date = tokens[3]
        if len(tokens) == 4:
            cat_dates = self.get_predicted_dates(cat)
            if date not in cat_dates:
                return [cat_date for cat_date in cat_dates
                        if cat_date.startswith(date)]

        return None

    def do_balance(self, line):
        line = line.strip().replace(',', "")
        if len(line) == 0:
            print(f'Balance: {Money(self.balance)}')
        else:
            amount = float(Money(line))
            if amount is None:
                print(f'Invalid amount: {line}', file=sys.stderr)
            else:
                self.balance = amount
                print(f'Balance: {Money(self.balance)}')

    def do_cats(self, line):
        self.table.category_table(self.categories)

    def do_exceptions(self, line):
        self.table.exceptions_table(self.exceptions)

    def do_trans(self, line):
        self.table.transactions_table(self.transaction_types, abbreviated=True)

    def do_transactions(self, line):
        self.table.transactions_table(self.transaction_types)

    def do_themes(self, line):
        self.table.theme_table(self.table.themes)

    def do_run(self, argstr):
        days, chokepoints = None, None
        if ' ' in argstr:
            days, chokepoints = re.split(r'\s+', argstr.strip())
        else:
            days = argstr.strip()
        if not days.isdigit() \
           or chokepoints is not None and chokepoints != '-c':
            print('usage: run <days> [-c]', file=sys.stderr)
        else:
            opening_balance = self.balance
            budget = Budget(
                self.balance,
                self.transaction_types,
                self.exceptions,
                self.history,
                int(days))
            self.table.projection_table(opening_balance, budget, chokepoints)

    def do_status(self, line):
        print(f'Current balance: {Money(self.balance)}')
        print(f'Category count: {len(self.categories)}')
        print(f'Exception count: {len(self.exceptions)}')
        print(f'Historical event count: {len(self.history)}')
        print(f'Downloads dir: {DOWNLOAD_DIR}')
        print(f'Cache dir: {CACHE_DIR}')

    def do_exit(self, line):
        if self.themes_changed:
            Data.update_theme(self.table.themes)
        if self.transaction_types_changed:
            Data.update_transaction_type(self.transaction_types)
        if self.exceptions_changed:
            Data.update_exception(self.exceptions)
        return True

    def do_quit(self, line):
        return True

    def do_q(self, line):
        return True

    def do_clear(self, line):
        print('\n' * 100)
        os.system('clear')


if __name__ == '__main__':
    BudgetShell().cmdloop()
