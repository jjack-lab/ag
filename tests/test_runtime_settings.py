import os
import unittest
from unittest import mock

from cattle_health_app.runtime import DEFAULT_HOST, DEFAULT_PORT, server_host, server_port


class RuntimeSettingsTests(unittest.TestCase):
    def test_defaults_to_loopback(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            self.assertEqual("127.0.0.1", DEFAULT_HOST)
            self.assertEqual("127.0.0.1", server_host())
            self.assertEqual(DEFAULT_PORT, server_port())

    def test_environment_overrides(self):
        with mock.patch.dict(
            os.environ,
            {"AGRINEBULA_HOST": "0.0.0.0", "AGRINEBULA_PORT": "8001"},
        ):
            self.assertEqual("0.0.0.0", server_host())
            self.assertEqual(8001, server_port())

    def test_blank_values_fall_back(self):
        with mock.patch.dict(
            os.environ, {"AGRINEBULA_HOST": "  ", "AGRINEBULA_PORT": " "}
        ):
            self.assertEqual("127.0.0.1", server_host())
            self.assertEqual(8000, server_port())

    def test_invalid_port_is_rejected(self):
        with mock.patch.dict(os.environ, {"AGRINEBULA_PORT": "abc"}):
            with self.assertRaises(ValueError):
                server_port()
        with mock.patch.dict(os.environ, {"AGRINEBULA_PORT": "70000"}):
            with self.assertRaises(ValueError):
                server_port()


if __name__ == "__main__":
    unittest.main()
