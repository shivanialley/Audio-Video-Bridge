from __future__ import annotations

import sqlite3
import threading
from backend.app.config import DB_PATH

_local = threading.local()

def get_db():
    if not hasattr(_local, "conn"):
        _local.conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
        _local.conn.row_factory = sqlite3.Row
    return _local.conn

def init_db():
    conn = get_db()
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS jobs (
            id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            stage_message TEXT,
            progress INTEGER DEFAULT 0,
            original_filename TEXT,
            source_language TEXT,
            target_language TEXT,
            has_video INTEGER DEFAULT 0,
            error TEXT,
            artifacts TEXT
        )
        """
    )
    conn.commit()

def update_job_stage(job_id: str, stage_message: str, progress: int = 0, status: str = "processing", error: str | None = None):
    """Updates job progress and status messages in SQLite."""
    conn = get_db()
    conn.execute(
        """
        UPDATE jobs 
        SET stage_message = ?, progress = ?, status = ?, error = ?
        WHERE id = ?
        """,
        (stage_message, progress, status, error, job_id)
    )
    conn.commit()