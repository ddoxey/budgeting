#!/usr/bin/env python3

import os
import re
import sys
import cmd
import readline  # MAC
from datetime import datetime, date
from operator import itemgetter
from collections import deque
import colors
from ui.tables import Tables
from budget import Budget
from util.cache import Cache
from util.money import Money
from util.history import History
from util.repetition import Repetition
from util.text import Cell

if 'libedit' in readline.__doc__:
    readline.parse_and_bind('bind ^I rl_complete')  # MAC
else:
    readline.parse_and_bind('tab: complete')  # Linux


class Util:

    @staticmethod
    def date_to_days_away(mm_dd_yyyy):
        if mm_dd_yyyy is None:
            return None
        mm, dd, yyyy = re.split(r'\D+', mm_dd_yyyy, maxsplit=2)
        try:
            target = date(int(yyyy), int(mm), int(dd))
        except ValueError:
            return None
        today = date.today()
        return (target - today).days

    @staticmethod
    def duration_to_days(duration):
        if duration is None:
            return None
        duration_regex = re.compile((
            r'\A'
            r'   (\d+) \s* ([dmy])'
            r'\Z'), re.X | re.M | re.S | re.I)
        m = duration_regex.match(duration)
        if m is None:
            print(f'Unable parse duration: {duration}', file=sys.stderr)
            return None
        multiplier_for = {
            'd': 1,
            'm': 30,
            'y': 365,
        }
        magnitude = int(m.group(1))
        units = m.group(2).strip()
        return magnitude * multiplier_for.get(units)

    @staticmethod
    def current_exceptions(exceptions, categories):

        if exceptions is None:
            exceptions = []

        def update_epoch(exc: dict):
            """Add an 'epoch' Property.
            """
            date = datetime.strptime(exc['date'], '%m-%d-%Y')
            exc['epoch'] = int(date.strftime('%s'))
            return exc

        threshold = 15  # wtf?
        exceptions = sorted([update_epoch(record)
                             for record in exceptions],
                            key=itemgetter('epoch'))

        return [exc for exc in exceptions
                if exc['epoch'] >= threshold
                and exc.get('category') in categories]


