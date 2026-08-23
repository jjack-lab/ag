from dataclasses import dataclass
import json
from pathlib import Path
from types import MappingProxyType
from typing import Mapping
from urllib.parse import urlparse


SCHEMA_VERSION = 1
LICENSE_STATUSES = frozenset(
    {"verified", "verify_before_download", "blocked_license", "not_used"}
)
RECORD_FIELDS = frozenset(
    {
        "dataset_id",
        "name",
        "version",
        "official_url",
        "access_url",
        "license_name",
        "license_url",
        "license_status",
        "intended_use",
        "storage_root",
        "max_download_bytes",
    }
)


class RegistryError(ValueError):
    pass


@dataclass(frozen=True)
class DatasetRecord:
    dataset_id: str
    name: str
    version: str
    official_url: str
    access_url: str
    license_name: str
    license_url: str
    license_status: str
    intended_use: str
    storage_root: Path
    max_download_bytes: int


class DatasetRegistry:
    def __init__(self, records: Mapping[str, DatasetRecord]):
        self._records = MappingProxyType(dict(records))

    @property
    def records(self) -> Mapping[str, DatasetRecord]:
        return self._records

    def require(self, dataset_id: str) -> DatasetRecord:
        try:
            return self._records[dataset_id]
        except KeyError as exc:
            raise RegistryError("unknown dataset_id: {}".format(dataset_id)) from exc


def _required_text(raw, field: str, row_number: int) -> str:
    value = raw.get(field)
    if not isinstance(value, str) or not value.strip():
        raise RegistryError("datasets[{}].{} must be non-empty text".format(row_number, field))
    return value.strip()


def _url(raw, field: str, row_number: int, required: bool = True) -> str:
    value = raw.get(field)
    if value == "" and not required:
        return ""
    if not isinstance(value, str):
        raise RegistryError("datasets[{}].{} must be a URL".format(row_number, field))
    parsed = urlparse(value)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise RegistryError("datasets[{}].{} must be an HTTP(S) URL".format(row_number, field))
    return value


def _storage_root(raw_value, project_root: Path, row_number: int) -> Path:
    if not isinstance(raw_value, str) or not raw_value.strip():
        raise RegistryError("datasets[{}].storage_root must be non-empty text".format(row_number))
    raw_path = Path(raw_value)
    candidate = raw_path if raw_path.is_absolute() else project_root / raw_path
    root = project_root.resolve()
    resolved = candidate.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise RegistryError(
            "datasets[{}].storage_root must resolve inside project_root".format(row_number)
        ) from exc
    return resolved


def _parse_record(raw, project_root: Path, row_number: int) -> DatasetRecord:
    if not isinstance(raw, dict) or set(raw) != RECORD_FIELDS:
        actual = set(raw) if isinstance(raw, dict) else set()
        raise RegistryError(
            "datasets[{}] fields mismatch: missing={}, extra={}".format(
                row_number, sorted(RECORD_FIELDS - actual), sorted(actual - RECORD_FIELDS)
            )
        )
    status = _required_text(raw, "license_status", row_number)
    if status not in LICENSE_STATUSES:
        raise RegistryError(
            "datasets[{}].license_status must be one of {}".format(
                row_number, sorted(LICENSE_STATUSES)
            )
        )
    budget = raw["max_download_bytes"]
    if isinstance(budget, bool) or not isinstance(budget, int) or budget <= 0:
        raise RegistryError(
            "datasets[{}].max_download_bytes must be a positive integer".format(row_number)
        )
    license_name = _required_text(raw, "license_name", row_number)
    license_url = _url(
        raw, "license_url", row_number, required=status == "verified"
    )
    return DatasetRecord(
        dataset_id=_required_text(raw, "dataset_id", row_number),
        name=_required_text(raw, "name", row_number),
        version=_required_text(raw, "version", row_number),
        official_url=_url(raw, "official_url", row_number),
        access_url=_url(raw, "access_url", row_number),
        license_name=license_name,
        license_url=license_url,
        license_status=status,
        intended_use=_required_text(raw, "intended_use", row_number),
        storage_root=_storage_root(raw["storage_root"], project_root, row_number),
        max_download_bytes=budget,
    )


def load_registry(path: Path, project_root: Path) -> DatasetRegistry:
    registry_path = Path(path)
    root = Path(project_root)
    try:
        payload = json.loads(registry_path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise RegistryError("cannot read registry {}: {}".format(registry_path, exc)) from exc
    if not isinstance(payload, dict) or set(payload) != {"schema_version", "datasets"}:
        raise RegistryError("registry fields must be exactly schema_version and datasets")
    if payload["schema_version"] != SCHEMA_VERSION:
        raise RegistryError("unsupported registry schema_version")
    if not isinstance(payload["datasets"], list):
        raise RegistryError("datasets must be a list")
    records = {}
    for index, raw in enumerate(payload["datasets"]):
        record = _parse_record(raw, root, index)
        if record.dataset_id in records:
            raise RegistryError("duplicate dataset_id: {}".format(record.dataset_id))
        records[record.dataset_id] = record
    return DatasetRegistry(records)
