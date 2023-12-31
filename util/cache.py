import os
import pickle
from datetime import datetime
from operator import itemgetter


class Cache:

    def __init__(self, name, **filenames):
        self.name = name
        self.filenames = filenames

    def cache_dir(self):
        return os.path.join(os.environ["HOME"], '.cache', self.name)

    def cache_file(self, filename):
        if not os.path.exists(self.cache_dir()):
            os.makedirs(self.cache_dir(), mode=0o700, exist_ok=True)
        return os.path.join(self.cache_dir(), filename)

    def read_exception(self, categories):
        """Read the exceptions data from the Pickle datafile.
        """
        if 'exceptions' not in self.filenames:
            raise RuntimeError('No filename provided for "exceptions"')
        exceptions = None
        with open(self.cache_file(self.filenames['exceptions']), 'rb') as pkl_file:
            exceptions = pickle.load(pkl_file)

        if exceptions is None:
            raise RuntimeError(f'Unable to read: {self.filenames["exceptions"]}')

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

    def update_exception(self, exceptions):
        """Save the updated Exceptions list to the db.
        """
        if 'exceptions' not in self.filenames:
            raise RuntimeError('No filename provided for "exceptions"')
        if len(exceptions) > 0:
            with open(self.cache_file(self.filenames['exceptions']), 'wb') as pkl_file:
                pickle.dump(exceptions, pkl_file)
            print(f'Updated: {self.filenames["exceptions"]}')

    def read_transaction_type(self):
        """Read the transactions data from the Pickle datafile.
        """
        if 'transactions' not in self.filenames:
            raise RuntimeError('No filename provided for "transactions"')
        transactions = None
        with open(self.cache_file(self.filenames['transactions']), 'rb') as pkl_file:
            transactions = pickle.load(pkl_file)
        if transactions is None:
            raise RuntimeError(f'Unable to read: {self.filenames["transactions"]}')
        return transactions

    def update_transaction_type(self, transactions):
        """Save the updated transactions list to the db.
        """
        if 'transactions' not in self.filenames:
            raise RuntimeError('No filename provided for "transactions"')
        if len(transactions) > 0:
            with open(self.cache_file(self.filenames['transactions']), 'wb') as pkl_file:
                pickle.dump(transactions, pkl_file)
            print(f'Updated: {self.filenames["transactions"]}')

    def read_theme(self):
        """Read the themes data from the Pickle datafile.
        """
        if 'themes' not in self.filenames:
            raise RuntimeError('No filename provided for "themes"')
        themes = None
        with open(self.cache_file(self.filenames['themes']), 'rb') as pkl_file:
            themes = pickle.load(pkl_file)
        if themes is None:
            raise RuntimeError(f'Unable to read: {self.filenames["themes"]}')
        return themes

    def update_theme(self, themes):
        """Save the updated themes list to the db.
        """
        if 'themes' not in self.filenames:
            raise RuntimeError('No filename provided for "themes"')
        if len(themes) > 0:
            with open(self.cache_file(self.filenames['themes']), 'wb') as pkl_file:
                pickle.dump(themes, pkl_file)
            print(f'Updated: {self.filenames["themes"]}')
