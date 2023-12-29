import re
import os
import json
from datetime import datetime, timedelta
from os import environ as env
import logging
from pytz import timezone

NFCU_TZ = 'EST'

ONE_DAY = 86400

DayOfWeekRegex = re.compile(
    r'(sun|mon|tue|wed|thu|fri|sat)( / ([0-9]+) )?',
    re.X | re.M | re.S | re.I
)

DayOfMonthRegex = re.compile(
    r'( [0-9,]+ )( / ([0-9]+) )?',
    re.X | re.M | re.S
)


def _is_older(date_a, date_b):

    if not isinstance(date_a, datetime):
        mon, day, year = date_a.split('-')
        date_a = datetime(
            year=int(year),
            month=int(mon),
            day=int(day),
            hour=0,
            minute=0,
            second=0,
            tzinfo=timezone(NFCU_TZ))

    if not isinstance(date_b, datetime):
        mon, day, year = date_b.split('-')
        date_b = datetime(
            year=int(year),
            month=int(mon),
            day=int(day),
            hour=0,
            minute=0,
            second=0,
            tzinfo=timezone(NFCU_TZ))

    return date_a < date_b


def _compute_last(trans_type):

    max_days_ago = 365

    category = trans_type['category']
    repetition = trans_type['repetition']

    field, values, multiplier = _rep_parse(repetition)

    if field == '%d':  # day of the month

        max_days_ago = 1 + multiplier * 31

    elif field == '%a':  # day of the week

        max_days_ago = 1 + multiplier * 7

    else:
        raise ValueError(f'{category} with unsupported repetition field: {field}')

    from_date = datetime.now()

    from_date = from_date.replace(
        hour=0,
        minute=0,
        second=0,
        tzinfo=timezone(NFCU_TZ))

    to_date = datetime.fromtimestamp(
        int(from_date.timestamp()) - (max_days_ago * ONE_DAY))

    timestamps = range(
        int(from_date.timestamp()),
        int(to_date.timestamp()),
        -ONE_DAY)

    dates = [d for d in [
        datetime.fromtimestamp(ts).replace(
            hour=0,
            minute=0,
            second=0,
            tzinfo=from_date.tzinfo)
        for ts in timestamps]
        if d.strftime(field) in values]

    dates = [{'y': dates[i].strftime('%Y'),
              'm': dates[i].strftime('%m'),
              'd': dates[i].strftime('%d')}
             for i in range(len(dates))
             if (i + 1) % multiplier == 0]

    if len(dates) == 0:
        raise RuntimeError(f'failed to compute last occurrence of {category}')

    return datetime(
        year=int(dates[0]['y']),
        month=int(dates[0]['m']),
        day=int(dates[0]['d']),
        hour=0,
        minute=0,
        second=0,
        tzinfo=timezone(NFCU_TZ))


def _find_lasts(history, transaction_types, exceptions, now):

    last_for = {}

    def _matches(transaction, conditions):
        for field in conditions:
            if field in transaction:
                regex = conditions[field]
                value = transaction[field]
                if not re.search(regex, value, re.X | re.M | re.S | re.I):
                    return False
            else:
                return False
        return True

    def _categorize(transaction):
        for trans_type in transaction_types:
            if _matches(transaction, trans_type['conditions']):
                return trans_type['category']
        return None

    for transaction in history:

        if len(last_for) == len(transaction_types):
            break

        category = _categorize(transaction)

        if category is None or category in last_for:
            continue

        mon, day, year = transaction['date'].split('/')

        last_for[category] = datetime(
            year=int(year),
            month=int(mon),
            day=int(day),
            hour=0,
            minute=0,
            second=0,
            tzinfo=timezone(NFCU_TZ))

    if len(last_for) != len(transaction_types):
        for trans_type in transaction_types:
            if trans_type['category'] not in last_for:
                last_for[trans_type['category']] = _compute_last(trans_type)

    for exception in exceptions:
        if _is_older(exception['date'], now):
            if exception['category'] not in last_for \
               or _is_older(
                    last_for[exception['category']],
                    exception['date']):
                mon, day, year = exception['date'].split('-')
                last_for[exception['category']] = datetime(
                    year=int(year),
                    month=int(mon),
                    day=int(day),
                    hour=0,
                    minute=0,
                    second=0,
                    tzinfo=timezone(NFCU_TZ))

    return last_for


