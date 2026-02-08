# budgeting
Interactive budgeting CLI that classifies transactions and projects future
balances from your recurring transaction rules and exceptions. You define
transaction types (category, repetition pattern, amount, and matching rules),
then optionally add exceptions to override amounts on specific dates. Exceptions
also act as markers for the last occurrence of a transaction type when recent
history is missing or hard to infer.

This program is optimized for parsing the `transactions.CSV` file downloaded
from the NFCU online banking web application.

# Usage

./shell.py

Within the shell, use the `run` command to generate a projected transaction
history over a duration (and optionally from a future start date):

```bash
run 60d
run 6m
run 1y 03-01-2026
```

`run` prints a projection table (and a dotchart when available) so you can see
expected balances and potential low points.
