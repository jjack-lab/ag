from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> None:
    project_root = Path(__file__).resolve().parents[1]
    if str(project_root) not in sys.path:
        sys.path.insert(0, str(project_root))

    import cv2
    import fastapi
    import torch
    import ultralytics
    import uvicorn

    from cattle_health_app.model_registry import (
        resolve_behavior_model,
        resolve_detector_model,
    )
    from cattle_health_app.yolo_runtime import load_delivery_yolo_class

    artifact = resolve_detector_model(project_root=project_root)
    yolo_class = load_delivery_yolo_class()
    model = yolo_class(str(artifact.path))
    if model is None:
        raise RuntimeError("YOLO11 model failed to load")

    behavior_artifact = resolve_behavior_model(project_root=project_root)
    print(
        json.dumps(
            {
                "status": "ok",
                "python": sys.version.split()[0],
                "opencv": cv2.__version__,
                "torch": torch.__version__,
                "fastapi": fastapi.__version__,
                "uvicorn": uvicorn.__version__,
                "ultralytics": ultralytics.__version__,
                "model_sha256": artifact.sha256,
                "detector_status": "ready",
                "detector_path": str(artifact.path),
                "detector_sha256": artifact.sha256,
                "behavior_status": behavior_artifact.status,
                "behavior_path": str(behavior_artifact.path),
                "behavior_sha256": behavior_artifact.sha256,
                "behavior_error": behavior_artifact.error,
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()
