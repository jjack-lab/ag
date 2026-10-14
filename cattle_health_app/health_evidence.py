"""Build a traceable, rule-based health evidence view for cattle video tracks."""

ALERT_LABELS = {
    "still": "持续低活动",
    "lying": "疑似长时间卧倒",
    "isolated": "持续离群",
    "activity_drop": "活动量下降",
    "zone_dwell": "采食或饮水区停留异常",
}


def build_health_evidence(summaries, alerts, low_activity_threshold=5.0):
    """Link each cattle track's rule observations to its existing risk score."""
    by_track = {}
    for alert in alerts:
        by_track.setdefault(alert.track_id, []).append({
            "type": alert.alert_type,
            "label": ALERT_LABELS.get(alert.alert_type, alert.alert_type),
            "time_seconds": alert.time_seconds,
            "confidence": alert.confidence,
            "detail": alert.detail,
            "suggestion": alert.suggestion,
        })
    profiles = []
    for summary in summaries:
        observations = list(by_track.get(summary.track_id, []))
        if (not observations and summary.risk_score >= 15
                and summary.average_speed_px_s <= low_activity_threshold):
            observations.append({
                "type": "low_average_speed",
                "label": "全视频平均活动速度偏低",
                "time_seconds": None,
                "confidence": None,
                "detail": f"平均速度 {summary.average_speed_px_s:.1f} px/s",
                "suggestion": "建议人工复核活动状态",
            })
        profiles.append({
            "track_id": summary.track_id,
            "risk_score": summary.risk_score,
            "risk_level": summary.risk_level,
            "observations": observations,
        })
    return profiles
