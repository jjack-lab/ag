import unittest
from unittest.mock import patch

from ultralytics.nn import tasks


class TorchSafeLoadCompatTest(unittest.TestCase):
    def test_uses_legacy_checkpoint_loading_for_trusted_local_weights(self):
        with patch.object(tasks, "check_suffix"), patch(
            "ultralytics.utils.downloads.attempt_download_asset", return_value="best.pt"
        ), patch.object(tasks.torch, "load", return_value={"model": object()}) as torch_load:
            loaded, weight = tasks.torch_safe_load("best.pt")

        self.assertIn("model", loaded)
        self.assertEqual("best.pt", weight)
        self.assertEqual(False, torch_load.call_args.kwargs["weights_only"])


if __name__ == "__main__":
    unittest.main()
