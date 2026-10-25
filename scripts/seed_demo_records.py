"""Seed clearly marked, reversible demonstration records for an existing cattle video."""

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path

from cattle_health_app.repository import SQLiteRepository


ANIMALS = ((1, "DEMO-COW-001"), (2, "DEMO-COW-002"))
PENS = (("01", "DEMO-PEN-01", 4), ("02", "DEMO-PEN-02", 6))


def _validated_job(repository, job_id):
    job = repository.get_video_job(job_id)
    if job.status != "completed" or not job.result or job.result.get("species", "cattle") != "cattle":
        raise ValueError("a completed cattle video job is required")
    if not {track for track, _ in ANIMALS}.issubset(set(job.result.get("track_ids") or [])):
        raise ValueError("two cattle tracks (1 and 2) are required")
    existing = {row["track_id"]: row["animal_id"] for row in repository.list_job_animal_links(job_id)}
    for track, animal in ANIMALS:
        if track in existing and existing[track] != animal:
            raise ValueError(f"track {track} is already linked to another animal")
    return existing


def seed_demo_records(repository, job_id):
    existing = _validated_job(repository, job_id)
    now = datetime.now().astimezone().isoformat(timespec="seconds")
    links_created = 0
    for track, animal in ANIMALS:
        if track not in existing:
            repository.save_animal_link({
                "job_id": job_id, "track_id": track, "animal_id": animal,
                "species": "cattle", "linked_at": now,
            })
            links_created += 1
    checks_created = 0
    for suffix, pen, count in PENS:
        identifier = f"demo-inventory-v1-{job_id}-{suffix}"
        try:
            existing_check = repository.get_inventory_check(identifier)
        except KeyError:
            existing_check = None
        if existing_check:
            if existing_check["job_id"] != job_id or existing_check["pen_id"] != pen:
                raise ValueError(f"inventory ID collision: {identifier}")
            continue
        repository.save_inventory_check({
            "id": identifier, "job_id": job_id, "species": "cattle",
            "pen_id": pen, "expected_count": count,
            "baseline_source": "模拟台账（仅供界面演示，未经现场核实）",
            "observed_count": None, "coverage": "unknown",
            "coverage_note": "模拟数据；未验证圈舍覆盖或实际牛只数量",
            "operator_name": "演示数据", "observed_at": now, "created_at": now,
        })
        checks_created += 1
    return {"animal_links_created": links_created, "inventory_checks_created": checks_created}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--database", type=Path, default=Path("data/agrinebula.db"))
    parser.add_argument("--job-id", required=True)
    parser.add_argument("--apply", action="store_true", help="Back up DB and insert demo records")
    parser.add_argument("--backup", type=Path)
    args = parser.parse_args()
    repository = SQLiteRepository(args.database)
    _validated_job(repository, args.job_id)
    if not args.apply:
        print(json.dumps({"dry_run": True, "job_id": args.job_id,
                          "animals": [animal for _, animal in ANIMALS],
                          "pens": [pen for _, pen, _ in PENS]}, ensure_ascii=False))
        return
    timestamp = datetime.now().astimezone().strftime("%Y%m%d_%H%M%S")
    backup = args.backup or args.database.parent / f"demo_seed_backup_{timestamp}.db"
    backup.parent.mkdir(parents=True, exist_ok=True)
    if backup.exists():
        raise ValueError(f"backup already exists: {backup}")
    with sqlite3.connect(args.database) as source, sqlite3.connect(backup) as target:
        source.backup(target)
    result = seed_demo_records(repository, args.job_id)
    print(json.dumps({**result, "backup": str(backup)}, ensure_ascii=False))


if __name__ == "__main__":
    main()
