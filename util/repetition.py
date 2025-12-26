import re
import inflect


class Repetition:

    REGEX = re.compile((
        r'\A'
        r'(Sun|Mon|Tue|Wed|Thu|Fri|Sat|\d{1,2})'
        r'(?:[/](\d+))?'
        r'\Z'), re.X | re.M | re.S)

    @staticmethod
    def parse(text):
        m = Repetition.REGEX.match(text)
        if m is None:
            return None
        return {'when': m.group(1).strip().strip(','),
                'repeater': 1 if m.group(2) is None else int(m.group(2))}

    def __init__(self, text):
        data = self.parse(text)
        if data is None:
            raise ValueError(f'Invalid repetition string: {text}')
        self.when = data['when']
        self.repeater = data['repeater']

    @property
    def values(self):
        if self.when[0].isdigit():
            return [d.zfill(2)
                    for d in self.when.split(',')]
        return [self.when.lower().title()]

    @property
    def field(self):
        if self.when[0].isdigit():
            return '%d'
        return '%a'

    def monthly_factor(self):
        values = self.values
        if len(values) == 1:
            if values[0][0].isdigit():
                # day of month
                return 1 / self.repeater
            else:
                # day of week
                return 4 / self.repeater
        else:
            # multiple days per month (repeater n/a)
            return len(values)

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
