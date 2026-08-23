from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
import stat
from typing import Callable, Iterable, Mapping, Optional, Tuple
import zipfile

import requests

from cattle_health_app.behavior.external_registry import DatasetRecord


class AcquisitionError(RuntimeError):
    pass


class DownloadBlocked(AcquisitionError):
    pass


class UnsafeArchive(AcquisitionError):
    pass


@dataclass(frozen=True)
class RemoteFileSpec:
    relative_path: str
    url: str
    expected_size: Optional[int]
    sha256: Optional[str]


@dataclass(frozen=True)
class AcquisitionResult:
    path: Path
    size: int
    sha256: str
    reused: bool


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        while True:
            chunk = handle.read(chunk_size)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root: Path, relative_path: str) -> Path:
    raw = Path(relative_path)
    if raw.is_absolute() or not relative_path.strip():
        raise AcquisitionError("relative_path must stay inside dataset storage root")
    resolved_root = Path(root).resolve()
    candidate = (resolved_root / raw).resolve()
    try:
        candidate.relative_to(resolved_root)
    except ValueError as exc:
        raise AcquisitionError("relative_path must stay inside dataset storage root") from exc
    return candidate


def _storage_bytes(root: Path, excluded: Tuple[Path, ...] = ()) -> int:
    if not root.exists():
        return 0
    excluded_resolved = {path.resolve() for path in excluded}
    total = 0
    for path in root.rglob("*"):
        if path.is_file() and path.resolve() not in excluded_resolved:
            total += path.stat().st_size
    return total


def _default_opener(url: str) -> Iterable[bytes]:
    with requests.get(url, stream=True, timeout=(15, 120)) as response:
        response.raise_for_status()
        for chunk in response.iter_content(chunk_size=1024 * 1024):
            if chunk:
                yield chunk


def _validate_spec(spec: RemoteFileSpec) -> None:
    if spec.expected_size is not None:
        if (
            isinstance(spec.expected_size, bool)
            or not isinstance(spec.expected_size, int)
            or spec.expected_size < 0
        ):
            raise AcquisitionError("expected_size must be a non-negative integer or null")
    if spec.sha256 is not None:
        value = spec.sha256.lower()
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise AcquisitionError("sha256 must be 64 lowercase hexadecimal characters")


def acquire_file(
    record: DatasetRecord,
    spec: RemoteFileSpec,
    opener: Optional[Callable[[str], Iterable[bytes]]] = None,
) -> AcquisitionResult:
    _validate_spec(spec)
    if record.license_status != "verified":
        raise DownloadBlocked(
            "download blocked because dataset license is not verified: {}".format(
                record.license_status
            )
        )
    destination = _inside(record.storage_root, spec.relative_path)
    partial = destination.with_name(destination.name + ".part")
    if destination.exists():
        size = destination.stat().st_size
        digest = sha256_file(destination)
        if spec.expected_size is not None and size != spec.expected_size:
            raise AcquisitionError("existing file size does not match expected_size")
        if spec.sha256 is not None and digest != spec.sha256.lower():
            raise AcquisitionError("existing file SHA-256 does not match expected value")
        return AcquisitionResult(destination, size, digest, True)

    used = _storage_bytes(record.storage_root, excluded=(partial,))
    remaining = record.max_download_bytes - used
    if remaining < 0:
        raise DownloadBlocked("existing dataset files already exceed download budget")
    if spec.expected_size is not None and spec.expected_size > remaining:
        raise DownloadBlocked("declared file size exceeds remaining download budget")

    destination.parent.mkdir(parents=True, exist_ok=True)
    partial.unlink(missing_ok=True)
    size = 0
    digest = hashlib.sha256()
    stream_opener = opener or _default_opener
    try:
        with partial.open("wb") as handle:
            for chunk in stream_opener(spec.url):
                if not isinstance(chunk, (bytes, bytearray)):
                    raise AcquisitionError("download stream yielded a non-bytes chunk")
                if not chunk:
                    continue
                size += len(chunk)
                if size > remaining:
                    raise DownloadBlocked("download stream exceeded remaining budget")
                handle.write(chunk)
                digest.update(chunk)
        if spec.expected_size is not None and size != spec.expected_size:
            raise AcquisitionError("downloaded size does not match expected_size")
        actual_hash = digest.hexdigest()
        if spec.sha256 is not None and actual_hash != spec.sha256.lower():
            raise AcquisitionError("downloaded file SHA-256 does not match expected value")
        partial.replace(destination)
        return AcquisitionResult(destination, size, actual_hash, False)
    except Exception:
        partial.unlink(missing_ok=True)
        raise


def safe_extract_zip(archive: Path, output_root: Path) -> Tuple[Path, ...]:
    archive_path = Path(archive)
    root = Path(output_root).resolve()
    planned = []
    try:
        with zipfile.ZipFile(str(archive_path), "r") as handle:
            for info in handle.infolist():
                member = Path(info.filename)
                target = (root / member).resolve()
                try:
                    target.relative_to(root)
                except ValueError as exc:
                    raise UnsafeArchive(
                        "archive member resolves outside extraction root: {}".format(
                            info.filename
                        )
                    ) from exc
                unix_mode = (info.external_attr >> 16) & 0o170000
                if member.is_absolute() or ".." in member.parts or unix_mode == stat.S_IFLNK:
                    raise UnsafeArchive(
                        "archive member resolves outside extraction root: {}".format(
                            info.filename
                        )
                    )
                planned.append((info, target))
            extracted = []
            for info, target in planned:
                if info.is_dir():
                    target.mkdir(parents=True, exist_ok=True)
                    continue
                target.parent.mkdir(parents=True, exist_ok=True)
                with handle.open(info, "r") as source, target.open("wb") as destination:
                    while True:
                        chunk = source.read(1024 * 1024)
                        if not chunk:
                            break
                        destination.write(chunk)
                extracted.append(target)
            return tuple(extracted)
    except zipfile.BadZipFile as exc:
        raise UnsafeArchive("invalid ZIP archive: {}".format(archive_path)) from exc


def append_operation(path: Path, operation: Mapping[str, object]) -> None:
    if not isinstance(operation, Mapping):
        raise AcquisitionError("operation must be a mapping")
    try:
        line = json.dumps(dict(operation), ensure_ascii=False, sort_keys=True)
    except (TypeError, ValueError) as exc:
        raise AcquisitionError("operation must be JSON serializable") from exc
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8", newline="\n") as handle:
        handle.write(line + "\n")
