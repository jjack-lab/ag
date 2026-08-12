from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum


class AlertLevel(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


@dataclass(frozen=True)
class AlertRecord:
    id: str
    cattle_id: str
    risk_type: str
    level: AlertLevel
    reason: str
    suggestion: str
    occurred_at: str
    confidence: float
    evidence_path: str | None = None
    status: str = "open"
    resolution: str | None = None
    resolved_at: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class VideoJobRecord:
    id: str
    source_path: str
    status: str
    progress: float
    created_at: str
    updated_at: str
    result: dict | None = None
    error: str | None = None

    def to_dict(self) -> dict:
        return asdict(self)
