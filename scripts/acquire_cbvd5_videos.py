"""Resumable, budgeted acquisition of the approved CBVD-5 v11 video directory."""

import argparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import asdict, dataclass
import hashlib
import json
from pathlib import Path
from typing import Callable, Iterable, Mapping, Optional, Sequence, Tuple


DATASET_HANDLE = "fandaoerji/cbvd-5cow-behavior-video-dataset/versions/11"
DATASET_ID = "cbvd5"
DATASET_VERSION = 11
VIDEO_DIRECTORY = "videos/videos"
EXPECTED_VIDEO_COUNT = 687
EXPECTED_VIDEO_BYTES = 3480105107
DOWNLOAD_BUDGET_BYTES = 5368709120


class VideoAcquisitionError(RuntimeError):
    pass


@dataclass(frozen=True)
class VideoInventoryEntry:
    relative_path: str
    size: int


@dataclass(frozen=True)
class AcquiredVideo:
    relative_path: str
    local_path: str
    size: int
    sha256: str
    reused: bool


def _safe_relative_path(value: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise VideoAcquisitionError("video path must stay inside the dataset root")
    normalized = value.replace("\\", "/")
    path = Path(normalized)
    if path.is_absolute() or ".." in path.parts or not normalized.startswith(VIDEO_DIRECTORY + "/"):
        raise VideoAcquisitionError("video path must stay inside the approved directory")
    if path.suffix.lower() != ".mp4":
        raise VideoAcquisitionError("approved video inventory may contain only MP4 files")
    return normalized


def validate_inventory(
    rows: Iterable[Mapping[str, object]], expected_count: int, expected_bytes: int
) -> Tuple[VideoInventoryEntry, ...]:
    entries = []
    paths = set()
    for row in rows:
        if not isinstance(row, Mapping):
            raise VideoAcquisitionError("inventory rows must be mappings")
        relative_path = _safe_relative_path(row.get("path"))
        size = row.get("bytes")
        if isinstance(size, bool) or not isinstance(size, int) or size <= 0:
            raise VideoAcquisitionError("video bytes must be a positive integer")
        if relative_path in paths:
            raise VideoAcquisitionError("official inventory contains duplicate paths")
        paths.add(relative_path)
        entries.append(VideoInventoryEntry(relative_path, size))
    entries.sort(key=lambda item: item.relative_path)
    if len(entries) != expected_count:
        raise VideoAcquisitionError(
            "official video count mismatch: expected {}, got {}".format(
                expected_count, len(entries)
            )
        )
    total = sum(entry.size for entry in entries)
    if total != expected_bytes:
        raise VideoAcquisitionError(
            "official video total bytes mismatch: expected {}, got {}".format(
                expected_bytes, total
            )
        )
    return tuple(entries)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _other_storage_bytes(storage_root: Path, destinations: Sequence[Path]) -> int:
    if not storage_root.exists():
        return 0
    targets = {path.resolve() for path in destinations}
    return sum(
        path.stat().st_size
        for path in storage_root.rglob("*")
        if path.is_file() and path.resolve() not in targets
    )


def acquire_inventory(
    entries: Sequence[VideoInventoryEntry],
    storage_root: Path,
    max_download_bytes: int,
    downloader: Callable[[VideoInventoryEntry, Path], None],
    *,
    workers: int = 1,
    progress: Optional[Callable[[int, int, AcquiredVideo], None]] = None,
) -> Tuple[AcquiredVideo, ...]:
    if isinstance(max_download_bytes, bool) or not isinstance(max_download_bytes, int) or max_download_bytes <= 0:
        raise VideoAcquisitionError("download budget must be a positive integer")
    if isinstance(workers, bool) or not isinstance(workers, int) or workers <= 0:
        raise VideoAcquisitionError("workers must be a positive integer")
    root = Path(storage_root).expanduser().resolve()
    destinations = [(root / "raw" / Path(entry.relative_path)).resolve() for entry in entries]
    for destination in destinations:
        try:
            destination.relative_to(root)
        except ValueError as exc:
            raise VideoAcquisitionError("video destination must stay inside storage root") from exc
    planned_total = _other_storage_bytes(root, destinations) + sum(entry.size for entry in entries)
    if planned_total > max_download_bytes:
        raise VideoAcquisitionError(
            "approved files exceed download budget: {} > {}".format(
                planned_total, max_download_bytes
            )
        )

    def acquire_one(index):
        entry = entries[index]
        destination = destinations[index]
        reused = destination.is_file()
        if reused:
            if destination.stat().st_size != entry.size:
                raise VideoAcquisitionError(
                    "existing video size mismatch: {}".format(entry.relative_path)
                )
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            downloader(entry, destination)
            if not destination.is_file():
                raise VideoAcquisitionError(
                    "downloader did not create {}".format(entry.relative_path)
                )
            if destination.stat().st_size != entry.size:
                raise VideoAcquisitionError(
                    "downloaded video size mismatch: {}".format(entry.relative_path)
                )
        return AcquiredVideo(
            relative_path=entry.relative_path,
            local_path=destination.relative_to(root).as_posix(),
            size=destination.stat().st_size,
            sha256=_sha256(destination),
            reused=reused,
        )

    results = [None] * len(entries)
    completed = 0
    if workers == 1:
        for index in range(len(entries)):
            result = acquire_one(index)
            results[index] = result
            completed += 1
            if progress:
                progress(completed, len(entries), result)
    else:
        with ThreadPoolExecutor(max_workers=workers) as executor:
            futures = {executor.submit(acquire_one, index): index for index in range(len(entries))}
            for future in as_completed(futures):
                index = futures[future]
                result = future.result()
                results[index] = result
                completed += 1
                if progress:
                    progress(completed, len(entries), result)
    return tuple(results)


def list_official_inventory() -> Tuple[VideoInventoryEntry, ...]:
    """Read the official paginated tree through Kaggle's supported SDK."""

    try:
        from kagglehub.clients import build_kaggle_client
        from kagglesdk.datasets.types.dataset_api_service import (
            ApiListTreeDatasetFilesRequest,
        )
    except ImportError as exc:
        raise VideoAcquisitionError(
            "kagglehub is required for official inventory access"
        ) from exc
    raw_rows = []
    page_token = None
    seen_tokens = set()
    with build_kaggle_client() as client:
        while True:
            request = ApiListTreeDatasetFilesRequest()
            request.owner_slug = "fandaoerji"
            request.dataset_slug = "cbvd-5cow-behavior-video-dataset"
            request.dataset_version_number = DATASET_VERSION
            request.path = VIDEO_DIRECTORY
            request.page_size = 1000
            if page_token:
                request.page_token = page_token
            response = client.datasets.dataset_api_client.list_tree_dataset_files(request)
            for item in response.files:
                raw_rows.append(
                    {"path": item.relative_url, "bytes": int(item.total_bytes)}
                )
            page_token = response.next_page_token or None
            if not page_token:
                break
            if page_token in seen_tokens:
                raise VideoAcquisitionError("official inventory repeated a page token")
            seen_tokens.add(page_token)
    return validate_inventory(raw_rows, EXPECTED_VIDEO_COUNT, EXPECTED_VIDEO_BYTES)


def _kaggle_downloader(storage_root: Path):
    try:
        import kagglehub
    except ImportError as exc:
        raise VideoAcquisitionError("kagglehub is required for downloads") from exc
    output_root = storage_root / "raw"

    def download(entry: VideoInventoryEntry, destination: Path) -> None:
        resolved = kagglehub.dataset_download(
            DATASET_HANDLE,
            path=entry.relative_path,
            output_dir=str(output_root),
        )
        if Path(resolved).resolve() != destination:
            raise VideoAcquisitionError("KaggleHub returned an unexpected destination")

    return download


def _write_json(path: Path, payload) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )
    temporary.replace(path)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--project-root", default=str(Path(__file__).resolve().parents[1]))
    parser.add_argument("--storage-root", default="data/external/cbvd5")
    parser.add_argument("--workers", type=int, default=1)
    return parser


