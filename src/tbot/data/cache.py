"""Parquet data files with a SQLite index, using only strings for decimal values.

Files are immutable and written atomically before updating their index entry.
Old files may remain after refresh; they are harmless and can be removed when
no readers are running. Cache keys describe exact requests, not partial coverage.
"""
import hashlib
import json
import os
import sqlite3
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from pathlib import Path
from uuid import uuid4
import pyarrow as pa
import pyarrow.parquet as pq
from tbot.core.models import Candle

SCHEMA = pa.schema([(name, pa.string()) for name in
                    ("timestamp", "symbol", "open", "high", "low", "close", "volume")])


class CandleCache:
    def __init__(self, directory):
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)
        self.database = self.directory / "index.sqlite3"
        with sqlite3.connect(self.database) as connection:
            connection.execute("""CREATE TABLE IF NOT EXISTS datasets
                (cache_key TEXT PRIMARY KEY, request TEXT NOT NULL,
                 filename TEXT NOT NULL, row_count INTEGER NOT NULL,
                 saved_at TEXT NOT NULL)""")

    @staticmethod
    def key(request):
        return hashlib.sha256(json.dumps(request, sort_keys=True).encode()).hexdigest()

    def load(self, request):
        with sqlite3.connect(self.database) as connection:
            row = connection.execute("SELECT filename, row_count FROM datasets WHERE cache_key = ?",
                                     (self.key(request),)).fetchone()
        if row is None:
            return None
        table = pq.read_table(self.directory / row[0], schema=SCHEMA)
        if table.num_rows != row[1]:
            raise ValueError("Cached row count does not match its index")
        try:
            return [Candle(datetime.fromisoformat(r["timestamp"]), r["symbol"],
                           *(Decimal(r[key]) for key in ("open", "high", "low", "close", "volume")))
                    for r in table.to_pylist()]
        except (InvalidOperation, ValueError, KeyError, TypeError) as error:
            raise ValueError("Cached candle file contains malformed values; refresh the dataset") from error

    def save(self, request, candles):
        filename = self.key(request) + "-" + uuid4().hex + ".parquet"
        path = self.directory / filename
        temporary = path.with_suffix(".tmp")
        rows = [dict(timestamp=c.timestamp.isoformat(), symbol=c.symbol,
                     **{key: str(getattr(c, key)) for key in ("open", "high", "low", "close", "volume")})
                for c in candles]
        try:
            pq.write_table(pa.Table.from_pylist(rows, schema=SCHEMA), temporary)
            os.replace(temporary, path)
            with sqlite3.connect(self.database) as connection:
                connection.execute("INSERT OR REPLACE INTO datasets VALUES (?, ?, ?, ?, ?)",
                                   (self.key(request), json.dumps(request, sort_keys=True), filename,
                                    len(candles), datetime.now(timezone.utc).isoformat()))
        finally:
            temporary.unlink(missing_ok=True)
