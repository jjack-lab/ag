"""Status rules for human pen inventory reconciliation."""

from __future__ import annotations


def inventory_state(check: dict, latest_recheck: dict | None) -> dict:
    current_count = (
        latest_recheck["counted_count"] if latest_recheck is not None
        else check["observed_count"]
    )
    difference = (
        check["expected_count"] - current_count if current_count is not None else None
    )
    if check["coverage"] != "complete":
        status = "coverage_needed"
    elif latest_recheck is not None:
        status = {
            "resolved": "verified_match",
            "shortfall_pending": "shortfall_pending",
            "surplus_pending": "surplus_pending",
            "loss_user_recorded": "loss_user_recorded",
        }[latest_recheck["outcome"]]
    elif current_count is None:
        status = "count_needed"
    elif difference == 0:
        status = "preliminary_match"
    else:
        status = "discrepancy_pending"
    return {"status": status, "difference": difference, "current_count": current_count}


def validate_recheck(check: dict, recheck: dict) -> None:
    if check["coverage"] != "complete":
        raise ValueError("拍摄覆盖不完整，需先补拍并建立新盘点")
    if check["observed_count"] is None:
        raise ValueError("需先完成首次人工清点，之后才能提交复核")
    difference = check["expected_count"] - recheck["counted_count"]
    outcome = recheck["outcome"]
    lost_count = recheck.get("lost_count")
    if outcome == "resolved":
        valid = difference == 0 and lost_count is None
    elif outcome == "shortfall_pending":
        valid = difference > 0 and lost_count is None
    elif outcome == "surplus_pending":
        valid = difference < 0 and lost_count is None
    elif outcome == "loss_user_recorded":
        valid = (
            difference > 0
            and isinstance(lost_count, int)
            and not isinstance(lost_count, bool)
            and 1 <= lost_count <= difference
            and recheck["movement_records_checked"]
            and recheck["field_search_complete"]
        )
    else:
        valid = False
    if not valid:
        raise ValueError("复核结论与数量或现场核查证据不符")
