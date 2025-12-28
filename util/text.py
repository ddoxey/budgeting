import os
import json
import re
from dataclasses import dataclass
from wcwidth import wcswidth

_ansi_re = re.compile(r'\x1b\[[0-9;]*m')

def strip_ansi(s: str) -> str:
    return _ansi_re.sub('', s)

def disp_width(s: str) -> int:
    # measure terminal column width; strip ANSI first
    s2 = strip_ansi(s)
    w = wcswidth(s2)
    return w if w >= 0 else len(s2)

class Lang:
    Debug = os.environ.get('DEBUG', False)
    DebugLog = None
    Language, Encoding = os.environ.get('LANG', 'en_US.UTF-8').split('.', 1)
    ConfigFilename = os.path.join(os.environ['HOME'], 'budget-lang.json')
    TextFor = None

    @classmethod
    def _log(cls, text):
        if cls.Debug and cls.DebugLog is None:
            log_filename = cls.ConfigFilename.replace('.json', '.log')
            cls.DebugLog = open(log_filename, 'w', encoding='utf8')
        if cls.DebugLog is not None:
            cls.DebugLog.write(f'{text}\n')

    @classmethod
    def _load(cls):
        if cls.TextFor is not None:
            return
        try:
            with open(cls.ConfigFilename, 'r', encoding=cls.Encoding) as conf:
                cls.TextFor = json.load(conf) or {}
            if len(cls.TextFor) > 0:
                cls._log(f'Loaded dictionary: {cls.ConfigFilename}')
        except FileNotFoundError:
            cls._log(f'No such file: {cls.ConfigFilename}')
            cls.TextFor = {}
        except json.JSONDecodeError:
            cls._log(f'JSON Error: {cls.ConfigFilename}')
            cls.TextFor = {}

    @classmethod
    def text(cls, src_text: str) -> str:
        if not src_text:
            return ""
        if cls.Language == 'en_US':
            return src_text
        cls._load()
        d = cls.TextFor.get(src_text.lower())
        if not isinstance(d, dict):
            cls._log(f'Not found: {src_text}')
            return src_text
        return d.get(cls.Language, src_text)

class Cell:

    def __init__(self, src_text, width = None, align = 'left'):
        self.src_text = src_text
        self.width = width
        self.align = align

    def text(self):
        return Lang.text(self.src_text)

    def __str__(self):
        s = self.text()
        if self.width is None:
            return s
        return self._pad(s, self.width, self.align)

    def dlen(self) -> int:
        return disp_width(self.text())

    def left(self, width):
        self.width = width
        self.align = 'left'
        return str(self)

    def center(self, width):
        self.width = width
        self.align = 'center'
        return str(self)

    def right(self, width):
        self.width = width
        self.align = 'right'
        return str(self)

    @staticmethod
    def _pad(s, width, align):
        s = f' {s} '
        pad = max(0, width - disp_width(s))
        if pad == 0:
            return s
        if align == 'right':
            return (' ' * pad) + s
        if align == 'center':
            left = pad // 2
            return (' ' * left) + s + (' ' * (pad - left))
        # default left
        return s + (' ' * pad)