class BudgetShell(cmd.Cmd):
    intro = 'Type help or ? to list commands.'
    prompt = 'Budget: '

    def __init__(self, completekey='tab', stdin=None, stdout=None):
        super().__init__(completekey, stdin, stdout)
        self.session = Cache.session('budget')
        if self.session is None or len(self.session) == 0:
            self.session = {'profile': 'Main'}
        self.cache = None
        self.tables = None
        self.profiles = None
        self.transaction_types = None
        self.categories = None
        self.exceptions = None
        self.history = None
        self.lasts = None
        self.changes = {}
        self.do_reload(None)

    def do_export(self, line):
        """Set an environment variable."""
        export_regex = re.compile((
            r'\A'
            r'   (\w+) [=] (\S+) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = export_regex.match(line)
        if m is None:
            print(f'Unable parse export: {line}')
            return
        var_name = m.group(1)
        var_value = m.group(2)
        os.environ[var_name] = var_value

    def do_unset(self, line):
        """Unset an environment variable."""
        unset_regex = re.compile((
            r'\A'
            r'   (\w+) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = unset_regex.match(line)
        if m is None:
            print(f'Unable parse unset: {line}')
            return
        var_name = m.group(1)
        if var_name in os.environ: 
            del os.environ[var_name]

    def do_reload(self, line):
        """Reload cached data and history from the transactions CSV."""
        self.cache = Cache(name='budget',
                           profile=self.session.get('profile'))
        self.tables = Tables(self.session.get('profile'), self.cache.read('themes'))
        self.changes['themes'] = False
        self.profiles = self.cache.read('profiles',
                                        [{'name': 'Main',
                                          'description': 'Default Profile',
                                          'balance': 0}])
        self.changes['profiles'] = False
        self.transaction_types = self.cache.read('transaction_types', [])
        self.changes['transaction_types'] = False
        self.categories = sorted([trans.get('category')
                                  for trans in self.transaction_types])
        self.exceptions = Util.current_exceptions(
                            self.cache.read('exceptions'),
                            self.categories)
        self.changes['exceptions'] = False
        self.history = History.read_transaction_history()
        self.lasts = self.cache.read('lasts')
        if len(self.history['transactions']) == 0:
            if self.lasts is not None:
                self.history['transactions'] = [
                    {'transaction_date': date.replace('-', '/'), 'cat': cat}
                    for cat, date in self.lasts.items()]
        if len(self.history['transactions']) > 0:
            budget = Budget(0,
                            self.transaction_types,
                            self.exceptions,
                            self.history['transactions'],
                            36)
            self.lasts = budget.get_last_occurrences()
            self.cache.write('lasts', self.lasts)
        self.changes['lasts'] = False

    def get_balance(self):
        for profile in self.profiles:
            if profile.get('name') == self.session['profile']:
                return profile.get('balance', 0.0)
        return 0.0

    def set_balance(self, amount):
        for profile_i, profile in enumerate(self.profiles):
            if profile.get('name') == self.session['profile']:
                self.profiles[profile_i]['balance'] = amount
                self.do_save('profiles')
                break

    def get_predicted_dates(self, cat):
        budget = Budget(0,
                        self.transaction_types,
                        self.exceptions,
                        self.history['transactions'],
                        365)
        events = budget.get_events(category=cat)
        return [event.get('date') for event in events]

    def update_profile(self, arg_str):
        update_profile_regex = re.compile((
            r'\A'
            r'   (\w+) \s+ '
            r'   (\w+.*) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = update_profile_regex.match(arg_str)
        if m is None:
            print(f'Unable parse profile update: {arg_str}', file=sys.stderr)
            return
        name = m.group(1)
        desc = m.group(2).strip()
        for profile_i, profile in enumerate(self.profiles):
            if profile.get('name') == name:
                self.profiles[profile_i] = {'name': name,
                                            'description': desc,
                                            'balance': profile.get('balance', 0.0)}
                print(f'updated profile {name}: {desc}', file=sys.stderr)
                self.changes['profiles'] = True
                return
        self.profiles.append({'name': name,
                              'description': desc,
                              'balance': 0.0})
        print(f'Added profile {name}: {desc}')
        self.changes['profiles'] = True
        return

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
            print(f'Unable parse theme update: {arg_str}', file=sys.stderr)
            return
        cat = m.group(1)
        if cat not in self.categories:
            print(f'Unrecognized category: {cat}', file=sys.stderr)
            return
        fg = m.group(2)
        if not fg.isdigit():
            print(f'Foreground value {fg} is not an int', file=sys.stderr)
            return
        if not 0 <= int(fg) <= 255:
            print(f'Foreground value {fg} must on the range of 0 to 255', file=sys.stderr)
            return
        bg = m.group(3)
        if not bg.isdigit():
            print(f'Background value {bg} is not an int', file=sys.stderr)
            return
        if not 0 <= int(bg) <= 255:
            print(f'Background value {bg} must on the range of 0 to 255', file=sys.stderr)
            return
        style = m.group(4)
        if style not in colors.STYLES:
            print(f'Unrecognized style: {style}', file=sys.stderr)
            print(f'Choose from: {", ".join(colors.STYLES)}', file=sys.stderr)
            return
        if cat in self.tables.themes:
            self.tables.themes[cat]['fg'] = int(fg)
            self.tables.themes[cat]['bg'] = int(bg)
            self.tables.themes[cat]['style'] = style
            print(f'Updated theme {cat}: {fg}, {bg}, {style}')
            self.changes['themes'] = True
            return
        self.tables.themes[cat] = {'fg': int(fg),
                                   'bg': int(bg),
                                   'style': style}
        print(f'Added theme {cat}: {fg}, {bg}, {style}')
        self.changes['themes'] = True
        return

    def update_last(self, arg_str):
        update_exception_regex = re.compile((
            r'\A'
            r'   (\w+) \s+ '
            r'   (\d{2}[-]\d{2}[-]\d{4}) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = update_exception_regex.match(arg_str)
        if m is None:
            print(f'Unable parse last occurrence update: {arg_str}', file=sys.stderr)
            return
        cat = m.group(1)
        if cat not in self.categories:
            print(f'Unrecognized category: {cat}', file=sys.stderr)
            return
        date = m.group(2)
        if cat in self.lasts:
            print(f'Update last {cat}: {date}')
        else:
            print(f'Add last {cat}: {date}')
        self.lasts[cat] = date
        self.changes['lasts'] = True
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
            print(f'Unable parse exception update: {arg_str}', file=sys.stderr)
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
                self.changes['exceptions'] = True
                return
        print(f'Add exception {cat}: {amount} on {date}')
        self.exceptions.append({'date': date,
                                'category': cat,
                                'amount': float(Money(amount))})
        self.changes['exceptions'] = True
        return

    def update_transaction(self, arg_str):
        update_transaction_regex = re.compile((
            r'\A'
            r'   (\S+) \s+ '
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
            if not re.match(r'\A[\w&-]+\Z', cat):
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
        for transaction_type in self.transaction_types:
            if transaction_type['category'] == cat:
                transaction_type['repetition'] = repetition
                transaction_type['amount'] = float(Money(amount))
                if m.group(4) is not None:
                    transaction_type['conditions']['description'] = m.group(4)
                if m.group(5) is not None:
                    transaction_type['conditions']['debit'] = m.group(5)
                print(f'Updated transaction {cat}: {amount} on {repetition}')
                self.changes['transaction_types'] = True
                return
        desc_regex = "" if m.group(4) is None else m.group(4)
        debit_regex = "" if m.group(5) is None else m.group(5)
        self.transaction_types.append({'category': cat,
                                       'repetition': repetition,
                                       'amount': float(Money(amount)),
                                       'conditions': {
                                           'description': desc_regex,
                                           'debit': debit_regex
                                       }})
        self.categories = sorted([trans['category']
                                 for trans in self.transaction_types])
        print(f'Added a new transaction {cat}: {amount} on {repetition}')
        self.changes['transaction_types'] = True
        return

    def copy_profile(self, arg_str):
        copy_profile_regex = re.compile((
            r'\A'
            r'   (\w+) \s+ '
            r'   (\w+) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = copy_profile_regex.match(arg_str)
        if m is None:
            print(f'Unable parse profile copy: {arg_str}')
            return
        from_name = m.group(1)
        to_name = m.group(2)
        profiles = [profile for profile in self.profiles
                    if profile.get('name') == from_name]
        if len(profiles) == 0:
            print(f'Unrecognized profile: {from_name}', file=sys.stderr)
            return
        if from_name == to_name:
            print(f'Cannot copy {from_name} to itself', file=sys.stderr)
            return
        self.cache.copy(from_name, to_name)
        self.profiles.append(
            {'name': to_name,
             'description': f'Copy of {profiles[0]["description"]}'})
        self.do_save('profiles')

    def copy_theme(self, arg_str):
        copy_theme_regex = re.compile((
            r'\A'
            r'   (\w+) \s+ '
            r'   (\w+) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = copy_theme_regex.match(arg_str)
        if m is None:
            print(f'Unable parse theme copy: {arg_str}')
            return
        from_cat = m.group(1)
        to_cat = m.group(2)
        if from_cat not in self.tables.themes:
            print(f'Unrecogized theme category: {from_cat}', file=sys.stderr)
            return
        if from_cat == to_cat:
            print(f'Cannot copy {from_cat} theme to itself', file=sys.stderr)
            return
        self.tables.themes[to_cat] = dict(self.tables.themes[from_cat])
        print(f'Copied theme {from_cat} to {to_cat}')
        self.changes['themes'] = True

    def copy_transaction(self, arg_str):
        copy_transaction_type_regex = re.compile((
            r'\A'
            r'   (\w+) \s+ '
            r'   (\w+) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = copy_transaction_type_regex.match(arg_str)
        if m is None:
            print(f'Unable parse transaction copy: {arg_str}')
            return
        from_cat = m.group(1)
        to_cat = m.group(2)
        transactions = [dict(transaction)
                        for transaction in self.transaction_types
                        if transaction['category'] == from_cat]
        if len(transactions) == 0:
            print(f'Unrecogized transaction category: {from_cat}',
                  file=sys.stderr)
            return
        if from_cat == to_cat:
            print(f'Cannot copy {from_cat} transaction_type to itself',
                  file=sys.stderr)
            return
        transactions[0]['category'] = to_cat
        self.transaction_types.append(transactions[0])
        print(f'Copied transaction {from_cat} to {to_cat}')
        self.changes['transaction_types'] = True

    def do_copy(self, arg_str):
        """Create a copy of a profile."""
        if ' ' not in arg_str:
            print(f'Invalid copy command: {arg_str}', file=sys.stderr)
            return
        copy_type, arg_str = re.split(r'\s+', arg_str.strip(), maxsplit=1)
        if copy_type == 'profile':
            self.copy_profile(arg_str)
            return
        if copy_type == 'theme':
            self.copy_theme(arg_str)
            return
        if copy_type == 'transaction':
            self.copy_transaction(arg_str)
            return
        print(f'Unsupported copy type: {copy_type}', file=sys.stderr)

    def do_update(self, arg_str):
        """Update the specified configuration.

Usage: update <profile|theme|exception|transaction|last> <cat> <parameters ...>

Profile updates:
    update profile <name> <description>

<name>        - A single token profile name
<description> - A short description of the profile

The transaction types are grouped by profile which permits the user to
configure multiple budgets and run them seperately.


Theme updates:
    update theme <cat> <fg> <bg> <style>

<cat>         - transaction category
<fg> and <bg> - ANSI color codes on the range of 0 to 255.
<style>       - text style modifier (see tab auto-complete for valid values)

Themes are applied to a transaction event when a table of transactions
is displayed.

Exception updates:
    update exception <cat> <mm-dd-yyyy> <amount>

<cat>        - transaction category
<mm-dd-yyyy> - date when the exception applies
<amount>     - amount applicable to <cat> for this date

Exceptions are cases where the amount on a particular transaction
category deviates from the regularly scheduled amount.

Transaction updates:
    update transaction <cat> <when>[/<repeat>] <amount> <desc> <amount>

<cat>     - transaction category
<when>    - day of month, or day of week (Sun, Mon, ...)
/<repeat> - optional repeater value default is 1
    i.e. Tue/2 - every second Thursday
         15    - every 15th day of the month
         1/2   - every second first day of the month

<amount> - regular amount for this transaction
           (Include unary minus for debit values.)

<desc> - regular expression value that matches on the transaction
         Description

         Note: Must use single quoted Python r-string syntax,
               such as: r'[ ]Mortgage[ ]Payment[ ]'

<amount> - regular expression value that matches on the transaction
           Debit

           Note: Must use single quoted Python r-string syntax,
                 such as: r'[.]42$'

Transactions are scheduled budget events, such as Rent, Payday, etc.

Last occurrence updates:
    update last <cat> <mm-dd-yyyy>

<cat>        - transaction category
<mm-dd-yyyy> - date of last occurrence

The last occurrence records indicate the last date that a transaction
category occurred.
"""
        if ' ' not in arg_str:
            print(f'Invalid update command: {arg_str}', file=sys.stderr)
            return
        update_type, arg_str = re.split(r'\s+', arg_str.strip(), maxsplit=1)
        if update_type == 'profile':
            self.update_profile(arg_str)
            return
        if update_type == 'theme':
            self.update_theme(arg_str)
            return
        if update_type == 'exception':
            self.update_exception(arg_str)
            return
        if update_type == 'transaction':
            self.update_transaction(arg_str)
            return
        if update_type == 'last':
            self.update_last(arg_str)
            return
        print(f'Invalid update type: {update_type}', file=sys.stderr)
        return

    def complete_themes(self, text, state, begidx, endidx):
        themes_types = ['rotate', 'randomize']
        tokens = re.split(r'\s+', state.strip())
        if len(tokens) == 1:
            return themes_types
        themes_type = tokens[1]
        if len(tokens) == 2:
            if themes_type not in themes_types:
                return [opt for opt in themes_types
                        if opt.startswith(themes_type)]
            return self.categories
        if len(tokens) == 3:
            cat = tokens[2]
            if cat not in self.categories:
                return [opt for opt in self.categories
                        if opt.startswith(cat)]
        return None

    def complete_update(self, text, state, begidx, endidx):
        update_types = ['last', 'transaction', 'exception', 'theme', 'profile']
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
                return colors.STYLES
        if len(tokens) == 6:
            if update_type == 'theme':
                theme_style = tokens[5]
                if theme_style not in colors.STYLES:
                    return [style for style in colors.STYLES
                            if style.startswith(theme_style)]
        return None

    def do_save(self, arg_str=""):
        """Save changed data to disk.

Usage: save [<themes|transactions|exceptions>]

All changed data will be saved if the optional save type is omitted."""
        save_types = [save_type
                      for save_type in re.split(r'\s+', arg_str.strip())
                      if len(save_type) > 0]
        if len(save_types) == 0:
            save_types = ['lasts', 'themes', 'transactions', 'exceptions', 'profiles']
        else:
            for save_type in save_types:
                if save_type in self.changes:
                    self.changes[save_type] = True
        for save_type in save_types:
            if save_type == 'lasts':
                if self.changes.get('lasts', False):
                    self.cache.write('lasts', self.lasts)
                    self.changes['lasts'] = False
                continue
            if save_type == 'profiles':
                if self.changes.get('profiles', False):
                    self.cache.write('profiles', self.profiles)
                    self.changes['profiles'] = False
                continue
            if save_type == 'themes':
                if self.changes.get('themes', False):
                    self.cache.write('themes', self.tables.themes)
                    self.changes['themes'] = False
                continue
            if save_type == 'exceptions':
                if self.changes.get('exceptions', False):
                    self.cache.write('exceptions', self.exceptions)
                    self.changes['exceptions'] = False
                continue
            if save_type == 'transactions':
                if self.changes.get('transaction_types', False):
                    self.cache.write('transaction_types',
                                     self.transaction_types)
                    self.changes['transaction_types'] = False
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

    def complete_copy(self, text, state, begidx, endidx):
        copy_types = ['theme', 'transaction', 'profile']
        tokens = re.split(r'\s+', state.strip())
        if len(tokens) == 1:
            return copy_types
        if len(tokens) == 2:
            copy_type = tokens[1]
            if copy_type not in copy_types:
                return [opt for opt in copy_types
                        if opt.startswith(copy_type)]
        return None

    def delete_profile(self, arg_str):
        del_theme_regex = re.compile((
            r'\A'
            r'   (\w+) '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = del_theme_regex.match(arg_str)
        if m is not None:
            name = m.group(1)
            if name == 'Main':
                print(f'Profile "{name}" cannot be deleted', file=sys.stderr)
                return
            profiles = [profile for profile in self.profiles
                        if profile.get('name') != name]
            if len(profiles) < len(self.profiles):
                self.cache.delete(profile=name)
                self.profiles = profiles
                self.do_save('profiles')
                print(f'Removed profile: {name}')
                if name == self.session.get('profile'):
                    self.session['profile'] = 'Main'
                    Cache.session('budget', self.session)
                    self.do_reload(None)
                return
        print(f'Profile not found: {name}', file=sys.stderr)

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
                self.tables.themes = {}
                print('Removed all themes')
                self.changes['themes'] = True
                return
            if cat in self.tables.themes:
                del self.tables.themes[cat]
                print(f'Removed {cat} theme')
                self.changes['themes'] = True
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
                                   if not (exception['category'] == cat
                                           and exception['date'] == date)]
                print(f'Removed {cat} exception for {date}')
            self.changes['exceptions'] = True
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
            self.transaction_types = [
                transaction_type
                for transaction_type in self.transaction_types
                if transaction_type['category'] != cat]
            self.delete_theme(cat)
            self.delete_exception(f'{cat} *')
            self.categories = sorted([trans['category']
                                     for trans in self.transaction_types])
            print(f'Removed {cat} transaction')
            self.changes['transaction_types'] = True
            return
        print(f'Invalid transactions del command: {arg_str}', file=sys.stderr)

    def do_del(self, arg_str):
        """Delete configuration.

Usage: del <theme|exception|transaction> <parameters ...>

Delete a profile:
    del profile <name>

Delete a theme:
    del theme <cat>

Delete all themes:
    del theme * [-f]

Delete an exception:
    del exception <cat> <mm-dd-yyyy>

Delete all exceptions for a transaction category:
    del exception <cat> *

Delete a transaction type:
    del transaction <cat>"""
        if ' ' not in arg_str:
            print(f'Invalid del command: {arg_str}', file=sys.stderr)
            return
        del_type, arg_str = re.split(r'\s+', arg_str.strip(), maxsplit=1)
        if del_type == 'profile':
            self.delete_profile(arg_str)
            return
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
        del_types = ['transaction', 'theme', 'exception', 'profile']
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

    def do_profile(self, line):
        """Set or display the current budget profile.

Usage: profile [<name>]

Sets the current profile if a new value is provided."""
        name = line.strip()
        if len(name) == 0:
            print(f'Profile: {self.session.get("profile")}')
        else:
            for profile in self.profiles:
                if name == profile.get('name'):
                    self.session['profile'] = name
                    Cache.session('budget', self.session)
                    self.do_reload(None)
                    return
            print(f'Invalid profile name: {name}', file=sys.stderr)

    def do_balance(self, line):
        """Set or display the current account balance.

Usage: balance [<amount>]

Sets the account balance if a new value is provided."""
        operator = None
        line = line.strip().replace(',', "")
        if len(line) > 0:
            inc_dec_balance_regex = re.compile((
                r'\A'
                r'  ([+-]=) \s* '
                r'  (\S+) '
                r'\Z'), re.X | re.M | re.S | re.I)
            m = inc_dec_balance_regex.match(line)
            if m is not None:
                operator = m.group(1)
                line = m.group(2)
            if not Money.matches(line):
                print(f'Invalid monetary value: {line}', file=sys.stderr)
                return
            amount = float(Money(line))
            if amount is None:
                print(f'Invalid amount: {line}', file=sys.stderr)
                return
            if operator is not None:
                balance = self.get_balance()
                if operator == '+=':
                    amount = balance + amount
                elif operator == '-=':
                    amount = balance - amount
            self.set_balance(amount)
        balance = self.get_balance()
        print(f'Balance: {Money(balance, "$")}')

    def do_cats(self, line):
        """Show a table of categories."""
        self.tables.category_table(self.categories)

    def do_exceptions(self, line):
        """Show a table of transaction exceptions."""
        self.tables.exceptions_table(self.exceptions)

    def do_trans(self, line):
        """Show an abbreviated table of transaction types."""
        self.tables.transactions_table(self.transaction_types,
                                       abbreviated=True)

    def do_transactions(self, line):
        """Show a table of transaction types."""
        self.tables.transactions_table(self.transaction_types)

    def do_themes(self, arg_str):
        """Show a table of highlighting themes.

Usage: themes [randomize [category]|rotate]

Show a table of the curent themes:
    themes

Randomize the theme for a specific category:
    themes randomize Payday

Randomize the theme for all categories:
    themes randomize

Rotate the theme relative to the categories:
    themes rotate
        """
        if len(arg_str) > 0:
            action, cat = None, None
            theme_action_regex = re.compile((
                r'\A'
                r'   (rotate|randomize) '
                r'   (?: \s+ (\w+) )? '
                r'\Z'), re.X | re.M | re.S | re.I)
            m = theme_action_regex.match(arg_str)
            if m is not None:
                action = m.group(1)
                cat = m.group(2)
                if cat is not None:
                    if cat not in self.categories:
                        print(f'Unrecognized category: {cat}', file=sys.stderr)
                        return
            else:
                print(f'Unrecognized themes action: {arg_str}', file=sys.stderr)
                return
            if action == 'randomize':
                if cat is not None:
                    fg, bg = colors.random_color_pair()
                    self.tables.themes[cat] = {'fg': int(fg),
                                               'bg': int(bg),
                                               'style': 'bold'}
                else:
                    self.tables.themes = {}
                    palette = colors.random_palette(len(self.categories))
                    for index, cat in enumerate(self.categories):
                        index %= len(palette)
                        self.tables.themes[cat] = {'fg': int(palette[index]['fg']),
                                                   'bg': int(palette[index]['bg']),
                                                   'style': 'bold'}
                self.changes['themes'] = True
            elif action == 'rotate':
                cats = self.tables.themes.keys()
                themes = [self.tables.themes[cat] for cat in cats]
                catd = deque(cats)
                catd.rotate(1)
                cats = list(catd)
                for index, cat in enumerate(cats):
                   self.tables.themes[cat] = themes[index]
            else:
                print(f'Invalid themes operation: {arg_str}', file=sys.stderr)
                return
        self.tables.theme_table(self.tables.themes)

    def do_profiles(self, line):
        """Show a table of budget prfiles."""
        self.tables.profile_table(self.profiles)

    def do_run(self, arg_str):
        """Run the budget for the specified number of days.

Usage: run <number><duration-type> [<start-date>]

Where <duration-type> is 'd' for days, 'm' for months, 'y' for years."""
        chokepoints = None
        duration, days_offset = None, 0
        run_regex = re.compile((
            r'\A'
            r'   (\d+[ymd]) '
            r'   (?: \s+ ([0-9]{2}[-][0-9]{2}[-][0-9]{4}) )? '
            r'\Z'), re.X | re.M | re.S | re.I)
        m = run_regex.match(arg_str)
        if m is not None:
            duration = m.group(1)
            start_date = m.group(2)
            if start_date is not None:
                days_offset = Util.date_to_days_away(start_date)
                if days_offset is None or days_offset < 0:
                    print(f'Invalid date: {start_date}', file=sys.stderr)
                    return
        days = Util.duration_to_days(duration)
        if days is None:
            print('Usage: run <number>(d|m|y) [<start-date>]', file=sys.stderr)
        else:
            if days > 60:
                chokepoints = True
            opening_balance = self.get_balance()
            budget = Budget(
                self.get_balance(),
                self.transaction_types,
                self.exceptions,
                self.history['transactions'],
                days,
                days_offset)
            self.tables.projection_table(opening_balance, budget, chokepoints)

    def do_totals(self, arg_str):
        """Report the total amount for each category for the specified duration of time.

Usage: totals <number><duration-type>

Where <duration-type> is 'd' for days, 'm' for months, 'y' for years."""
        duration = arg_str.strip()
        days = Util.duration_to_days(duration)
        if days is None:
            print('Usage: totals <number>(d|m|y)', file=sys.stderr)
        else:
            budget = Budget(
                self.get_balance(),
                self.transaction_types,
                self.exceptions,
                self.history['transactions'],
                days)
            self.tables.totals_table(duration, budget.get_totals())

    def do_status(self, line):
        """Display a summary of status parameters."""
        profiles = [profile for profile in self.profiles
                    if profile.get('name') == self.session.get('profile')]

        status = {
            Cell('Profile').text(): Cell(profiles[0].get('description')).text(),
            Cell('Balance').text(): str(Money(self.get_balance(), "$")),
            Cell('Categories').text(): len(self.categories),
            Cell('Exceptions').text(): len(self.exceptions),
            Cell('Cache Dir').text(): self.cache.cache_dir(),
            Cell('Download Dir').text(): History.download_dir(),
            Cell('History Date').text(): self.history['last-modified'],
            Cell('History Data').text(): self.history['filename'],
            Cell('History Event Count').text(): len(self.history['transactions']),
        }
        self.tables.dict_table('Status', status)

    def do_lasts(self, line):
        """Display a table of last occurrences for each transaction type.

These dates are parsed from the downloaded transaction history or may be
provided in an exception.
        """
        if self.lasts is None:
            self.lasts = self.cache.read('lasts')
        if self.lasts is None:
            budget = Budget(0,
                            self.transaction_types,
                            self.exceptions,
                            self.history['transactions'],
                            36)
            self.lasts = budget.get_last_occurrences()
            self.cache.write('lasts', self.lasts)
            self.changes['lasts'] = True
        self.tables.lasts_table(self.lasts)

    def do_exit(self, line):
        """Save changes and exit."""
        self.do_save()
        Cache.session('budget', self.session)
        return True

    def do_x(self, line):
        """Save changes and exit."""
        return self.do_exit(line)

    def do_quit(self, line):
        """Terminate the program."""
        return True

    def do_q(self, line):
        """Terminate the program."""
        return self.do_quit(line)

    def do_clear(self, line):
        """Clear the screen."""
        print('\n' * 100)
        os.system('clear')


if __name__ == '__main__':
    BudgetShell().cmdloop()
