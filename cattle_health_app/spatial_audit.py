"""Human review of per-video spatial events."""

import hashlib
import json


def report_hash(report):
    source = json.dumps(report, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(source).hexdigest()


def new_audit(report):
    return {"report_hash": report_hash(report), "verdicts": {}, "missed": [],
            "coverage_confirmed": False}


def set_verdict(audit, report, event_index, verdict, reviewer, note):
    if not 0 <= event_index < len(report["metrics"]["events"]):
        raise ValueError("事件序号不存在")
    if verdict == "wrong_direction" and report["kind"] != "gate":
        raise ValueError("区域进入事件没有方向")
    audit["verdicts"][str(event_index)] = {"verdict": verdict, "reviewer": reviewer,
                                           "note": note}
    audit["coverage_confirmed"] = False
    return audit


def add_missed(audit, report, time_seconds, direction, reviewer, note):
    audit["missed"].append({"time_seconds": time_seconds, "direction": direction,
                            "reviewer": reviewer, "note": note})
    audit["coverage_confirmed"] = False
    return audit


def audit_summary(audit, report):
    verdicts = [row["verdict"] for row in audit["verdicts"].values()]
    automatic = len(report["metrics"]["events"])
    correct = verdicts.count("correct")
    false_positive = verdicts.count("false_positive")
    wrong_direction = verdicts.count("wrong_direction")
    missed = len(audit["missed"])
    complete = len(verdicts) == automatic and audit["coverage_confirmed"]
    return {"automatic": automatic, "reviewed": len(verdicts), "correct": correct,
            "false_positive": false_positive, "wrong_direction": wrong_direction,
            "missed": missed, "complete": complete,
            "precision": correct / automatic if complete and automatic else None,
            "recall": correct / (correct + wrong_direction + missed)
            if complete and correct + wrong_direction + missed else None}
