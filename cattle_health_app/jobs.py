from __future__ import annotations

import csv
import inspect
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import replace
from datetime import datetime, timedelta
from pathlib import Path
from uuid import uuid4

from cattle_health_app.domain import AlertLevel, AlertRecord, VideoJobRecord

INTERRUPTED_MESSAGE = "服务重启：任务已中断，请重新提交"


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec="seconds")


class VideoJobService:
    def __init__(self, repository, processor, result_root, executor=None):
        self.repository = repository
        self.processor = processor
        self.result_root = Path(result_root)
        self.executor = executor or ThreadPoolExecutor(max_workers=1)

    def create(self, source_path, conf, iou, class_id, tracker):
        timestamp = now_iso()
        job = VideoJobRecord(
            id=uuid4().hex,
            source_path=str(source_path),
            status="queued",
            progress=0.0,
            created_at=timestamp,
            updated_at=timestamp,
        )
        self.repository.save_video_job(job)
        self.executor.submit(self._run, job, conf, iou, class_id, tracker)
        return job

    def recover_interrupted(self):
        """把上个进程遗留的 queued/running 任务标记为中断，返回受影响的任务 ID。"""
        return self.repository.mark_interrupted_video_jobs(
            now_iso(), INTERRUPTED_MESSAGE
        )

    def _run(self, job, conf, iou, class_id, tracker):
        running = replace(
            job,
            status="running",
            progress=0.05,
            updated_at=now_iso(),
        )
        self.repository.save_video_job(running)
        try:
            track_video = self.processor.track_video

            last_progress = 0.05
            last_saved = time.monotonic()

            def update_progress(value):
                nonlocal last_progress, last_saved
                progress = max(0.05, min(0.99, float(value)))
                now = time.monotonic()
                # 不逐帧写库：进度推进 >=1% 或距上次写入 >=1 秒才落盘。
                if progress - last_progress < 0.01 and now - last_saved < 1.0:
                    return
                last_progress = progress
                last_saved = now
                self.repository.save_video_job(
                    replace(running, progress=progress, updated_at=now_iso())
                )

            arguments = (
                running.source_path,
                self.result_root / running.id,
                conf,
                iou,
                class_id,
                tracker,
            )
            if "progress_callback" in inspect.signature(track_video).parameters:
                result = track_video(*arguments, progress_callback=update_progress)
            else:
                result = track_video(*arguments)
            completed = replace(
                running,
                status="completed",
                progress=1.0,
                updated_at=now_iso(),
                result=result.to_dict(self.result_root),
            )
            self.repository.save_video_job(completed)
            self._persist_alerts(completed, result.alert_csv)
            self._persist_trajectory_anomalies(
                completed, result.trajectory_anomaly_csv
            )
        except Exception as error:
            failed = replace(
                running,
                status="failed",
                updated_at=now_iso(),
                error=str(error),
            )
            self.repository.save_video_job(failed)

    def _persist_alerts(self, job, alert_csv):
        occurred_base = datetime.fromisoformat(job.created_at)
        evidence_path = job.result["video_path"]
        with Path(alert_csv).open("r", encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                occurred_at = occurred_base + timedelta(
                    seconds=float(row["time_seconds"])
                )
                alert = AlertRecord(
                    id=(
                        f"{job.id}:{row['track_id']}:{row['alert_type']}:"
                        f"{row['frame_index']}"
                    ),
                    cattle_id=row["track_id"],
                    risk_type=row["alert_type"],
                    level=AlertLevel(row["severity"]),
                    reason=row["detail"],
                    suggestion=row["suggestion"],
                    occurred_at=occurred_at.isoformat(timespec="seconds"),
                    confidence=float(row["confidence"]),
                    evidence_path=evidence_path,
                )
                self.repository.save_alert(alert)

    def _persist_trajectory_anomalies(self, job, anomaly_csv):
        if not anomaly_csv:
            return
        anomaly_path = Path(anomaly_csv)
        if not anomaly_path.is_file():
            return
        occurred_base = datetime.fromisoformat(job.created_at)
        evidence_path = job.result["video_path"]
        with anomaly_path.open("r", encoding="utf-8-sig", newline="") as source:
            for row in csv.DictReader(source):
                if row.get("is_outlier") != "1":
                    continue
                score = float(row["anomaly_score"])
                occurred_at = occurred_base + timedelta(
                    seconds=float(row.get("duration_seconds", 0.0))
                )
                contributors = row.get("top_contributors", "")
                reason = (
                    f"活动模式偏离牛群整体（Isolation Forest 异常得分 {score:.2f}）。"
                )
                if contributors:
                    reason += f" 主要差异特征：{contributors}。"
                alert = AlertRecord(
                    id=f"{job.id}:{row['track_id']}:trajectory_anomaly",
                    cattle_id=row["track_id"],
                    risk_type="trajectory_anomaly",
                    level=AlertLevel.MEDIUM,
                    reason=reason,
                    suggestion="建议人工复核该牛的活动能力、采食与精神状态。",
                    occurred_at=occurred_at.isoformat(timespec="seconds"),
                    confidence=score,
                    evidence_path=evidence_path,
                )
                self.repository.save_alert(alert)
