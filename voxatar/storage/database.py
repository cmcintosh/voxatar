from __future__ import annotations

"""
SQLite persistence layer for Voxatar call data.

Stores calls, transcript entries, action items, and scorecard entries.
Thread-safe with WAL mode enabled.
"""

import json
import logging
import os
import sqlite3
import threading
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)


class CallDatabase:
    """
    Thread-safe SQLite database for Voxatar call persistence.

    Tables:
        calls             — one row per call session
        transcript_entries — individual transcript lines
        action_items      — tasks extracted from calls
        scorecard_entries — per-objective evaluation results
    """

    def __init__(self, db_path: str | None = None) -> None:
        """
        Initialize the database connection and create tables if needed.

        Args:
            db_path: Filesystem path to the SQLite database file.
                     If None, uses /app/data/voxatar.db if /app exists,
                     otherwise ~/.voxatar/voxatar.db.
        """
        if db_path is None:
            if os.path.isdir("/app"):
                db_path = "/app/data/voxatar.db"
            else:
                db_path = os.path.expanduser("~/.voxatar/voxatar.db")
        self.db_path = db_path
        self._lock = threading.Lock()

        # Ensure parent directory exists
        db_dir = os.path.dirname(db_path)
        if db_dir:
            os.makedirs(db_dir, exist_ok=True)

        # Enable WAL mode and initialise schema
        self._execute("PRAGMA journal_mode=WAL;")
        self._execute("PRAGMA foreign_keys=ON;")
        self.init_db()
        logger.info("CallDatabase initialised at %s", db_path)

    # ------------------------------------------------------------------ #
    #  Low-level helpers                                                 #
    # ------------------------------------------------------------------ #

    def _get_conn(self) -> sqlite3.Connection:
        """Create a new SQLite connection (caller is responsible for closing)."""
        conn = sqlite3.connect(self.db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys=ON;")
        return conn

    def _execute(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
    ) -> sqlite3.Cursor:
        """Execute a single SQL statement with the internal lock."""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(sql, params or ())
                conn.commit()
                return cursor

    def _executemany(
        self,
        sql: str,
        seq_of_params: list[tuple[Any, ...]],
    ) -> None:
        """Execute a statement against multiple parameter sets."""
        with self._lock:
            with self._get_conn() as conn:
                conn.executemany(sql, seq_of_params)
                conn.commit()

    def _query(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
    ) -> list[sqlite3.Row]:
        """Run a SELECT and return all rows."""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(sql, params or ())
                return cursor.fetchall()

    def _query_one(
        self,
        sql: str,
        params: tuple[Any, ...] | None = None,
    ) -> sqlite3.Row | None:
        """Run a SELECT and return a single row (or None)."""
        with self._lock:
            with self._get_conn() as conn:
                cursor = conn.execute(sql, params or ())
                return cursor.fetchone()

    # ------------------------------------------------------------------ #
    #  Schema                                                            #
    # ------------------------------------------------------------------ #

    def init_db(self) -> None:
        """Create all required tables if they do not already exist."""
        statements = [
            """
            CREATE TABLE IF NOT EXISTS calls (
                id              TEXT PRIMARY KEY,
                agent_name      TEXT NOT NULL,
                start_time      TEXT NOT NULL,
                end_time        TEXT,
                duration        REAL,
                summary         TEXT,
                status          TEXT DEFAULT 'active',
                objectives_met  TEXT DEFAULT '[]'
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS transcript_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id     TEXT NOT NULL,
                timestamp   REAL NOT NULL,
                speaker     TEXT NOT NULL,
                text        TEXT NOT NULL,
                is_partial  INTEGER DEFAULT 0,
                FOREIGN KEY (call_id) REFERENCES calls(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS action_items (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id     TEXT NOT NULL,
                task        TEXT NOT NULL,
                assignee    TEXT,
                due_date    TEXT,
                status      TEXT DEFAULT 'open',
                FOREIGN KEY (call_id) REFERENCES calls(id) ON DELETE CASCADE
            )
            """,
            """
            CREATE TABLE IF NOT EXISTS scorecard_entries (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                call_id     TEXT NOT NULL,
                objective   TEXT NOT NULL,
                status      TEXT NOT NULL,
                notes       TEXT,
                FOREIGN KEY (call_id) REFERENCES calls(id) ON DELETE CASCADE
            )
            """,
            "CREATE INDEX IF NOT EXISTS idx_transcript_call_id ON transcript_entries(call_id)",
            "CREATE INDEX IF NOT EXISTS idx_action_items_call_id ON action_items(call_id)",
            "CREATE INDEX IF NOT EXISTS idx_scorecard_call_id ON scorecard_entries(call_id)",
        ]
        for stmt in statements:
            self._execute(stmt)

    # ------------------------------------------------------------------ #
    #  Call CRUD                                                         #
    # ------------------------------------------------------------------ #

    def create_call(
        self,
        call_id: str,
        agent_name: str,
        start_time: str,
    ) -> None:
        """
        Insert a new call row.

        Args:
            call_id: Unique call identifier.
            agent_name: Name of the Voxatar agent.
            start_time: ISO-8601 timestamp string.
        """
        self._execute(
            "INSERT INTO calls (id, agent_name, start_time, status) VALUES (?, ?, ?, 'active')",
            (call_id, agent_name, start_time),
        )
        logger.debug("Created call %s for agent %s", call_id, agent_name)

    def update_call_end(
        self,
        call_id: str,
        end_time: str,
        duration: float,
        summary: str,
        status: str,
        objectives_met: list[str],
    ) -> None:
        """
        Finalise a call with end time, summary, and objectives.

        Args:
            call_id: Unique call identifier.
            end_time: ISO-8601 timestamp string.
            duration: Call duration in seconds.
            summary: LLM-generated summary text.
            status: Final status (e.g. "completed", "failed").
            objectives_met: List of objective strings that were achieved.
        """
        self._execute(
            """
            UPDATE calls
            SET end_time = ?, duration = ?, summary = ?, status = ?, objectives_met = ?
            WHERE id = ?
            """,
            (
                end_time,
                duration,
                summary,
                status,
                json.dumps(objectives_met),
                call_id,
            ),
        )
        logger.debug("Updated call %s: status=%s duration=%.1fs", call_id, status, duration)

    def get_calls(self, limit: int = 50, offset: int = 0) -> list[dict]:
        """
        Retrieve a paginated list of calls (newest first).

        Returns:
            List of call dictionaries.
        """
        rows = self._query(
            "SELECT * FROM calls ORDER BY start_time DESC LIMIT ? OFFSET ?",
            (limit, offset),
        )
        return [self._row_to_call_dict(r) for r in rows]

    def get_call(self, call_id: str) -> dict | None:
        """Return a single call dict by id, or None if not found."""
        row = self._query_one("SELECT * FROM calls WHERE id = ?", (call_id,))
        if row is None:
            return None
        return self._row_to_call_dict(row)

    def delete_call(self, call_id: str) -> bool:
        """
        Delete a call and all related rows (cascade).

        Returns:
            True if a row was deleted, False otherwise.
        """
        cursor = self._execute("DELETE FROM calls WHERE id = ?", (call_id,))
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted call %s and related data", call_id)
        return deleted

    # ------------------------------------------------------------------ #
    #  Transcript                                                        #
    # ------------------------------------------------------------------ #

    def save_transcript_entry(
        self,
        call_id: str,
        timestamp: float,
        speaker: str,
        text: str,
        is_partial: bool = False,
    ) -> None:
        """Insert a single transcript entry."""
        self._execute(
            """
            INSERT INTO transcript_entries (call_id, timestamp, speaker, text, is_partial)
            VALUES (?, ?, ?, ?, ?)
            """,
            (call_id, timestamp, speaker, text, 1 if is_partial else 0),
        )

    def get_transcript(self, call_id: str) -> list[dict]:
        """Return all transcript entries for a call, ordered by time."""
        rows = self._query(
            "SELECT * FROM transcript_entries WHERE call_id = ? ORDER BY timestamp ASC",
            (call_id,),
        )
        return [
            {
                "id": r["id"],
                "call_id": r["call_id"],
                "timestamp": r["timestamp"],
                "speaker": r["speaker"],
                "text": r["text"],
                "is_partial": bool(r["is_partial"]),
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    #  Action items                                                      #
    # ------------------------------------------------------------------ #

    def save_action_items(self, call_id: str, items: list[dict]) -> None:
        """
        Replace all action items for a call.

        Each dict should contain: task, assignee, due_date, status.
        """
        # Remove existing items for this call
        self._execute("DELETE FROM action_items WHERE call_id = ?", (call_id,))
        if not items:
            return
        rows = [
            (
                call_id,
                item.get("task", ""),
                item.get("assignee"),
                item.get("due_date"),
                item.get("status", "open"),
            )
            for item in items
        ]
        self._executemany(
            """
            INSERT INTO action_items (call_id, task, assignee, due_date, status)
            VALUES (?, ?, ?, ?, ?)
            """,
            rows,
        )
        logger.debug("Saved %d action items for call %s", len(rows), call_id)

    def get_action_items(self, call_id: str) -> list[dict]:
        """Return all action items for a call."""
        rows = self._query(
            "SELECT * FROM action_items WHERE call_id = ? ORDER BY id ASC",
            (call_id,),
        )
        return [
            {
                "id": r["id"],
                "call_id": r["call_id"],
                "task": r["task"],
                "assignee": r["assignee"],
                "due_date": r["due_date"],
                "status": r["status"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    #  Scorecard                                                         #
    # ------------------------------------------------------------------ #

    def save_scorecard(self, call_id: str, entries: list[dict]) -> None:
        """
        Replace all scorecard entries for a call.

        Each dict should contain: objective, status, notes.
        """
        self._execute("DELETE FROM scorecard_entries WHERE call_id = ?", (call_id,))
        if not entries:
            return
        rows = [
            (
                call_id,
                entry.get("objective", ""),
                entry.get("status", ""),
                entry.get("notes"),
            )
            for entry in entries
        ]
        self._executemany(
            """
            INSERT INTO scorecard_entries (call_id, objective, status, notes)
            VALUES (?, ?, ?, ?)
            """,
            rows,
        )
        logger.debug("Saved %d scorecard entries for call %s", len(rows), call_id)

    def get_scorecard(self, call_id: str) -> list[dict]:
        """Return all scorecard entries for a call."""
        rows = self._query(
            "SELECT * FROM scorecard_entries WHERE call_id = ? ORDER BY id ASC",
            (call_id,),
        )
        return [
            {
                "id": r["id"],
                "call_id": r["call_id"],
                "objective": r["objective"],
                "status": r["status"],
                "notes": r["notes"],
            }
            for r in rows
        ]

    # ------------------------------------------------------------------ #
    #  Utilities                                                         #
    # ------------------------------------------------------------------ #

    @staticmethod
    def _row_to_call_dict(row: sqlite3.Row) -> dict:
        """Convert a calls row to a plain dict with parsed JSON."""
        return {
            "id": row["id"],
            "agent_name": row["agent_name"],
            "start_time": row["start_time"],
            "end_time": row["end_time"],
            "duration": row["duration"],
            "summary": row["summary"],
            "status": row["status"],
            "objectives_met": json.loads(row["objectives_met"] or "[]"),
        }