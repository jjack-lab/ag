"""Per-track clip buffering and temporally smoothed behavior inference."""

from __future__ import annotations

import math
from collections import OrderedDict, deque
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Optional, Sequence, Union

import numpy as np
import torch
from torch import nn

from .cvb_labels import CVB_LABELS
from .dataset import FRAME_COUNT, evaluation_transform
from .model import DEFAULT_MODEL_VERSION, load_behavior_checkpoint

CLASS_COUNT = len(CVB_LABELS)
UNCERTAIN_LABEL_ID = 1
UNCERTAIN_DISPLAY_NAME = "无法确定"


@dataclass(frozen=True)
class BehaviorPrediction:
    """A JSON-friendly behavior result for one tracked animal."""

    track_id: int
    frame_index: int
    timestamp_seconds: Optional[float]
    label_id: int
    label: str
    display_name: str
    confidence: float
    health_eligible: bool
    raw_label_id: int
    raw_label: str
    raw_confidence: float
    model_version: str


class TrackClipBuffer:
    """Bounded per-track frame buffer with deterministic stride readiness."""

    def __init__(self, clip_frames: int = FRAME_COUNT, stride: int = 4):
        if isinstance(clip_frames, bool) or not isinstance(clip_frames, int) or clip_frames <= 0:
            raise ValueError("clip_frames must be a positive integer")
        if isinstance(stride, bool) or not isinstance(stride, int) or stride <= 0:
            raise ValueError("stride must be a positive integer")
        self.clip_frames = clip_frames
        self.stride = stride
        self._frames = deque(maxlen=clip_frames)
        self._last_frame_index: Optional[int] = None
        self._appended = 0
        self._last_inference_count: Optional[int] = None

    def append(self, frame_index: int, crop: np.ndarray) -> None:
        if isinstance(frame_index, bool) or not isinstance(frame_index, int) or frame_index < 0:
            raise ValueError("frame_index must be a nonnegative integer")
        if self._last_frame_index is not None and frame_index <= self._last_frame_index:
            raise ValueError("frame indexes must be strictly increasing per track")
        if (not isinstance(crop, np.ndarray) or crop.dtype != np.uint8 or crop.ndim != 3 or
                crop.shape[2] != 3 or crop.size == 0):
            raise ValueError("crop must be a non-empty uint8 HxWx3 BGR image")
        self._frames.append(crop.copy())
        self._last_frame_index = frame_index
        self._appended += 1

    @property
    def ready(self) -> bool:
        if len(self._frames) < self.clip_frames:
            return False
        return (self._last_inference_count is None or
                self._appended - self._last_inference_count >= self.stride)

    def clip(self) -> tuple[np.ndarray, ...]:
        if not self.ready:
            raise RuntimeError("track clip is not ready for inference")
        self._last_inference_count = self._appended
        return tuple(self._frames)

    def __len__(self) -> int:
        return len(self._frames)


@dataclass
class _TrackState:
    buffer: TrackClipBuffer
    last_seen_frame: int
    probabilities: Optional[np.ndarray] = None


