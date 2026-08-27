General Ledger ETL Pipeline
----------------------------
Reads the General Ledger Excel export, enriches it with Seasons and USD-converted
amounts, then loads the result into an Oracle database table.

SETUP REQUIRED BEFORE RUNNING:
1. pip install pandas sqlalchemy oracledb python-dotenv openpyxl
2. Create a .env file in this same folder (see .env.example below) with your real
   credentials. NEVER commit the .env file itself — only .env.example belongs in git.
3. Update GL_SOURCE_PATH below to point at your local Excel file.

import os
import numpy as np
import pandas as pd
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

load_dotenv()  # reads variables from a local .env file, keeps secrets out of the script


Configuration

GL_SOURCE_PATH = r"C:\Users\fonac\OneDrive\Desktop\General-Ledger.xlsx"

ORACLE_USER = os.environ["ORACLE_USER"]
ORACLE_PASSWORD = os.environ["ORACLE_PASSWORD"]
ORACLE_HOST = os.environ.get("ORACLE_HOST")
ORACLE_PORT = int(os.environ.get("ORACLE_PORT"))
ORACLE_SERVICE = os.environ.get("ORACLE_SERVICE")

TABLE_NAME = "GENERAL_LEDGER"
SCHEMA_NAME = ORACLE_USER  # loading into your own schema by default

FX_RATES = {
    'USD': 1.0000,
    'EUR': 1.1678,
    'GBP': 1.3648,
    'AUD': 0.7175,
    'CAD': 0.7252,
}

SEASON_MAP = {
    12: 'Winter', 1: 'Winter', 2: 'Winter',
    3: 'Spring', 4: 'Spring', 5: 'Spring',
    6: 'Summer', 7: 'Summer', 8: 'Summer',
    9: 'Fall', 10: 'Fall', 11: 'Fall',
}


Load and inspect
assert os.path.exists(GL_SOURCE_PATH), f"File not found: {GL_SOURCE_PATH}"

df = pd.read_excel(GL_SOURCE_PATH)

print(df.head())
print(df.info())
print(df.describe(include='all'))
print(df.isnull().sum())

Enrich: Season, FX rates, USD conversion, rounding

df['Season'] = df['TxnDate'].dt.month.map(SEASON_MAP)

df['FXRate'] = df['Currency'].map(FX_RATES)
assert df['FXRate'].notna().all(), "Unmapped currency codes found"

df['Debit_USD'] = df['Debit'] * df['FXRate']
df['Credit_USD'] = df['Credit'] * df['FXRate']

df['Debit_USD_rounded'] = np.ceil(df['Debit_USD'] / 100) * 100
df['Credit_USD_rounded'] = np.ceil(df['Credit_USD'] / 100) * 100

print(df.groupby('AccountName')[['Debit_USD', 'Credit_USD']].sum())

Drop the un-rounded USD columns now that the rounded versions exist.
df = df.drop(columns=['Debit_USD', 'Credit_USD'])

print(df.head(20))


# Connect to Oracle
# ---------------------------------------------------------------------------
connection_url = URL.create(
    drivername="oracle+oracledb",
    username=ORACLE_USER,
    password=ORACLE_PASSWORD,
    host=ORACLE_HOST,
    port=ORACLE_PORT,
    query={"service_name": ORACLE_SERVICE},
)

engine = create_engine(connection_url)

Sanity checks
schemas = pd.read_sql("SELECT username FROM all_users ORDER BY username", engine)
print(schemas)

current = pd.read_sql(
    "SELECT sys_context('USERENV','CURRENT_SCHEMA') AS schema FROM dual", engine
)
print(current)


Build explicit Oracle DDL and load
df.columns = [c.upper() for c in df.columns]


def oracle_col_def(col, series):
    dtype = str(series.dtype)

    if dtype == 'object':
        max_len = series.dropna().str.len().max()
        length = min(int(max_len) * 2, 4000) if pd.notna(max_len) and max_len > 0 else 255
        return f'"{col}" VARCHAR2({length} CHAR)'

    elif 'float' in dtype:
        return f'"{col}" FLOAT(126)'

    elif 'int' in dtype:
        return f'"{col}" NUMBER(19)'

    else:
        return f'"{col}" VARCHAR2(255 CHAR)'


col_defs = ",\n    ".join(oracle_col_def(col, df[col]) for col in df.columns)

with engine.begin() as conn:
    try:
        conn.execute(text(f"DROP TABLE {SCHEMA_NAME}.{TABLE_NAME}"))
    except Exception:
        pass  # table doesn't exist yet on first run — that's fine

    conn.execute(text(f"""
        CREATE TABLE {SCHEMA_NAME}.{TABLE_NAME} (
            {col_defs}
        )
    """))

df.to_sql(
    TABLE_NAME,
    engine,
    schema=SCHEMA_NAME,
    if_exists="append",  # table already created above with explicit types
    index=False,
    dtype=None,
)

print(f"Loaded {len(df)} rows into {SCHEMA_NAME}.{TABLE_NAME}")


Verify final schema
verify = pd.read_sql(text(f"""
    SELECT column_name, data_type, data_length, char_used
    FROM all_tab_columns
    WHERE table_name = '{TABLE_NAME}'
    AND owner = '{SCHEMA_NAME}'
    ORDER BY column_id
"""), engine)

print(verify.to_string(index=False))
