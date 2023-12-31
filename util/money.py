import re

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