def _rep_parse(repetition):

    field = None
    values = None
    multiplier = None

    dow_m = DayOfWeekRegex.match(repetition)

    if dow_m:
        field = '%a'
        values = [dow_m.group(1).lower().title()]
        multiplier = dow_m.group(3)

    else:

        dom_m = DayOfMonthRegex.match(repetition)

        if dom_m:
            field = '%d'
            values = [
                d.zfill(2)
                for d in dom_m.group(1).strip(',').split(',')]
            multiplier = dom_m.group(3)
        else:
            return None, None, None

    if multiplier is None:
        multiplier = 1

    return field, values, int(multiplier)


class Chokepoint:

    def __init__(self, event):
        self.datetime = event.get('datetime')
        self.balance = event.get('balance')

    def __repr__(self):
        return ' : '.join([
            self.datetime.strftime('%m-%d-%Y'),
            f'{self.balance:0.2f}'
        ])

    def __add__(self, other):
        return str(self) + other

    def __radd__(self, other):
        return other + str(self)

    def get(self, field):
        if field == 'balance':
            return float(self.balance)
        if field == 'date':
            return self.datetime.strftime('%m-%d-%Y')
        raise ValueError(f'{field} is not a Chokepoint property')


class ChokepointList:

    def __init__(self, transaction_types, events):

        self.iteration_n = 0

        major_expense = {
            'category': None,
            'amount': 0,
            'count': 0,
        }
        major_income = {
            'category': None,
            'amount': 0,
            'count': 0,
        }

        for trans_type in transaction_types:
            category = trans_type['category']
            amount = trans_type['amount']
            if amount < major_expense['amount']:
                major_expense = {
                    'category': category,
                    'amount': amount,
                    'count': 0,
                }
            elif amount > major_income['amount']:
                major_income = {
                    'category': category,
                    'amount': amount,
                    'count': 0,
                }

        smallest = {
            'balance': 999999,
            'event': None
        }

        self.chokepoints = []

        for event_i, event in enumerate(events):

            if smallest['balance'] > event.get('balance'):
                smallest = {
                    'balance': event.get('balance'),
                    'event': event,
                }

            category = event.get('category')

            if event.get('amount') == major_expense['amount']:

                major_expense['count'] += 1

            elif event.get('amount') == major_income['amount']:

                if major_expense['count'] > 0 and event_i > 0:
                    self.chokepoints.append(Chokepoint(events[event_i-1]))

                major_expense['count'] = 0

        if smallest['event'] is not None:
            self.smallest = Chokepoint(smallest['event'])

    def __len__(self):
        return len(self.chokepoints)

    def __iter__(self):
        self.iteration_n = -1
        return self

    def __next__(self):
        if len(self.chokepoints) == 0 \
           or self.iteration_n == len(self.chokepoints) - 1:
            raise StopIteration
        self.iteration_n += 1
        return self.chokepoints[self.iteration_n]

    def eye(self):
        return self.smallest


class DateList:

    def __init__(self, repetition, now, from_date, day_span):

        days_ago = (now - from_date).days
        days = day_span + days_ago

        field, values, multiplier = _rep_parse(repetition)

        from_date = from_date.replace(
            hour=0,
            minute=0,
            second=0,
            tzinfo=timezone(NFCU_TZ))

        now = now.replace(
            hour=0,
            minute=0,
            second=0,
            tzinfo=timezone(NFCU_TZ))

        to_date = datetime.fromtimestamp(
            int(now.timestamp()) + ((day_span + 1) * ONE_DAY),
        )

        to_date = to_date.replace(
            hour=23,
            minute=59,
            second=59,
            tzinfo=timezone(NFCU_TZ))

        if to_date < from_date:
            to_date = to_date.strftime('%D %T %Z')
            from_date = from_date.strftime('%D %T %Z')
            raise ValueError(f'({to_date}) precedes ({from_date})')

        timestamps = range(
            int(from_date.timestamp()),
            int(to_date.timestamp()),
            ONE_DAY
        )

        now_ts = int(now.timestamp())

        dates = [
            {
                'ts': ts,
                'dt': datetime.fromtimestamp(ts).replace(
                    hour=0,
                    minute=0,
                    second=0,
                    tzinfo=from_date.tzinfo),
            }
            for ts in timestamps
        ]

        occurrence_count = 1
        value = None
        self.dates = []

        for date in dates:
            if date['dt'].strftime(field) in values:
                occurrence_count += 1
                value = date['dt'].strftime(field)
                if date['ts'] < now_ts:
                    continue
                if multiplier == 1 or occurrence_count % multiplier == 0:
                    self.dates.append(date['dt'])

        self.from_date = from_date
        self.to_date = to_date
        self.field = field
        self.value = value
        self.multiplier = multiplier
        self.days = days

    def json(self):
        fmt_str = '%m-%d-%Y %H:%M:%S %Z'
        return json.dumps(
            {
                'dates': [e.strftime(fmt_str) for e in self.dates],
                'days': self.days,
                'field': self.field,
                'multiplier': self.multiplier,
                'range': {
                    'from': self.from_date.strftime(fmt_str),
                    'to': self.to_date.strftime(fmt_str),
                },
                'value': self.value,
            },
            sort_keys=True,
            indent=4
        )

    def __str__(self):
        return self.json()

    def get_dates(self):
        return self.dates


