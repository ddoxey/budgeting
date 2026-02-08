import re
import os
import csv
import sys
import glob
from datetime import datetime
from functools import lru_cache


class History:

    @staticmethod
    @lru_cache(maxsize=1)
    def download_dir():
        return os.path.join(os.environ["HOME"], 'Downloads')

    @staticmethod
    def find_transactions_csv():
        search_path = os.path.join(History.download_dir(), 'transactions*.*')
        filepaths = [{'path': filepath, 'mtime': os.stat(filepath).st_mtime}
                     for filepath in glob.glob(search_path)
                     if filepath.lower().endswith('.csv')]
        if len(filepaths) == 0:
            if 'DEBUG' in os.environ and os.environ['DEBUG']:
                print('No CSVs found in:', search_path)
            return None
        csv_files = sorted(filepaths, key=lambda fn: fn['mtime'])
        if 'DEBUG' in os.environ and os.environ['DEBUG']:
            print('chosen CSV:', csv_files[-1]['path'])
        return csv_files[-1]['path']

    @staticmethod
    def read_transaction_history():
        csv_file = History.find_transactions_csv()
        if csv_file is None:
            return {'transactions': [],
                    'filename': None,
                    'filepath': None,
                    'last-modified': 0}
        mtime = os.stat(csv_file).st_mtime
        last_modified = datetime.fromtimestamp(mtime).strftime('%m-%d-%Y %H:%M:%S')
        transactions = []
        with open(csv_file, encoding='UTF-8') as csv_fh:
            print(f'Reading: {os.path.basename(csv_file)}', file=sys.stderr)
            csv_doc = csv.reader(csv_fh)
            header_row = next(csv_doc)
            headers = [re.sub(r'\W+', "", header.lower().replace(' ', "_"))
                       for header in header_row]
            for row in csv_doc:
                event = {}
                for header_i in range(len(headers)):
                    event[headers[header_i]] = row[header_i] if header_i < len(row) else ""
                transactions.append(event)
        return {'transactions': transactions,
                'filename': os.path.basename(csv_file),
                'filepath': csv_file,
                'last-modified': last_modified}