def main(argv=None) -> int:
    args = build_parser().parse_args(argv)
    project_root = Path(args.project_root).expanduser().resolve()
    raw_storage = Path(args.storage_root)
    storage_root = (
        raw_storage.resolve()
        if raw_storage.is_absolute()
        else (project_root / raw_storage).resolve()
    )
    try:
        storage_root.relative_to(project_root)
    except ValueError as exc:
        raise VideoAcquisitionError("storage_root must stay inside project_root") from exc
    entries = list_official_inventory()
    manifest_root = storage_root / "manifests"
    _write_json(
        manifest_root / "official_video_inventory_v11.json",
        {
            "dataset_id": DATASET_ID,
            "dataset_version": DATASET_VERSION,
            "official_handle": DATASET_HANDLE,
            "directory": VIDEO_DIRECTORY,
            "file_count": len(entries),
            "total_bytes": sum(entry.size for entry in entries),
            "files": [
                {"path": entry.relative_path, "bytes": entry.size} for entry in entries
            ],
        },
    )

    def progress(done, total, result):
        if done == 1 or done % 10 == 0 or done == total:
            print(
                "completed {}/{}: {} ({} bytes)".format(
                    done, total, result.relative_path, result.size
                ),
                flush=True,
            )

    results = acquire_inventory(
        entries,
        storage_root,
        DOWNLOAD_BUDGET_BYTES,
        _kaggle_downloader(storage_root),
        workers=args.workers,
        progress=progress,
    )
    _write_json(
        manifest_root / "acquired_video_files_v11.json",
        {
            "dataset_id": DATASET_ID,
            "dataset_version": DATASET_VERSION,
            "file_count": len(results),
            "total_bytes": sum(result.size for result in results),
            "reused_count": sum(result.reused for result in results),
            "files": [asdict(result) for result in results],
        },
    )
    print(
        json.dumps(
            {
                "status": "complete",
                "file_count": len(results),
                "total_bytes": sum(result.size for result in results),
                "reused_count": sum(result.reused for result in results),
            },
            sort_keys=True,
        ),
        flush=True,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