class EventList:

    def __init__(self,
                 category,
                 amount,
                 repetition,
                 exception_for,
                 now,
                 from_date,
                 day_span):

        self.iteration_n = 0

        dates = DateList(repetition, now, from_date, day_span)

        def _decide_amount(event_date, amount, exception_for):
            exception_key = f'{event_date.strftime("%m-%d-%Y")}:{category}'
            if exception_key in exception_for:
                return float(exception_for[exception_key])
            return float(amount)

        self.events = [{
                'category': category,
                'amount': _decide_amount(event_date, amount, exception_for),
                'datetime': event_date,
                'yyyymmdd': event_date.strftime('%Y%m%d'),
                'epoch': int(event_date.timestamp()),
            }
            for event_date in dates.get_dates()]

    def __len__(self):
        return len(self.events)

    def __iter__(self):
        self.iteration_n = -1
        return self

    def __next__(self):
        if len(self.events) == 0 \
           or self.iteration_n == len(self.events) - 1:
            raise StopIteration
        self.iteration_n += 1
        return self.events[self.iteration_n]

    def json(self):
        fmt_str = '%m-%d-%Y %H:%M:%S %Z'
        return json.dumps([
                {**e, 'datetime': e['datetime'].strftime(fmt_str)}
                for e in self.events],
            sort_keys=True,
            indent=4)

    def __str__(self):
        return self.json()

    def get_events(self):
        return self.events


class Event:

    def __init__(self, event, bal):
        if not isinstance(event, dict):
            raise ValueError('Event must be a dict')

        bal['balance'] += float(event['amount'])

        self.event = {
            **event,
            'balance': bal['balance'],
            'epoch': int(event['datetime'].timestamp())}

    def __str__(self):
        return ' '.join([
            self.event['datetime'].strftime('%m-%d-%Y'),
            self.event['category'],
            self.event['amount'],
            self.event['balance']])

    def get(self, field):
        if field in ['amount', 'balance']:
            return float(self.event[field])
        if field == 'date':
            return self.event['datetime'].strftime('%m-%d-%Y')
        return self.event[field]

    def get_key(self):
        return self.event['yyyymmdd']


class Budget:

    def __init__(self, balance, transaction_types, exceptions, history, days):

        self.iteration_n = 0

        exception_for = {
            f'{exc["date"]}:{exc["category"]}': exc['amount']
            for exc in exceptions
        }

        now = datetime.now(tz=timezone(NFCU_TZ))

        self.last_occurrence_of = _find_lasts(
            history,
            transaction_types,
            exceptions,
            now)

        if 'DEBUG' in env and env['DEBUG']:
            print('Last occurred:')
            for cat, event in self.last_occurrence_of.items():
                print(f'{cat.rjust(12)} : {event}')

        event_lists = [
            EventList(
                trans_type['category'],
                trans_type['amount'],
                trans_type['repetition'],
                exception_for,
                now,
                self.last_occurrence_of[trans_type['category']],
                days
            )
            for trans_type in transaction_types
        ]

        events = []

        for e_list in event_lists:
            if len(e_list) > 0:
                events.extend(e_list)

        events = sorted(events, key=lambda e: (e['epoch'], -1 * e['amount']))

        bal = {'balance': balance}

        self.days = days
        self.events = [Event(e, bal) for e in events]
        self.balance = bal['balance']
        self.chokepoints = ChokepointList(transaction_types, self.events)

    def __iter__(self):
        self.iteration_n = -1
        return self

    def __next__(self):
        if len(self.events) == 0 or self.iteration_n == len(self.events) - 1:
            raise StopIteration
        self.iteration_n += 1
        return self.events[self.iteration_n]

    def get_balance(self):
        return self.balance

    def get_days(self):
        return self.days

    def get_chokepoints(self):
        return self.chokepoints

    def get_last_occurrences(self):
        return {
            cat: event.strftime('%m-%d-%Y')
            for cat, event in self.last_occurrence_of.items()
        }

    def get_events(self, date=None, category=None, amount=None):
        field, value = None, None
        if category is not None:
            field, value = 'category', category
        elif date is not None:
            field, value = 'date', date
        elif amount is not None:
            field, value = 'amount', amount
        else:
            return []
        return [event for event in self.events
                if event.get(field) == value]