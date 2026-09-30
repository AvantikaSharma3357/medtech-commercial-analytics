"""Loads the raw CSV extracts into an in-memory DuckDB warehouse."""
from __future__ import annotations

from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parents[2]
RAW = ROOT / "data" / "raw"
TABLES = ("users", "accounts", "opportunities", "orders")


def connect(raw_dir: Path = RAW) -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection with one table per CSV extract."""
    con = duckdb.connect()
    for table in TABLES:
        path = raw_dir / f"{table}.csv"
        if not path.exists():
            raise FileNotFoundError(f"Missing {path}. Run: python data/generate_data.py")
        con.execute(f"CREATE TABLE {table} AS SELECT * FROM read_csv_auto(?)", [str(path)])
    return con
