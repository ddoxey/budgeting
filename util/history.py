import re
import os
import csv
import sys
import glob
from datetime import datetime


class History:

    @staticmethod
    def download_dir():
        return os.path.join(os.environ["HOME"], 'Downloads')

    @staticmethod
    def find_transactions_csv():
        search_path = os.path.join(History.download_dir(), 'transactions*.*')
        filenames = [{'path': filename, 'mtime': os.stat(filename).st_mtime}
                     for filename in glob.glob(search_path)
                     if filename.lower().endswith('.csv')]
        if len(filenames) == 0:
            raise RuntimeError(f'transactions.CSV not in {History.download_dir()}')
        csv_files = sorted(filenames, key=lambda fn: fn['mtime'])
        if 'DEBUG' in os.environ and os.environ['DEBUG']:
            print('chosen CSV:', csv_files[-1]['path'])
        return csv_files[-1]['path']

    @staticmethod
    def read_transaction_history():
        csv_file = History.find_transactions_csv()
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
                    event[headers[header_i]] = row[header_i]
                transactions.append(event)
        return {'transactions': transactions,
                'filename': csv_file,
                'last-modified': last_modified}
