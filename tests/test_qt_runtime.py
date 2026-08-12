import os
import unittest
from pathlib import Path

from qt_runtime import configure_qt_platform_plugin


class QtRuntimeTests(unittest.TestCase):
    def test_configures_existing_windows_platform_plugin_directory(self):
        previous = os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
        try:
            plugin_dir = Path(configure_qt_platform_plugin())
            self.assertTrue((plugin_dir / "qwindows.dll").is_file())
            self.assertEqual(str(plugin_dir), os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"])
        finally:
            if previous is None:
                os.environ.pop("QT_QPA_PLATFORM_PLUGIN_PATH", None)
            else:
                os.environ["QT_QPA_PLATFORM_PLUGIN_PATH"] = previous


if __name__ == "__main__":
    unittest.main()