class TorchBehaviorClassifier:
    """Thin X3D adapter that owns preprocessing and model inference only."""

    def __init__(
        self,
        model: nn.Module,
        device: Union[str, torch.device] = "cpu",
        model_version: str = DEFAULT_MODEL_VERSION,
        input_size: int = 224,
        amp: bool = True,
    ):
        if not isinstance(model, nn.Module):
            raise TypeError("model must be a torch.nn.Module")
        try:
            validated_device = torch.device(device)
        except (TypeError, ValueError, RuntimeError) as exc:
            raise ValueError(f"invalid classifier device: {device!r}") from exc
        if validated_device.type == "cuda" and not torch.cuda.is_available():
            raise RuntimeError("CUDA device requested but CUDA is unavailable")
        if validated_device.type == "cuda" and validated_device.index is not None:
            if validated_device.index >= torch.cuda.device_count():
                raise RuntimeError("requested CUDA device index is unavailable")
        if not isinstance(model_version, str) or not model_version.strip():
            raise ValueError("model_version must be a nonempty string")
        if isinstance(input_size, bool) or not isinstance(input_size, int) or input_size <= 0:
            raise ValueError("input_size must be a positive integer")
        self.device = validated_device
        self.model_version = model_version
        self.input_size = input_size
        self.amp = bool(amp)
        self.model = model.to(self.device).eval()

    @classmethod
    def from_checkpoint(
        cls, path: Union[str, Path], device: Union[str, torch.device] = "cpu", amp: bool = True
    ) -> "TorchBehaviorClassifier":
        loaded = load_behavior_checkpoint(path, device=device)
        return cls(
            loaded.model,
            device=device,
            model_version=loaded.metadata.model_version,
            input_size=loaded.metadata.input_size,
            amp=amp,
        )

    def predict(self, clips: Sequence[Sequence[np.ndarray]]) -> torch.Tensor:
        if not clips:
            return torch.empty((0, CLASS_COUNT), dtype=torch.float32)
        tensors = [evaluation_transform(clip, size=self.input_size) for clip in clips]
        batch = torch.stack(tensors).to(self.device, non_blocking=self.device.type == "cuda")
        with torch.inference_mode():
            with torch.cuda.amp.autocast(enabled=self.amp and self.device.type == "cuda"):
                logits = self.model(batch)
            if not isinstance(logits, torch.Tensor) or logits.shape != (len(clips), CLASS_COUNT):
                raise ValueError(
                    f"behavior model must return shape ({len(clips)}, {CLASS_COUNT})"
                )
            probabilities = torch.softmax(logits.float(), dim=1)
        return probabilities.cpu()


