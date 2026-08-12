import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

from cattle_health_app.media_inference import detect_image, process_video


class FakeBoxes:
    def __len__(self):
        return 2


class FakeResult:
    def __init__(self, frame):
        self.frame = frame
        self.boxes = FakeBoxes()

    def plot(self):
        annotated = self.frame.copy()
        annotated[0:4, 0:4] = (0, 255, 0)
        return annotated


class FakeModel:
    def predict(self, source, **kwargs):
        if isinstance(source, str):
            frame = cv2.imread(source)
        else:
            frame = source
        return [FakeResult(frame)]


class MediaInferenceTests(unittest.TestCase):
    def test_detect_image_returns_annotated_frame_and_count(self):
        with tempfile.TemporaryDirectory() as directory:
            image_path = Path(directory) / "sample.jpg"
            cv2.imwrite(str(image_path), np.zeros((32, 32, 3), dtype=np.uint8))

            result = detect_image(FakeModel(), image_path, conf=0.25, iou=0.45)

            self.assertEqual(2, result.detection_count)
            self.assertEqual((0, 255, 0), tuple(result.annotated_frame[0, 0]))

    def test_process_video_creates_playable_result_in_output_directory(self):
        with tempfile.TemporaryDirectory() as directory:
            source_path = Path(directory) / "source.avi"
            writer = cv2.VideoWriter(
                str(source_path),
                cv2.VideoWriter_fourcc(*"MJPG"),
                12.0,
                (32, 32),
            )
            for _ in range(3):
                writer.write(np.zeros((32, 32, 3), dtype=np.uint8))
            writer.release()

            output_path = process_video(
                FakeModel(),
                source_path,
                Path(directory) / "results",
                conf=0.25,
                iou=0.45,
            )

            capture = cv2.VideoCapture(str(output_path))
            self.assertTrue(output_path.is_file())
            self.assertTrue(capture.isOpened())
            self.assertEqual(3, int(capture.get(cv2.CAP_PROP_FRAME_COUNT)))
            self.assertAlmostEqual(12.0, capture.get(cv2.CAP_PROP_FPS), delta=1.0)
            capture.release()


if __name__ == "__main__":
    unittest.main()
