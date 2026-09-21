from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
FINANCE_DB_PATH = Path(os.getenv("FINANCE_DB", BASE_DIR / "data" / "finance.db"))

SCHEMA = """
CREATE TABLE IF NOT EXISTS financial_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    institution TEXT NOT NULL DEFAULT '',
    account_type TEXT NOT NULL DEFAULT 'Bank',
    currency TEXT NOT NULL DEFAULT 'PHP',
    opening_balance_minor INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS financial_transactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES financial_accounts(id) ON DELETE RESTRICT,
    occurred_on TEXT NOT NULL,
    transaction_type TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT '',
    description TEXT NOT NULL DEFAULT '',
    amount_minor INTEGER NOT NULL CHECK(amount_minor > 0),
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_financial_transactions_account_date
ON financial_transactions (account_id, occurred_on DESC);

CREATE TABLE IF NOT EXISTS recurring_payments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    account_id INTEGER NOT NULL REFERENCES financial_accounts(id) ON DELETE RESTRICT,
    name TEXT NOT NULL,
    category TEXT NOT NULL DEFAULT 'Monthly payment',
    amount_minor INTEGER NOT NULL CHECK(amount_minor > 0),
    frequency TEXT NOT NULL DEFAULT 'Monthly',
    next_due_date TEXT NOT NULL,
    active INTEGER NOT NULL DEFAULT 1,
    created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_recurring_payments_due
ON recurring_payments (active, next_due_date);
"""


@contextmanager
def get_finance_connection():
    FINANCE_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(FINANCE_DB_PATH)
    connection.row_factory = sqlite3.Row
    connection.execute("PRAGMA foreign_keys = ON")
    try:
        yield connection
        connection.commit()
    finally:
        connection.close()


def init_finance_db() -> None:
    with get_finance_connection() as conn:
        conn.executescript(SCHEMA)


def finance_fetch_all(query: str, params: tuple = ()) -> list[dict]:
    with get_finance_connection() as conn:
        return [dict(row) for row in conn.execute(query, params).fetchall()]


def finance_fetch_one(query: str, params: tuple = ()) -> dict | None:
    with get_finance_connection() as conn:
        row = conn.execute(query, params).fetchone()
        return dict(row) if row else None


def finance_execute(query: str, params: tuple = ()) -> int:
    with get_finance_connection() as conn:
        cursor = conn.execute(query, params)
        return cursor.lastrowid
