import importlib
import socket
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def load_main_module():
    fake_flask = types.ModuleType("flask")

    class FakeFlaskApp:
        def __init__(self, *args, **kwargs):
            self.secret_key = None
            self.config = {}

        def route(self, *args, **kwargs):
            def decorator(func):
                return func

            return decorator

        def send_static_file(self, filename):
            return filename

    fake_flask.Flask = FakeFlaskApp
    fake_flask.request = SimpleNamespace(files={}, json={})
    fake_flask.jsonify = lambda payload: payload
    fake_flask.Response = lambda data, mimetype=None: {"data": data, "mimetype": mimetype}
    fake_flask.session = {}

    fake_werkzeug_utils = types.ModuleType("werkzeug.utils")
    fake_werkzeug_utils.secure_filename = lambda name: name

    fake_engine = types.ModuleType("app.engine")
    fake_engine.upload_pdf_and_init = lambda *args, **kwargs: ("", None)
    fake_engine.process_action = lambda *args, **kwargs: iter([])

    sys.modules.pop("app.main", None)
    with patch.dict(
        sys.modules,
        {
            "flask": fake_flask,
            "werkzeug.utils": fake_werkzeug_utils,
            "app.engine": fake_engine,
        },
    ):
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
