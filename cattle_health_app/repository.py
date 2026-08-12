from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import replace
from pathlib import Path

from cattle_health_app.domain import AlertLevel, AlertRecord, VideoJobRecord


class SQLiteRepository:
    def __init__(self, database_path: str | Path):
        self.database_path = Path(database_path)

    def initialize(self):
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connection() as connection:
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS alerts (
                    id TEXT PRIMARY KEY,
                    cattle_id TEXT NOT NULL,
                    risk_type TEXT NOT NULL,
                    level TEXT NOT NULL,
                    reason TEXT NOT NULL,
                    suggestion TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    confidence REAL NOT NULL,
                    evidence_path TEXT,
                    status TEXT NOT NULL,
                    resolution TEXT,
                    resolved_at TEXT
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_jobs (
                    id TEXT PRIMARY KEY,
                    source_path TEXT NOT NULL,
                    status TEXT NOT NULL,
                    progress REAL NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    result_json TEXT,
                    error TEXT
                )
                """
            )

    def save_alert(self, alert: AlertRecord):
        values = alert.to_dict()
        values["level"] = alert.level.value
        with self._connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO alerts (
                    id, cattle_id, risk_type, level, reason, suggestion,
                    occurred_at, confidence, evidence_path, status,
                    resolution, resolved_at
                ) VALUES (
                    :id, :cattle_id, :risk_type, :level, :reason, :suggestion,
                    :occurred_at, :confidence, :evidence_path, :status,
                    :resolution, :resolved_at
                )
                """,
                values,
            )

    def list_alerts(self, status: str | None = None):
        query = "SELECT * FROM alerts"
        parameters = ()
        if status is not None:
            query += " WHERE status = ?"
            parameters = (status,)
        query += " ORDER BY occurred_at DESC"
        with self._connection() as connection:
            rows = connection.execute(query, parameters).fetchall()
        return [self._to_alert(row) for row in rows]

    def resolve_alert(self, alert_id: str, resolution: str, resolved_at: str):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM alerts WHERE id = ?", (alert_id,)
            ).fetchone()
            if row is None:
                raise KeyError(alert_id)
            current = self._to_alert(row)
            resolved = replace(
                current,
                status="resolved",
                resolution=resolution,
                resolved_at=resolved_at,
            )
            self.save_alert(resolved)
        return resolved

    def save_video_job(self, job: VideoJobRecord):
        values = job.to_dict()
        values["result_json"] = (
            json.dumps(job.result, ensure_ascii=False) if job.result is not None else None
        )
        values.pop("result")
        with self._connection() as connection:
            connection.execute(
                """
                INSERT OR REPLACE INTO video_jobs (
                    id, source_path, status, progress, created_at, updated_at,
                    result_json, error
                ) VALUES (
                    :id, :source_path, :status, :progress, :created_at, :updated_at,
                    :result_json, :error
                )
                """,
                values,
            )

    def get_video_job(self, job_id: str) -> VideoJobRecord:
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM video_jobs WHERE id = ?", (job_id,)
            ).fetchone()
        if row is None:
            raise KeyError(job_id)
        return self._to_video_job(row)

    def latest_completed_video_job(self) -> VideoJobRecord:
        with self._connection() as connection:
            row = connection.execute(
                """
                SELECT * FROM video_jobs
                WHERE status = 'completed'
                ORDER BY updated_at DESC
                LIMIT 1
                """
            ).fetchone()
        if row is None:
            raise KeyError("completed")
        return self._to_video_job(row)

    @staticmethod
    def _to_video_job(row):
        values = dict(row)
        values["result"] = (
            json.loads(values["result_json"])
            if values["result_json"] is not None
            else None
        )
        values.pop("result_json")
        return VideoJobRecord(**values)

    @contextmanager
    def _connection(self):
        connection = sqlite3.connect(self.database_path)
        connection.row_factory = sqlite3.Row
        try:
            with connection:
                yield connection
        finally:
            connection.close()

    @staticmethod
    def _to_alert(row):
        values = dict(row)
        values["level"] = AlertLevel(values["level"])
        return AlertRecord(**values)
