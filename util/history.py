import os
import csv
import glob


class History:

    @staticmethod
    def download_dir():
        return os.path.join(os.environ["HOME"], 'Downloads')

    @staticmethod
    def find_transactions_csv():
        search_path = os.path.join(History.download_dir(), 'transactions*.CSV')
        filenames = [{'path': filename, 'mtime': os.stat(filename).st_mtime}
                     for filename in glob.glob(search_path)]
        if len(filenames) == 0:
            raise RuntimeError(f'transactions.CSV not in {History.download_dir()}')
        csv_files = sorted(filenames, key=lambda fn: fn['mtime'])
        if 'DEBUG' in os.environ and os.environ['DEBUG']:
            print('chosen CSV:', csv_files[-1]['path'])
        return csv_files[-1]['path']

    @staticmethod
    def read_transaction_history():
        csv_file = History.find_transactions_csv()
        history = []
        with open(csv_file, encoding='UTF-8') as csv_fh:
            csv_doc = csv.reader(csv_fh)
            headers = [header.lower().replace('.', "")
                       for header in next(csv_doc)]
            for row in csv_doc:
                event = {}
                for header_i in range(len(headers)):
                    event[headers[header_i]] = row[header_i]
                history.append(event)
        return history
