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
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_reviews (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES video_jobs(id),
                    species TEXT NOT NULL,
                    issue_type TEXT NOT NULL,
                    track_id INTEGER,
                    time_seconds REAL,
                    verdict TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS video_reviews_job_idx ON video_reviews(job_id, created_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS action_tasks (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES video_jobs(id),
                    species TEXT NOT NULL,
                    title TEXT NOT NULL,
                    track_id INTEGER,
                    time_seconds REAL,
                    assignee TEXT NOT NULL,
                    due_at TEXT NOT NULL,
                    status TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS action_tasks_job_idx ON action_tasks(job_id, created_at, id)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS action_tasks_status_idx ON action_tasks(status, due_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS action_task_updates (
                    id TEXT PRIMARY KEY,
                    task_id TEXT NOT NULL REFERENCES action_tasks(id),
                    status TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    note TEXT NOT NULL,
                    next_due_at TEXT,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS action_task_updates_task_idx ON action_task_updates(task_id, created_at, id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS video_corrections (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES video_jobs(id),
                    species TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    frame_index INTEGER NOT NULL,
                    time_seconds REAL NOT NULL,
                    track_id INTEGER,
                    corrected_track_id INTEGER,
                    behavior_label TEXT,
                    box_json TEXT,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS video_corrections_job_idx ON video_corrections(job_id, frame_index)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS dataset_evaluations (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES video_jobs(id),
                    dataset_name TEXT NOT NULL,
                    source_url TEXT NOT NULL,
                    dataset_version TEXT NOT NULL,
                    license_name TEXT NOT NULL,
                    split_name TEXT NOT NULL,
                    video_sha256 TEXT NOT NULL,
                    annotations_sha256 TEXT NOT NULL,
                    metrics_json TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS animal_links (
                    job_id TEXT NOT NULL REFERENCES video_jobs(id),
                    track_id INTEGER NOT NULL,
                    animal_id TEXT NOT NULL,
                    species TEXT NOT NULL,
                    linked_at TEXT NOT NULL,
                    PRIMARY KEY (job_id, track_id)
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS animal_links_animal_idx ON animal_links(animal_id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS animal_followups (
                    id TEXT PRIMARY KEY,
                    animal_id TEXT NOT NULL,
                    kind TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    note TEXT NOT NULL,
                    diagnosis TEXT,
                    source_reference TEXT,
                    verification_status TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS animal_followups_animal_idx ON animal_followups(animal_id, observed_at)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory_checks (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL REFERENCES video_jobs(id),
                    species TEXT NOT NULL,
                    pen_id TEXT NOT NULL,
                    expected_count INTEGER NOT NULL,
                    baseline_source TEXT NOT NULL,
                    observed_count INTEGER,
                    coverage TEXT NOT NULL,
                    coverage_note TEXT NOT NULL,
                    operator_name TEXT NOT NULL,
                    observed_at TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS inventory_checks_pen_idx ON inventory_checks(pen_id, created_at)"
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS inventory_checks_job_idx ON inventory_checks(job_id, created_at, id)"
            )
            connection.execute(
                """
                CREATE TABLE IF NOT EXISTS inventory_rechecks (
                    id TEXT PRIMARY KEY,
                    check_id TEXT NOT NULL REFERENCES inventory_checks(id),
                    counted_count INTEGER NOT NULL,
                    outcome TEXT NOT NULL,
                    movement_records_checked INTEGER NOT NULL,
                    field_search_complete INTEGER NOT NULL,
                    lost_count INTEGER,
                    operator_name TEXT NOT NULL,
                    note TEXT NOT NULL,
                    created_at TEXT NOT NULL
                )
                """
            )
            connection.execute(
                "CREATE INDEX IF NOT EXISTS inventory_rechecks_check_idx ON inventory_rechecks(check_id, created_at)"
            )

    def save_inventory_check(self, check: dict):
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO inventory_checks
                (id, job_id, species, pen_id, expected_count, baseline_source,
                 observed_count, coverage, coverage_note, operator_name, observed_at, created_at)
                VALUES (:id, :job_id, :species, :pen_id, :expected_count, :baseline_source,
                        :observed_count, :coverage, :coverage_note, :operator_name, :observed_at, :created_at)
                """,
                check,
            )

    def get_inventory_check(self, check_id: str):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM inventory_checks WHERE id = ?", (check_id,)
            ).fetchone()
        if row is None:
            raise KeyError(check_id)
        return dict(row)

    def list_inventory_checks(self, limit: int = 100):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM inventory_checks ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_inventory_checks_for_job(self, job_id: str):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM inventory_checks WHERE job_id = ? "
                "ORDER BY created_at DESC, id DESC",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def page_inventory_checks(
        self, *, limit: int = 20, offset: int = 0,
        pen_id: str = "", status: str = "",
    ):
        scoped = """
            WITH latest AS (
                SELECT check_id, outcome,
                    ROW_NUMBER() OVER (
                        PARTITION BY check_id ORDER BY created_at DESC, rowid DESC
                    ) AS rank
                FROM inventory_rechecks
            ), scoped AS (
                SELECT c.*,
                    CASE
                        WHEN c.coverage != 'complete' THEN 'coverage_needed'
                        WHEN latest.outcome = 'resolved' THEN 'verified_match'
                        WHEN latest.outcome = 'shortfall_pending' THEN 'shortfall_pending'
                        WHEN latest.outcome = 'surplus_pending' THEN 'surplus_pending'
                        WHEN latest.outcome = 'loss_user_recorded' THEN 'loss_user_recorded'
                        WHEN c.observed_count IS NULL THEN 'count_needed'
                        WHEN c.expected_count = c.observed_count THEN 'preliminary_match'
                        ELSE 'discrepancy_pending'
                    END AS computed_status
                FROM inventory_checks AS c
                LEFT JOIN latest ON latest.check_id = c.id AND latest.rank = 1
                WHERE instr(lower(c.pen_id), lower(?)) > 0
            )
        """
        params = (pen_id, status, status)
        where = "WHERE (? = '' OR computed_status = ?)"
        with self._connection() as connection:
            total = connection.execute(
                scoped + "SELECT COUNT(*) FROM scoped " + where, params,
            ).fetchone()[0]
            rows = connection.execute(
                scoped + "SELECT * FROM scoped " + where +
                " ORDER BY created_at DESC, id DESC LIMIT ? OFFSET ?",
                (*params, limit, offset),
            ).fetchall()
        return [dict(row) for row in rows], total

    def save_inventory_recheck(self, recheck: dict):
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO inventory_rechecks
                (id, check_id, counted_count, outcome, movement_records_checked,
                 field_search_complete, lost_count, operator_name, note, created_at)
                VALUES (:id, :check_id, :counted_count, :outcome, :movement_records_checked,
                        :field_search_complete, :lost_count, :operator_name, :note, :created_at)
                """,
                recheck,
            )

    def list_inventory_rechecks(self, check_id: str):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM inventory_rechecks WHERE check_id = ? ORDER BY created_at, rowid",
                (check_id,),
            ).fetchall()
        return [dict(row) for row in rows]

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

    def list_video_jobs(self, limit: int = 20):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM video_jobs ORDER BY created_at DESC, id DESC LIMIT ?",
                (limit,),
            ).fetchall()
        return [self._to_video_job(row) for row in rows]

    def save_video_review(self, review: dict):
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO video_reviews
                (id, job_id, species, issue_type, track_id, time_seconds, verdict, note, created_at)
                VALUES (:id, :job_id, :species, :issue_type, :track_id, :time_seconds,
                        :verdict, :note, :created_at)
                """,
                review,
            )

    def list_video_reviews(self, job_id: str):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM video_reviews WHERE job_id = ? ORDER BY created_at, id",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def create_action_task(self, task: dict):
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO action_tasks
                (id, job_id, species, title, track_id, time_seconds, assignee,
                 due_at, status, created_at, updated_at)
                VALUES (:id, :job_id, :species, :title, :track_id, :time_seconds,
                        :assignee, :due_at, :status, :created_at, :updated_at)""",
                task,
            )

    def get_action_task(self, task_id: str):
        with self._connection() as connection:
            row = connection.execute(
                "SELECT * FROM action_tasks WHERE id = ?", (task_id,)
            ).fetchone()
            if row is None:
                raise KeyError(task_id)
            updates = connection.execute(
                "SELECT * FROM action_task_updates WHERE task_id = ? ORDER BY rowid",
                (task_id,),
            ).fetchall()
        return {**dict(row), "updates": [dict(item) for item in updates]}

    def list_action_tasks(self, *, job_id=None, status=None, assignee=None):
        conditions = []
        values = []
        for column, value in (("job_id", job_id), ("status", status), ("assignee", assignee)):
            if value is not None:
                conditions.append(f"{column} = ?")
                values.append(value)
        where = " WHERE " + " AND ".join(conditions) if conditions else ""
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT id FROM action_tasks" + where + " ORDER BY created_at DESC, id DESC",
                values,
            ).fetchall()
        return [self.get_action_task(row["id"]) for row in rows]

    def append_action_task_update(self, task_id: str, update: dict):
        with self._connection() as connection:
            cursor = connection.execute(
                "UPDATE action_tasks SET status = ?, due_at = COALESCE(?, due_at), updated_at = ? WHERE id = ?",
                (update["status"], update["next_due_at"], update["created_at"], task_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(task_id)
            connection.execute(
                """INSERT INTO action_task_updates
                (id, task_id, status, actor, note, next_due_at, created_at)
                VALUES (:id, :task_id, :status, :actor, :note, :next_due_at, :created_at)""",
                update,
            )

    def save_video_correction(self, correction: dict):
        values = {**correction, "box_json": json.dumps(correction["box"]) if correction["box"] else None}
        values.pop("box")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO video_corrections
                (id, job_id, species, kind, frame_index, time_seconds, track_id,
                 corrected_track_id, behavior_label, box_json, note, created_at)
                VALUES (:id, :job_id, :species, :kind, :frame_index, :time_seconds, :track_id,
                        :corrected_track_id, :behavior_label, :box_json, :note, :created_at)""",
                values,
            )

    def list_video_corrections(self, job_id: str):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM video_corrections WHERE job_id = ? ORDER BY frame_index, created_at, id",
                (job_id,),
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            box_json = value.pop("box_json")
            value["box"] = json.loads(box_json) if box_json else None
            result.append(value)
        return result

    def delete_video_correction(self, job_id: str, correction_id: str):
        with self._connection() as connection:
            cursor = connection.execute(
                "DELETE FROM video_corrections WHERE job_id = ? AND id = ?",
                (job_id, correction_id),
            )
            if cursor.rowcount == 0:
                raise KeyError(correction_id)

    def save_dataset_evaluation(self, evaluation: dict):
        values = {**evaluation, "metrics_json": json.dumps(evaluation["metrics"])}
        values.pop("metrics")
        with self._connection() as connection:
            connection.execute(
                """INSERT INTO dataset_evaluations
                (id, job_id, dataset_name, source_url, dataset_version, license_name,
                 split_name, video_sha256, annotations_sha256, metrics_json, created_at)
                VALUES (:id, :job_id, :dataset_name, :source_url, :dataset_version, :license_name,
                        :split_name, :video_sha256, :annotations_sha256, :metrics_json, :created_at)""",
                values,
            )

    def list_dataset_evaluations(self):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM dataset_evaluations ORDER BY created_at DESC, id DESC"
            ).fetchall()
        result = []
        for row in rows:
            value = dict(row)
            value["metrics"] = json.loads(value.pop("metrics_json"))
            result.append(value)
        return result

    def save_animal_link(self, link: dict):
        with self._connection() as connection:
            existing = connection.execute(
                "SELECT animal_id FROM animal_links WHERE job_id = ? AND track_id = ?",
                (link["job_id"], link["track_id"]),
            ).fetchone()
            if existing is not None:
                if existing["animal_id"] != link["animal_id"]:
                    raise ValueError("track_already_linked")
                return
            species = connection.execute(
                "SELECT species FROM animal_links WHERE animal_id = ? LIMIT 1",
                (link["animal_id"],),
            ).fetchone()
            if species is not None and species["species"] != link["species"]:
                raise ValueError("species_mismatch")
            same_job = connection.execute(
                "SELECT track_id FROM animal_links WHERE job_id = ? AND animal_id = ?",
                (link["job_id"], link["animal_id"]),
            ).fetchone()
            if same_job is not None:
                raise ValueError("animal_already_linked_in_job")
            connection.execute(
                """
                INSERT INTO animal_links (job_id, track_id, animal_id, species, linked_at)
                VALUES (:job_id, :track_id, :animal_id, :species, :linked_at)
                """,
                link,
            )

    def list_animal_links(self, animal_id: str):
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT l.* FROM animal_links l JOIN video_jobs j ON j.id = l.job_id
                WHERE l.animal_id = ? ORDER BY j.created_at, l.job_id
                """,
                (animal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def list_job_animal_links(self, job_id: str):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM animal_links WHERE job_id = ? ORDER BY track_id",
                (job_id,),
            ).fetchall()
        return [dict(row) for row in rows]

    def delete_animal_link(self, job_id: str, track_id: int):
        with self._connection() as connection:
            link = connection.execute(
                "SELECT animal_id FROM animal_links WHERE job_id = ? AND track_id = ?",
                (job_id, track_id),
            ).fetchone()
            if link is None:
                raise KeyError((job_id, track_id))
            other = connection.execute(
                "SELECT 1 FROM animal_links WHERE animal_id = ? AND NOT (job_id = ? AND track_id = ?) LIMIT 1",
                (link["animal_id"], job_id, track_id),
            ).fetchone()
            followup = connection.execute(
                "SELECT 1 FROM animal_followups WHERE animal_id = ? LIMIT 1",
                (link["animal_id"],),
            ).fetchone()
            if other is None and followup is not None:
                raise ValueError("已有回访记录，需先保留至少一个个体关联")
            connection.execute(
                "DELETE FROM animal_links WHERE job_id = ? AND track_id = ?",
                (job_id, track_id),
            )

    def save_animal_followup(self, followup: dict):
        with self._connection() as connection:
            connection.execute(
                """
                INSERT INTO animal_followups
                (id, animal_id, kind, observed_at, note, diagnosis,
                 source_reference, verification_status, created_at)
                VALUES (:id, :animal_id, :kind, :observed_at, :note, :diagnosis,
                        :source_reference, :verification_status, :created_at)
                """,
                followup,
            )

    def list_animal_followups(self, animal_id: str):
        with self._connection() as connection:
            rows = connection.execute(
                "SELECT * FROM animal_followups WHERE animal_id = ? ORDER BY observed_at, created_at, id",
                (animal_id,),
            ).fetchall()
        return [dict(row) for row in rows]

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

    def latest_completed_cattle_video_job(self) -> VideoJobRecord:
        with self._connection() as connection:
            rows = connection.execute(
                """
                SELECT * FROM video_jobs
                WHERE status = 'completed' AND result_json IS NOT NULL
                ORDER BY updated_at DESC, id DESC
                """
            ).fetchall()
        for row in rows:
            job = self._to_video_job(row)
            if job.result.get("species", "cattle") == "cattle":
                return job
        raise KeyError("completed cattle")

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
