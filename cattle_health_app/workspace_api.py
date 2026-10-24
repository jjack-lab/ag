"""Read-only directory and complete-history workspace statistics."""
import csv
import io
import json
from datetime import date, datetime, timedelta, timezone
from typing import Literal, Optional

from fastapi import HTTPException
from fastapi.responses import Response


SHANGHAI = timezone(timedelta(hours=8))
COUNTERS = ("videos", "completed_videos", "failed_videos", "cattle_videos",
            "sheep_videos", "alerts", "high_alerts", "resolved_alerts",
            "tasks_created", "tasks_closed")


def local_day(value):
    parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=SHANGHAI)
    return parsed.astimezone(SHANGHAI).date().isoformat()


def register_workspace_routes(app, repository):
    @app.get("/api/animals")
    def animal_directory(q: str = "", species: Optional[Literal["cattle", "sheep"]] = None):
        with repository._connection() as connection:
            rows = connection.execute("""
                SELECT l.animal_id, l.species, COUNT(DISTINCT l.job_id) AS video_count,
                       MAX(j.created_at) AS last_seen,
                       (SELECT COUNT(*) FROM animal_followups f
                        WHERE f.animal_id = l.animal_id) AS followup_count
                FROM animal_links l JOIN video_jobs j ON l.job_id = j.id
                GROUP BY l.animal_id, l.species ORDER BY last_seen DESC, l.animal_id
            """).fetchall()
        return [dict(row) for row in rows
                if (not species or row["species"] == species)
                and q.strip().casefold() in row["animal_id"].casefold()]

    def summarize(start, end):
        if start and end and start > end:
            raise HTTPException(status_code=422, detail="开始日期不能晚于结束日期")
        first, last = start.isoformat() if start else None, end.isoformat() if end else None
        daily = {}

        def count(timestamp, key):
            day = local_day(timestamp)
            if (first and day < first) or (last and day > last):
                return
            daily.setdefault(day, {"date": day, **dict.fromkeys(COUNTERS, 0)})[key] += 1

        with repository._connection() as connection:
            jobs = connection.execute("SELECT * FROM video_jobs").fetchall()
            alerts = connection.execute("SELECT * FROM alerts").fetchall()
            tasks = connection.execute("SELECT * FROM action_tasks").fetchall()
            # Count completed transitions on their actual update date, once per task.
            closures = connection.execute("""SELECT task_id, MAX(created_at) AS closed_at
                FROM action_task_updates WHERE status = 'closed' GROUP BY task_id""").fetchall()
        for job in jobs:
            count(job["created_at"], "videos")
            result = json.loads(job["result_json"]) if job["result_json"] else None
            if job["status"] == "completed":
                count(job["created_at"], "completed_videos")
                count(job["created_at"], "sheep_videos" if (result or {}).get("species") == "sheep" else "cattle_videos")
            elif job["status"] == "failed":
                count(job["created_at"], "failed_videos")
        for alert in alerts:
            count(alert["occurred_at"], "alerts")
            if alert["level"] == "high":
                count(alert["occurred_at"], "high_alerts")
            if alert["resolved_at"]:
                count(alert["resolved_at"], "resolved_alerts")
        for task in tasks:
            count(task["created_at"], "tasks_created")
        for closure in closures:
            count(closure["closed_at"], "tasks_closed")
        rows = [daily[key] for key in sorted(daily)]
        return {"timezone": "Asia/Shanghai", "start": first, "end": last,
                "daily": rows, "totals": {key: sum(row[key] for row in rows) for key in COUNTERS}}

    @app.get("/api/analytics")
    def analytics(start: Optional[date] = None, end: Optional[date] = None):
        return summarize(start, end)

    @app.get("/api/analytics.csv")
    def analytics_csv(start: Optional[date] = None, end: Optional[date] = None):
        data = summarize(start, end)
        output = io.StringIO()
        writer = csv.DictWriter(output, fieldnames=["date", *COUNTERS])
        writer.writeheader()
        writer.writerows(data["daily"])
        return Response(output.getvalue().encode("utf-8-sig"), media_type="text/csv",
                        headers={"Content-Disposition": 'attachment; filename="workspace-statistics.csv"'})
