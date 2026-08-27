# General Ledger ETL Pipeline

A synthetic General Ledger dataset and a Python script that cleans it up and loads it into Oracle.

## What's in here

| File | Purpose |
|---|---|
| `General-Ledger.xlsx` | The source data — GLID, transaction date, account, department, cost center, currency, debit/credit |
| `gl_etl_pipeline.py` | Loads the Excel file, adds a Season column and USD conversions, writes it to Oracle |
| `.env.example` | Copy this to `.env` and fill in your own Oracle credentials |
| `.gitignore` | Keeps your real `.env` out of git |
| `requirements.txt` | Python dependencies |

## How the accounting actually works here

Revenue accounts — Sales Revenue (`4000`) and Online Sales (`4010`) — only ever post to Credit. Expense accounts — COGS (`5000`), Travel Expense (`5010`), Payroll Expense (`6000`) — only ever post to Debit. So net income is `Credit - Debit`, not the other way around. Easy one to get backwards if you're building this from scratch.

## The Python pipeline

Takes the raw Excel export and does three things to it before it touches Oracle:

- Pulls a `Season` out of the transaction month.
- Converts Debit/Credit into USD using a fixed rate table — these are illustrative rates, not pulled from a live feed, so swap them out in `FX_RATES` if you need real ones.
- Rounds the USD amounts up to the nearest 100 into their own columns.

The Oracle load itself builds the table with explicit column types instead of letting pandas guess — pandas' automatic type inference and Oracle don't get along well, so this avoids the usual CLOB/VARCHAR headaches.

Get it running:

```bash
pip install -r requirements.txt
cp .env.example .env
# fill in your real Oracle credentials in .env
python gl_etl_pipeline.py
```

It's written in `#%%` blocks, so if you'd rather step through it cell by cell in VS Code or Jupyter, that works too.

One thing worth repeating even though it's already in `.gitignore`: don't commit your real `.env`. It has your Oracle password sitting in plain text.

## Worth knowing

- The FX rates are static and made up for this project — don't use them for anything real.
- If that Oracle password was ever committed anywhere before this `.gitignore` existed, it's still sitting in your git history. Rotate it.