class BehaviorRuntime:
    """Maintain bounded track clips, batch ready tracks, and smooth predictions."""

    def __init__(
        self,
        classifier,
        clip_frames: int = FRAME_COUNT,
        stride: int = 4,
        alpha: float = 0.4,
        confidence_threshold: float = 0.45,
        fps: float = 30.0,
        ttl_frames: Optional[int] = None,
        max_tracks: int = 128,
    ):
        if classifier is None or not callable(getattr(classifier, "predict", None)):
            raise TypeError("classifier must provide predict(clips)")
        if not math.isfinite(alpha) or not 0 < alpha <= 1:
            raise ValueError("alpha must be in (0, 1]")
        if not math.isfinite(confidence_threshold) or not 0 <= confidence_threshold <= 1:
            raise ValueError("confidence_threshold must be in [0, 1]")
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("fps must be finite and positive")
        if ttl_frames is None:
            ttl_frames = max(int(math.ceil(2 * fps)), 32)
        if isinstance(ttl_frames, bool) or not isinstance(ttl_frames, int) or ttl_frames <= 0:
            raise ValueError("ttl_frames must be a positive integer")
        if isinstance(max_tracks, bool) or not isinstance(max_tracks, int) or max_tracks <= 0:
            raise ValueError("max_tracks must be a positive integer")
        # Validate buffer settings once before accepting observations.
        TrackClipBuffer(clip_frames, stride)
        self.classifier = classifier
        self.clip_frames = clip_frames
        self.stride = stride
        self.alpha = float(alpha)
        self.confidence_threshold = float(confidence_threshold)
        self.ttl_frames = ttl_frames
        self.max_tracks = max_tracks
        self.model_version = getattr(classifier, "model_version", "unknown")
        self._tracks: "OrderedDict[int, _TrackState]" = OrderedDict()

    @property
    def active_track_ids(self) -> tuple[int, ...]:
        return tuple(self._tracks)

    @property
    def cached_crop_count(self) -> int:
        return sum(len(state.buffer) for state in self._tracks.values())

    def expire(self, current_frame_index: int) -> tuple[int, ...]:
        if isinstance(current_frame_index, bool) or not isinstance(current_frame_index, int):
            raise ValueError("current_frame_index must be an integer")
        expired = tuple(
            track_id for track_id, state in self._tracks.items()
            if current_frame_index - state.last_seen_frame > self.ttl_frames
        )
        for track_id in expired:
            del self._tracks[track_id]
        return expired

    def _state_for(self, track_id: int, frame_index: int) -> _TrackState:
        if isinstance(track_id, bool) or not isinstance(track_id, int) or track_id < 0:
            raise ValueError("track_id must be a nonnegative integer")
        state = self._tracks.get(track_id)
        if state is None:
            while len(self._tracks) >= self.max_tracks:
                self._tracks.popitem(last=False)
            state = _TrackState(
                TrackClipBuffer(self.clip_frames, self.stride), frame_index
            )
            self._tracks[track_id] = state
        else:
            self._tracks.move_to_end(track_id)
        return state

    def observe(
        self,
        track_id: int,
        frame_index: int,
        crop: np.ndarray,
        timestamp_seconds: Optional[float] = None,
    ) -> Optional[BehaviorPrediction]:
        results = self.observe_batch([(track_id, frame_index, crop, timestamp_seconds)])
        return results[0] if results else None

    def observe_batch(self, observations: Iterable[Sequence[object]]) -> list[BehaviorPrediction]:
        observations = list(observations)
        if not observations:
            return []
        parsed = []
        for observation in observations:
            if len(observation) not in (3, 4):
                raise ValueError("observations must contain track_id, frame_index, crop, [timestamp]")
            track_id, frame_index, crop = observation[:3]
            timestamp = observation[3] if len(observation) == 4 else None
            if timestamp is not None:
                if isinstance(timestamp, bool) or not isinstance(timestamp, (int, float)) or not math.isfinite(timestamp):
                    raise ValueError("timestamp_seconds must be finite or None")
                timestamp = float(timestamp)
            parsed.append((track_id, frame_index, crop, timestamp))
        latest_frame = max(item[1] for item in parsed)
        self.expire(latest_frame)
        ready = []
        metadata = []
        seen_in_batch = set()
        for track_id, frame_index, crop, timestamp in parsed:
            if track_id in seen_in_batch:
                raise ValueError("a track may appear only once per observation batch")
            seen_in_batch.add(track_id)
            state = self._state_for(track_id, frame_index)
            state.buffer.append(frame_index, crop)
            state.last_seen_frame = frame_index
            if state.buffer.ready:
                ready.append(state.buffer.clip())
                metadata.append((track_id, frame_index, timestamp, state))
        if not ready:
            return []
        probabilities = self._validated_probabilities(self.classifier.predict(ready), len(ready))
        return [
            self._prediction(track_id, frame_index, timestamp, state, row)
            for (track_id, frame_index, timestamp, state), row in zip(metadata, probabilities)
        ]

    @staticmethod
    def _validated_probabilities(values, batch_size: int) -> np.ndarray:
        if isinstance(values, torch.Tensor):
            values = values.detach().cpu().numpy()
        try:
            array = np.asarray(values, dtype=np.float64)
        except (TypeError, ValueError) as exc:
            raise ValueError("classifier probabilities must be numeric") from exc
        if array.shape != (batch_size, CLASS_COUNT):
            raise ValueError(f"classifier must return 12 probabilities for each of {batch_size} clips")
        if not np.isfinite(array).all() or (array < 0).any():
            raise ValueError("classifier probabilities must be finite and nonnegative")
        totals = array.sum(axis=1, keepdims=True)
        if (totals <= 0).any():
            raise ValueError("classifier probabilities must have a positive sum")
        return array / totals

    def _prediction(self, track_id, frame_index, timestamp, state, raw) -> BehaviorPrediction:
        raw_label_id = int(np.argmax(raw)) + 1
        raw_confidence = float(raw[raw_label_id - 1])
        if state.probabilities is None:
            state.probabilities = raw.copy()
        else:
            state.probabilities = self.alpha * raw + (1 - self.alpha) * state.probabilities
            state.probabilities /= state.probabilities.sum()
        smoothed_id = int(np.argmax(state.probabilities)) + 1
        confidence = float(state.probabilities[smoothed_id - 1])
        label_id = smoothed_id if confidence >= self.confidence_threshold else UNCERTAIN_LABEL_ID
        label = CVB_LABELS[label_id]
        raw_label = CVB_LABELS[raw_label_id]
        return BehaviorPrediction(
            track_id=track_id,
            frame_index=frame_index,
            timestamp_seconds=timestamp,
            label_id=label_id,
            label=label.name,
            display_name=label.display_name,
            confidence=confidence,
            health_eligible=not label.uncertain,
            raw_label_id=raw_label_id,
            raw_label=raw_label.name,
            raw_confidence=raw_confidence,
            model_version=self.model_version,
        )
