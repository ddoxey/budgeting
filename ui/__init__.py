import re
import os
import types
from colors import color
from util.money import Money
from util.text import Cell


class Printer:

    def __init__(self, *cell_widths):
        if len(cell_widths) == 0:
            raise RuntimeError(f'{__class__.__name__} Requires column widths')
        self.row_count, self.col_count = None, None
        with os.popen('stty size', 'r') as stty:
            for line in stty:
                self.row_count, self.col_count = [int(n) for n in line.split()]
                break
        if isinstance(cell_widths[0], types.GeneratorType):
            self.cell_widths = self.adjust_widths(list(*cell_widths))
        else:
            self.cell_widths = self.adjust_widths(list(cell_widths))
        self.set_theme()

    def adjust_widths(self, cell_widths):
        cell_pad = 2
        cell_sep = 1

        cell_count = len(cell_widths)
        fixed_sum = sum(w for w in cell_widths if isinstance(w, int))
        wild_idxs = [i for i, w in enumerate(cell_widths) if not isinstance(w, int)]
        wild_count = len(wild_idxs)

        if wild_count == 0:
            return list(cell_widths)

        overhead = cell_sep + cell_count * (cell_pad + cell_sep)
        slack = self.col_count - (overhead + fixed_sum)

        if slack < 0:
            # table can't fit
            wild = 1
            remainder = 0
        else:
            wild, remainder = divmod(slack, wild_count)

        widths = list(cell_widths)
        for j, idx in enumerate(wild_idxs):
            widths[idx] = wild + (1 if j < remainder else 0)
        return widths

    def set_themes(self, themes):
        self.themes = []
        for theme in themes:
            self.themes.append({
                'fg': theme.get('fg', 'black'),
                'bg': theme.get('bg', 'white'),
                'style': theme.get('style', ""),
            })

    def set_theme(self, fg='black', bg='white', style=""):
        self.themes = [{
            'fg': fg,
            'bg': bg,
            'style': style,
        }]

    def _c(self, key):

        coord = {
            'ul': [0, 0],
            'ur': [0, 4],
            'll': [3, 0],
            'lr': [3, 4],
            'tt': [0, 2],
            'rt': [2, 4],
            'bt': [3, 2],
            'lt': [2, 0],
            'hl': [0, 1],
            'vl': [1, 0],
            'cx': [2, 2],
            'ul-l': [4, 0],
            'ur-l': [4, 4],
            'll-l': [7, 0],
            'lr-l': [7, 4],
            'tt-l': [4, 2],
            'rt-l': [6, 4],
            'bt-l': [7, 2],
            'lt-l': [6, 0],
            'hl-l': [4, 1],
            'vl-l': [5, 0],
            'cx-l': [6, 2],
        }
        chars = [
            ['╔', '═', '╦', '═', '╗'],
            ['║',      '║',      '║'],
            ['╠', '═', '╬', '═', '╣'],
            ['╚', '═', '╩', '═', '╝'],
            ['╓', '─', '╤', '─', '╖'],
            ['║',      '│',      '║'],
            ['╟', '─', '╫', '┼', '╢'],
            ['╙', '─', '╧', '─', '╜'],
        ]

        return chars[coord[key][0]][coord[key][1]]

    def _box_horizontal(self, l, h, r):
        print(self._c(l), end="")
        print(self._c(h).ljust(int(self.col_count) - 2, self._c(h)), end="")
        print(self._c(r))

    def _table_bar(self, l, h, t, r):
        print(self._c(l), end="")
        for width_i, width in enumerate(self.cell_widths):
            print(self._c(h).ljust(width + 2, self._c(h)), end="")
            if width_i < len(self.cell_widths) - 1:
                print(self._c(t), end="")
        print(self._c(r))

    def _table_row(self, l, r, *cols):
        print(self._c(l), end="")
        for col_i, col in enumerate(cols):
            theme_n = col_i if len(cols) == len(self.themes) else -1
            col = "" if col is None else str(col)
            alignment = 'right' if Money.matches(col) else 'left'
            print(
                color(
                    str(Cell(col, width=self.cell_widths[col_i] + 2, align=alignment)),
                    fg=self.themes[theme_n]['fg'],
                    bg=self.themes[theme_n]['bg'],
                    style=self.themes[theme_n]['style']),
                end=""
            )
            print(self._c(r), end="")
        print("")

    def _table_title_row(self, title):
        self._table_bar('ul', 'hl', 'hl', 'ur')
        width = -1 + sum((w + 3 for w in self.cell_widths))
        print(self._c('vl'), end="")
        print(color(Cell(title).center(width), fg=1, bg=148, style='bold'), end="")
        print(self._c('vl'))

    def _table_head_row(self, l, r, *cols):
        print(self._c(l), end="")
        for col_i, col in enumerate(cols):
            theme_n = col_i if len(cols) == len(self.themes) else -1
            print(
                color(
                    str(Cell(col, width=self.cell_widths[col_i] + 2, align='center')),
                    fg=self.themes[theme_n]['fg'],
                    bg=self.themes[theme_n]['bg'],
                    style='bold'
                ),
                end=""
            )
            if col_i < len(cols) - 1:
                print(
                    color(
                        self._c(r),
                        fg=self.themes[theme_n]['fg'],
                        bg=self.themes[theme_n]['bg'],
                        style=self.themes[theme_n]['style']
                    ),
                    end=""
                )
            else:
                print(self._c(r), end="")
        print("")

    def table_header(self, *cols, title=None):
        if title is not None:
            self._table_title_row(title)
            self._table_bar('lt', 'hl', 'tt', 'rt')
        else:
            self._table_bar('ul', 'hl', 'tt', 'ur')
        if len(cols) > 0:
            self._table_head_row('vl', 'vl', *cols)
            self._table_bar('lt', 'hl', 'cx', 'rt')

    def table_row(self, *cols):
        self._table_row('vl', 'vl', *cols)

    def table_boundary(self, weight='heavy'):
        if weight == 'heavy':
            self._table_bar('lt', 'hl', 'cx', 'rt')
        elif weight == 'lite':
            self._table_bar('lt-l', 'hl-l', 'cx-l', 'rt-l')
        else:
            raise ValueError(f'weight must be heavy|lite but not {weight}')

    def table_close(self):
        self._table_bar('ll', 'hl', 'bt', 'lr')

    def banner(self, title):
        self._box_horizontal('ul', 'hl', 'ur')
        print(self._c('vl'), end="")
        print(color(Cell(title).left(int(self.col_count) - 2), style='bold'), end="")
        print(self._c('vl'))
        self._box_horizontal('ll', 'hl', 'lr')
