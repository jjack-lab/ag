"""Batch inference over virtual external clips while preserving raw logits."""

from dataclasses import replace
import math
from pathlib import Path
from typing import Callable, Iterable, Optional, Sequence, Tuple

import numpy as np
import torch

from cattle_health_app.behavior.cross_domain_experiment import ExternalPrediction
from cattle_health_app.behavior.dataset import evaluation_transform
from cattle_health_app.behavior.external_video_dataset import (
    ExternalVideoSample,
    decode_virtual_clip,
    measure_virtual_clip_quality,
)
from cattle_health_app.behavior.model import load_behavior_checkpoint


CLASS_COUNT = 12


class ExternalInferenceError(RuntimeError):
    pass


class FrozenX3DLogitPredictor:
    """Load the frozen checkpoint once and return pre-softmax 12-class logits."""

    def __init__(self, checkpoint_path, *, device="cuda", amp=True):
        loaded = load_behavior_checkpoint(checkpoint_path, device=device)
        self.device = torch.device(device)
        self.model = loaded.model.to(self.device).eval()
        self.input_size = loaded.metadata.input_size
        self.model_version = loaded.metadata.model_version
        self.amp = bool(amp)

    def __call__(self, clips: Sequence[Sequence[np.ndarray]]) -> np.ndarray:
        if not clips:
            return np.empty((0, CLASS_COUNT), dtype=np.float64)
        tensors = [evaluation_transform(clip, size=self.input_size) for clip in clips]
        batch = torch.stack(tensors).to(
            self.device, non_blocking=self.device.type == "cuda"
        )
        with torch.inference_mode():
            with torch.cuda.amp.autocast(
                enabled=self.amp and self.device.type == "cuda"
            ):
                logits = self.model(batch)
        if not isinstance(logits, torch.Tensor):
            raise ExternalInferenceError("behavior model did not return a tensor")
        return logits.detach().float().cpu().numpy().astype(np.float64, copy=False)


def collect_external_predictions(
    samples: Iterable[ExternalVideoSample],
    project_root,
    *,
    predictor: Callable[[Sequence[Sequence[np.ndarray]]], np.ndarray],
    batch_size: int = 4,
    frame_transform: Optional[
        Callable[[Tuple[np.ndarray, ...], ExternalVideoSample], Sequence[np.ndarray]]
    ] = None,
    progress: Optional[Callable[[int, int], None]] = None,
) -> Tuple[ExternalPrediction, ...]:
    """Decode, optionally corrupt, infer, and attach measured quality evidence."""

    rows = tuple(samples)
    if not rows:
        raise ExternalInferenceError("external samples must not be empty")
    if isinstance(batch_size, bool) or not isinstance(batch_size, int) or batch_size <= 0:
        raise ExternalInferenceError("batch_size must be a positive integer")
    root = Path(project_root).expanduser().resolve()
    output = []
    for offset in range(0, len(rows), batch_size):
        selected = rows[offset : offset + batch_size]
        decoded_rows = []
        for sample in selected:
            decoded = decode_virtual_clip(sample, root)
            if frame_transform is not None:
                transformed = tuple(frame_transform(decoded.frames, sample))
                if len(transformed) != len(decoded.frames):
                    raise ExternalInferenceError(
                        "frame_transform must preserve the model frame count"
                    )
                decoded = replace(decoded, frames=transformed)
            decoded_rows.append(decoded)
        try:
            logits = np.asarray(
                predictor([decoded.frames for decoded in decoded_rows]),
                dtype=np.float64,
            )
        except ExternalInferenceError:
            raise
        except Exception as exc:
            raise ExternalInferenceError("external predictor failed: {}".format(exc)) from exc
        if logits.shape != (len(decoded_rows), CLASS_COUNT):
            raise ExternalInferenceError(
                "external predictor must return shape ({}, {})".format(
                    len(decoded_rows), CLASS_COUNT
                )
            )
        if not np.isfinite(logits).all():
            raise ExternalInferenceError("external predictor logits must be finite")
        for decoded, logit_row in zip(decoded_rows, logits):
            evidence = dict(measure_virtual_clip_quality(decoded))
            if any(
                isinstance(value, bool)
                or not isinstance(value, (int, float))
                or not math.isfinite(float(value))
                for value in evidence.values()
            ):
                raise ExternalInferenceError("quality evidence must be finite numeric values")
            output.append(
                ExternalPrediction(
                    sample_id=decoded.sample.sample_id,
                    mapping_tier=decoded.sample.mapping_tier,
                    true_label=decoded.label_id,
                    logits=tuple(float(value) for value in logit_row),
                    quality_features=evidence,
                )
            )
        if progress:
            progress(len(output), len(rows))
    return tuple(output)
