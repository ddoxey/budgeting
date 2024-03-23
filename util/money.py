import re

class Money:

    REGEX = re.compile(r'^([$]?[-]?|[-]?[$]?)[0-9]+[.][0-9]+?$')

    @staticmethod
    def matches(text):
        if text is None or len(text) == 0:
            return False
        m = Money.REGEX.match(text.strip().replace(',', ""))
        if m is None:
            return False
        return True

    @staticmethod
    def parse(text):
        if isinstance(text, float):
            return text
        text = text.strip().replace(',', "")
        m = Money.REGEX.match(text)
        if m is None:
            return None
        return float(text.replace('$', ""))

    def __init__(self, amount, symbol=""):
        data = self.parse(amount)
        if data is None:
            raise ValueError(f'{amount} should resemble: $1.00')
        self.amount = data
        self.symbol = symbol

    def __float__(self):
        return self.amount

    def __str__(self):
        dollars, cents = f'{self.amount:0.2f}'.split('.')
        return f'{self.symbol}{int(dollars):,d}.{cents}'
