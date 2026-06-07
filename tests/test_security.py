import importlib
import socket
import sys
import types
import unittest
from unittest.mock import patch


def load_main_module():
    fake_engine = types.ModuleType("app.engine")
    fake_engine.upload_pdf_and_init = lambda *args, **kwargs: ("", None)
    fake_engine.process_action = lambda *args, **kwargs: iter([])

    sys.modules.pop("app.main", None)
    with patch.dict(sys.modules, {"app.engine": fake_engine}):
        main = importlib.import_module("app.main")
        return importlib.reload(main)


class SecurityValidationTests(unittest.TestCase):
    def setUp(self):
        self.main = load_main_module()

    def test_validate_remote_url_allows_clean_public_url(self):
        with patch.object(socket, "getaddrinfo", return_value=[(None, None, None, None, ("93.184.216.34", 0))]):
            validated_url, error = self.main._validate_remote_url("https://trilemma.com/module.pdf")

        self.assertEqual(validated_url, "https://trilemma.com/module.pdf")
        self.assertIsNone(error)

    def test_is_private_host_blocks_localhost_resolution(self):
        with patch.object(socket, "getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
            self.assertTrue(self.main._is_private_host("localhost"))

    def test_validate_remote_url_blocks_loopback_address(self):
        with patch.object(socket, "getaddrinfo", return_value=[(None, None, None, None, ("127.0.0.1", 0))]):
            validated_url, error = self.main._validate_remote_url("http://127.0.0.1")

        self.assertIsNone(validated_url)
        self.assertEqual(error, "Private or local network addresses are not allowed.")


if __name__ == "__main__":
    unittest.main()
