import unittest

from inference_profile import build_predict_kwargs, build_track_kwargs


class InferenceProfileTest(unittest.TestCase):
    def test_image_prediction_uses_accuracy_first_settings(self):
        kwargs = build_predict_kwargs(conf=0.35, iou=0.6, class_id=-1, source_type="image")

        self.assertEqual(0.35, kwargs["conf"])
        self.assertEqual(0.6, kwargs["iou"])
        self.assertEqual(960, kwargs["imgsz"])
        self.assertTrue(kwargs["augment"])
        self.assertEqual(500, kwargs["max_det"])
        self.assertNotIn("classes", kwargs)

    def test_video_prediction_keeps_tta_disabled_for_speed(self):
        kwargs = build_predict_kwargs(conf=0.25, iou=0.7, class_id=1, source_type="video")

        self.assertEqual(960, kwargs["imgsz"])
        self.assertFalse(kwargs["augment"])
        self.assertEqual(1, kwargs["classes"])

    def test_tracking_uses_higher_resolution_without_tta(self):
        kwargs = build_track_kwargs(conf=0.4, iou=0.65, class_id=1)

        self.assertEqual(0.4, kwargs["conf"])
        self.assertEqual(0.65, kwargs["iou"])
        self.assertEqual(960, kwargs["imgsz"])
        self.assertFalse(kwargs["augment"])
        self.assertFalse(kwargs["show"])
        self.assertEqual(1, kwargs["classes"])


if __name__ == "__main__":
    unittest.main()
