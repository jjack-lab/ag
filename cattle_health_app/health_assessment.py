"""Join existing cattle rule scores, behavior context, and human reviews."""

from __future__ import annotations


def build_health_assessment(job_id: str, result: dict, reviews: list[dict]) -> dict:
    profiles = {int(row["track_id"]): row for row in result.get("health_evidence", [])}
    behavior_by_track = {}
    for row in result.get("behavior_summary", []):
        behavior_by_track.setdefault(int(row["track_id"]), []).append(row)
    review_by_track = {}
    for row in reviews:
        if row["track_id"] is not None:
            review_by_track.setdefault(int(row["track_id"]), []).append(row)

    track_ids = sorted(set(result.get("track_ids") or []) | set(profiles))
    tracks = []
    for track_id in track_ids:
        profile = profiles.get(track_id, {})
        behaviors = behavior_by_track.get(track_id, [])
        observations = profile.get("observations", [])
        uncertain_seconds = max(
            (float(row.get("uncertain_duration_seconds", 0)) for row in behaviors), default=0,
        )
        if profile.get("risk_score") is None:
            analysis = "该轨迹没有可用的规则评分，请先核查视频与追踪结果。"
        elif observations:
            analysis = f"规则提示：{'、'.join(dict.fromkeys(row['label'] for row in observations))}。"
        else:
            analysis = "本次轨迹未触发规则提示，仍需结合现场观察。"
        if behaviors:
            primary = max(behaviors, key=lambda row: float(row.get("duration_seconds", 0)))
            analysis += f" 行为模型主要记录到{primary['behavior_display_name']} {float(primary['duration_seconds']):.1f} 秒，供回看参考。"
        if uncertain_seconds:
            analysis += f" 其中 {uncertain_seconds:.1f} 秒无法确定，建议查看原视频局部和前后动作。"
        if review_by_track.get(track_id):
            analysis += " 已有人工复核记录，具体判断以复核内容为准。"
        tracks.append({
            "track_id": track_id,
            "risk_score": profile.get("risk_score"),
            "risk_level": profile.get("risk_level", "unavailable"),
            "observations": observations,
            "behaviors": behaviors,
            "uncertain_duration_seconds": uncertain_seconds,
            "reviews": review_by_track.get(track_id, []),
            "analysis": analysis,
        })

    return {
        "job_id": job_id,
        "model": {
            "type": "rule_based",
            "name": "牛只轨迹规则型健康风险筛查",
            "behavior_model_status": result.get("behavior_model_status", "unavailable"),
            "behavior_model_version": result.get("behavior_model_version"),
            "score_basis": "轨迹运动与规则提示；行为摘要仅供旁证，不参与风险分数",
        },
        "summary": {
            "track_count": len(tracks),
            "attention_count": sum(row["risk_level"] in {"low", "medium", "high"} for row in tracks),
            "review_count": len(reviews),
        },
        "tracks": tracks,
    }
