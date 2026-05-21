"""SQLite event log for every semantic-layer query.

Never raises — wraps inserts in try/except and prints a stderr warning on failure.
Schema is small and append-only. Telemetry is the prototype's observability surface;
production would replace it with a real metric pipeline.
"""

from __future__ import annotations

import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TELEMETRY_DB = _PROJECT_ROOT / "telemetry.db"

SCHEMA_DDL = """
CREATE TABLE IF NOT EXISTS queries (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ts TEXT NOT NULL,
    tenant_id TEXT,
    question TEXT NOT NULL,
    metric_id TEXT,
    applied_definition TEXT,
    sql TEXT,
    execution_ms REAL,
    success INTEGER NOT NULL,
    error TEXT,
    narrative TEXT
);
"""


class Telemetry:
    """Append-only SQLite logger. Failures are swallowed with a stderr warning."""

    def __init__(self, db_path: Path | str = DEFAULT_TELEMETRY_DB) -> None:
        self.db_path = Path(db_path)
        try:
            con = sqlite3.connect(self.db_path)
            con.execute(SCHEMA_DDL)
            con.commit()
            con.close()
        except sqlite3.Error as e:
            print(
                f"telemetry: failed to initialize schema at {self.db_path}: {e}",
                file=sys.stderr,
            )

    def log_query(
        self,
        *,
        tenant_id: str | None,
        question: str,
        metric_id: str | None,
        applied_definition: str | None,
        sql: str | None,
        execution_ms: float | None,
        success: bool,
        error: str | None,
        narrative: str | None,
    ) -> None:
        ts = datetime.now(UTC).isoformat()
        try:
            con = sqlite3.connect(self.db_path)
            con.execute(
                """
                INSERT INTO queries
                  (ts, tenant_id, question, metric_id, applied_definition,
                   sql, execution_ms, success, error, narrative)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ts,
                    tenant_id,
                    question,
                    metric_id,
                    applied_definition,
                    sql,
                    execution_ms,
                    1 if success else 0,
                    error,
                    narrative,
                ),
            )
            con.commit()
            con.close()
        except sqlite3.Error as e:
            print(f"telemetry: log_query failed: {e}", file=sys.stderr)


__all__ = ["Telemetry", "DEFAULT_TELEMETRY_DB"]
