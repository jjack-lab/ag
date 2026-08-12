import builtins
import unittest
from unittest.mock import patch

from ultralytics.utils.torch_utils import get_cpu_info


class TorchUtilsFallbackTest(unittest.TestCase):
    def test_get_cpu_info_falls_back_when_cpuinfo_missing(self):
        real_import = builtins.__import__

        def import_without_cpuinfo(name, *args, **kwargs):
            if name == "cpuinfo":
                raise ModuleNotFoundError("No module named 'cpuinfo'")
            return real_import(name, *args, **kwargs)

        with patch("builtins.__import__", side_effect=import_without_cpuinfo):
            self.assertEqual("CPU", get_cpu_info())


if __name__ == "__main__":
    unittest.main()
