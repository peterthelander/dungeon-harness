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

        errorhandler = route

        def send_static_file(self, filename):
            return filename

    fake_flask.Flask = FakeFlaskApp
    fake_flask.request = SimpleNamespace(files={}, json={}, headers={}, get_json=lambda silent=False: fake_flask.request.json)
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

    def test_validate_remote_url_blocks_mixed_public_and_private_dns_answers(self):
        addresses = [
            (None, None, None, None, ("93.184.216.34", 0)),
            (None, None, None, None, ("127.0.0.1", 0)),
        ]
        with patch.object(socket, "getaddrinfo", return_value=addresses):
            validated_url, error = self.main._validate_remote_url("https://example.com/module.pdf")

        self.assertIsNone(validated_url)
        self.assertEqual(error, "Private or local network addresses are not allowed.")

    def test_open_pinned_response_connects_to_validated_address(self):
        captured = {}

        class FakeResponse:
            status = 200

        class FakeConnection:
            def __init__(self, host, port, address, timeout):
                captured.update(host=host, port=port, address=address, timeout=timeout)

            def request(self, method, target, headers):
                captured.update(method=method, target=target, headers=headers)

            def getresponse(self):
                return FakeResponse()

            def close(self):
                pass

        addresses = [(None, None, None, None, ("93.184.216.34", 0))]
        with (
            patch.object(socket, "getaddrinfo", return_value=addresses),
            patch.object(self.main, "_PinnedHTTPConnection", FakeConnection),
        ):
            connection, response = self.main._open_pinned_response("http://example.com/module.pdf")

        self.assertIsInstance(connection, FakeConnection)
        self.assertIsInstance(response, FakeResponse)
        self.assertEqual(captured["address"], "93.184.216.34")
        self.assertEqual(captured["headers"]["Host"], "example.com")


if __name__ == "__main__":
    unittest.main()
