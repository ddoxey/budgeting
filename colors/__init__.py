# Copyright (c) 2012 Giorgos Verigakis <verigak@gmail.com>
#
# Permission to use, copy, modify, and distribute this software for any
# purpose with or without fee is hereby granted, provided that the above
# copyright notice and this permission notice appear in all copies.
#
# THE SOFTWARE IS PROVIDED "AS IS" AND THE AUTHOR DISCLAIMS ALL WARRANTIES
# WITH REGARD TO THIS SOFTWARE INCLUDING ALL IMPLIED WARRANTIES OF
# MERCHANTABILITY AND FITNESS. IN NO EVENT SHALL THE AUTHOR BE LIABLE FOR
# ANY SPECIAL, DIRECT, INDIRECT, OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
# WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
# ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT OF
# OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

import re
import random
from functools import partial
from colors.palettes import Palettes


__version__ = '1.0.3'

COLORS = ('black', 'red', 'green', 'yellow', 'blue', 'magenta', 'cyan',
          'white')
STYLES = ('normal', 'bold', 'faint', 'italic', 'underline', 'blink',
          'blink2', 'negative', 'concealed', 'crossed')


def random_palette(size):
    palette = random.choice(Palettes)
    random.shuffle(palette)
    if len(palette) > size:
        palette = palette[0:size]
    return palette

def random_color_pair():
    all_colors = list(range(0, 256))
    color_a = random.choice(all_colors)
    off_limits = list(range(color_a - 20, color_a + 21))
    some_colors = [c for c in all_colors if c not in off_limits]
    return color_a, random.choice(some_colors)

def color(s, fg=None, bg=None, style=None):
    sgr = []

    if fg:
        if fg in COLORS:
            sgr.append(str(30 + COLORS.index(fg)))
        elif isinstance(fg, int) and 0 <= fg <= 255:
            sgr.append('38;5;%d' % int(fg))
        else:
            raise Exception('Invalid color "%s"' % fg)

    if bg:
        if bg in COLORS:
            sgr.append(str(40 + COLORS.index(bg)))
        elif isinstance(bg, int) and 0 <= bg <= 255:
            sgr.append('48;5;%d' % bg)
        else:
            raise Exception('Invalid color "%s"' % bg)

    if style:
        for st in style.split('+'):
            if st in STYLES:
                sgr.append(str(STYLES.index(st)))
            else:
                raise Exception('Invalid style "%s"' % st)

    if sgr:
        prefix = '\x1b[' + ';'.join(sgr) + 'm'
        suffix = '\x1b[0m'
        return prefix + s + suffix
    else:
        return s


def strip_color(s):
    return re.sub('\x1b[[].+?m', '', s)


# Foreground shortcuts
black = partial(color, fg='black')
red = partial(color, fg='red')
green = partial(color, fg='green')
yellow = partial(color, fg='yellow')
blue = partial(color, fg='blue')
magenta = partial(color, fg='magenta')
cyan = partial(color, fg='cyan')
white = partial(color, fg='white')

# Style shortcuts
bold = partial(color, style='bold')
faint = partial(color, style='faint')
italic = partial(color, style='italic')
underline = partial(color, style='underline')
blink = partial(color, style='blink')
blink2 = partial(color, style='blink2')
negative = partial(color, style='negative')
concealed = partial(color, style='concealed')
crossed = partial(color, style='crossed')
