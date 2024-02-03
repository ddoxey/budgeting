import os
import re
import sys
import glob
import shutil
import pickle


class Cache:

    def __init__(self, name, profile):
        self.name = name
        self.profile = profile

    def cache_dir(self):
        """Return the current cache directory."""
        return os.path.join(os.environ["HOME"], '.cache', self.name)

    def cache_file(self, file_key, profile=None):
        """Generate the full path to a cache file for the given profile/key.
        """
        if profile is None:
            profile = self.profile
        filename = re.sub(r'\W+', '_', file_key) + '.pkl'
        if not os.path.exists(self.cache_dir()):
            os.makedirs(self.cache_dir(), mode=0o700, exist_ok=True)
        if file_key != 'profiles' \
          and profile is not None and profile != 'Main':
            filename = f'{profile}-{filename}'
        return os.path.join(self.cache_dir(), filename)

    def delete(self, profile):
        """Delete all cache files for the given profile."""
        if not os.path.exists(self.cache_dir()):
            print(f'No such directory: {self.cache_dir()}', file=sys.stderr)
            return
        if profile == 'Main':
            print(f'Cannot delete the {profile} profile', file=sys.stderr)
            return
        for filepath in glob.glob(f'{self.cache_dir()}/{profile}-*.pkl'):
            os.remove(filepath)

    def copy(self, from_profile, to_profile):
        """Copy all cache files from one profile to another."""
        if not os.path.exists(self.cache_dir()):
            print(f'No such directory: {self.cache_dir()}', file=sys.stderr)
            return
        if from_profile == to_profile:
            print(f'Cannot copy {from_profile} onto itself', file=sys.stderr)
            return
        file_regex = re.compile(r'\A( \w+ )-( \w+ )[.]pkl', re.X | re.M | re.S)
        if from_profile == 'Main':
            file_regex = re.compile(r'\A ( \w+ ) [.]pkl', re.X | re.M | re.S)
        for filepath in glob.glob(os.path.join(self.cache_dir(), '*.pkl')):
            filename = os.path.basename(filepath)
            m = file_regex.match(filename)
            if m is None:
                continue
            tokens = m.groups()
            to_filename = f'{to_profile}-{tokens[-1]}.pkl'
            if to_profile == 'Main':
                to_filename = f'{tokens[-1]}.pkl'
            to_filepath = os.path.join(self.cache_dir(), to_filename)
            shutil.copy(filepath, to_filepath)

    def read(self, record_key, default=None):
        """Read data from the cache file.
        """
        filename = self.cache_file(record_key)
        if os.path.exists(filename):
            with open(filename, 'rb') as pkl_file:
                print(f'Reading: {os.path.basename(filename)}',
                      file=sys.stderr)
                data = pickle.load(pkl_file)
                if data is None or len(data) == 0:
                    data = default
                return data
        return default

    def write(self, record_key, data):
        """Write data to the dache file.
        """
        filename = self.cache_file(record_key)
        with open(filename, 'wb') as pkl_file:
            print(f'Updating: {os.path.basename(filename)}',
                  file=sys.stderr)
            pickle.dump(data, pkl_file)
