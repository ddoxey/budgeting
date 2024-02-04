#!/usr/bin/env python3

import math
from operator import itemgetter
from ui import Printer
from util.repetition import Repetition


class Tables:

    def __init__(self, profile, themes):
        self.profile = profile
        self.themes = themes

    def get(self, key):
        if key in self.themes:
            return self.themes[key]
        return {'fg': 105, 'bg': 121, 'style': 'bold'}

    def projection_table(self, opening_balance, budget, chokepoints=False):
        ptr = Printer(10, '*', 10, 10)
        ptr.banner(f'Opening Balance: {opening_balance}')
        ptr.table_header('date', 'category', 'amount', 'balance')
        last_mon = None
        for event in budget:
            if event.get('amount') != 0:
                this_mon = event.get('datetime').strftime('%m')
                if last_mon is None:
                    last_mon = this_mon
                if this_mon != last_mon:
                    ptr.table_boundary(weight='lite')
                last_mon = this_mon
                theme = self.get(event.get('category'))
                ptr.set_theme(**theme)
                ptr.table_row(
                    event.get('date'),
                    event.get('category'),
                    f'{event.get("amount"):0.2f}',
                    f'{event.get("balance"):0.2f}')
        ptr.table_close()

        if chokepoints:
            chokepoints = budget.get_chokepoints()

            ptr = Printer(10, 30)
            ptr.table_header(
                'date',
                'balance',
                title="Eye of the needle: " + str(chokepoints.eye()))

            theme = [
                {'fg': 'black', 'bg': 230},
                {'fg': 'black', 'bg': 'white'},
            ]
            row_i = 0

            for chokepoint in chokepoints:
                ptr.set_theme(**theme[row_i % 2])
                row_i += 1
                ptr.table_row(
                    chokepoint.get('date'),
                    f'{chokepoint.get("balance"):0.2f}'
                )
            ptr.table_close()

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

        ptr = Printer(15 for col_i in range(columns_n))

        ptr.table_header(title=f'{self.profile} Categories')

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
                    row.append(cat)
                themes.append(self.get(cat))
            ptr.set_themes(themes)
            ptr.table_row(*row)
        ptr.table_close()

    def exceptions_table(self, exceptions: list):
        """Display the exceptions table.
        """
        ptr = Printer(10, '*', 10)
        ptr.table_header(title=f'{self.profile} Exceptions')

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
        col_headers = ['Category', 'Repeats', 'Amount',
                       'Match Description', 'Match Amount']
        if abbreviated:
            col_sizes = ['10', 14,  10]
            col_headers = ['Category', 'Repeats', 'Amount']

        ptr = Printer(*col_sizes)
        ptr.table_header(title=f'{self.profile} Transaction Types')
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
        ptr = Printer('*', 10,  10, 10)
        ptr.table_header(title=f'{self.profile} Themes')

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

    def profile_table(self, profiles):
        """Display the profile table.
        """
        ptr = Printer(10, '*')
        ptr.table_header(title=f'{self.profile} Profiles')

        ptr.table_row('Name', 'Description')
        ptr.table_boundary(weight='lite')

        theme = [
            {'fg': 'black', 'bg': 230},
            {'fg': 'black', 'bg': 'white'},
        ]
        row_i = 0

        for profile in profiles:
            ptr.set_theme(**theme[row_i % 2])
            row_i += 1
            ptr.table_row(
                profile.get('name'),
                profile.get('description'))
        ptr.table_close()

    def lasts_table(self, occurrences):
        """Display the last occurrences table.
        """
        ptr = Printer('*', 10)
        ptr.table_header(title=f'{self.profile} Last Occurrences')

        ptr.table_row('Category', 'Date')
        ptr.table_boundary(weight='lite')

        categories = sorted(occurrences.keys())

        for category in categories:
            theme = self.get(category)
            ptr.set_theme(**theme)
            ptr.table_row(
                category,
                occurrences.get(category))
        ptr.table_close()

    def dict_table(self, title, data):
        """Display dict key/val in two columns.
        """
        col1_width = max(len(key) for key in data)
        ptr = Printer(col1_width, '*')
        ptr.table_header(title=f'{self.profile} {title}')

        theme = [
            {'fg': 'black', 'bg': 230},
            {'fg': 'black', 'bg': 'white'},
        ]
        row_i = 0

        for key, val in data.items():
            ptr.set_theme(**theme[row_i % 2])
            row_i += 1
            ptr.table_row(f'{key:>{col1_width}}', val)
        ptr.table_close()
