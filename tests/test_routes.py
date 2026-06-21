import importlib
import json
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import patch


def load_main_module(process_action_impl=None):
    fake_flask = types.ModuleType("flask")

    class FakeJsonResponse(dict):
        def __init__(self, payload):
            super().__init__(payload)
            self.status_code = 200
            self.headers = {}

    class FakeResponse:
        def __init__(self, data, mimetype=None):
            self.data = data
            self.mimetype = mimetype
            self.headers = {}

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
    fake_flask.jsonify = lambda payload: FakeJsonResponse(payload)
    fake_flask.Response = FakeResponse
    fake_flask.session = {}

    fake_werkzeug_utils = types.ModuleType("werkzeug.utils")
    fake_werkzeug_utils.secure_filename = lambda name: name

    fake_engine = types.ModuleType("app.engine")
    fake_engine.upload_pdf_and_init = lambda *args, **kwargs: ("Intro", None)
    fake_engine.process_action = process_action_impl or (lambda *args, **kwargs: iter([{"type": "done"}]))

    fake_state = types.ModuleType("app.state")
    fake_state.get_or_create_session_state = lambda _session_id: {"chat_session": object()}

    sys.modules.pop("app.main", None)
    with patch.dict(
        sys.modules,
        {
            "flask": fake_flask,
            "werkzeug.utils": fake_werkzeug_utils,
            "app.engine": fake_engine,
            "app.state": fake_state,
        },
    ):
        main = importlib.import_module("app.main")
        return importlib.reload(main), fake_flask


class RoutesTests(unittest.TestCase):
    def test_upload_rejects_invalid_extension(self):
        main, fake_flask = load_main_module()

        class FakeUpload:
            filename = "evil.exe"
            mimetype = "application/pdf"

            def save(self, *_args, **_kwargs):
                raise AssertionError("save should not be called for invalid extension")

        fake_flask.request.files = {"file": FakeUpload()}
        fake_flask.request.headers = {}

        response = main.upload()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["error"], "Only PDF files are supported.")
        self.assertEqual(response["code"], "bad_request")
        self.assertIn("request_id", response)

    def test_load_url_requires_url(self):
        main, fake_flask = load_main_module()
        fake_flask.request.json = {}
        fake_flask.request.headers = {}

        response = main.load_url()

        self.assertEqual(response.status_code, 400)
        self.assertEqual(response["error"], "No url provided")
        self.assertEqual(response["code"], "bad_request")
        self.assertIn("request_id", response)

    def test_action_stream_returns_ndjson_events(self):
        def fake_process_action(*_args, **_kwargs):
            return iter(
                [
                    {"type": "text_chunk", "text": "Hello"},
                    {"type": "tool_call", "message": "Rolling"},
                    {"type": "image", "image_data": "data:image/png;base64,abc"},
                    {"type": "done"},
                ]
            )

        main, fake_flask = load_main_module(process_action_impl=fake_process_action)
        fake_flask.request.json = {"text": "look"}
        fake_flask.request.headers = {}

        response = main.action()
        lines = list(response.data)
        events = [json.loads(line.strip()) for line in lines]

        self.assertEqual(events[0]["type"], "text_chunk")
        self.assertEqual(events[1]["type"], "tool_call")
        self.assertEqual(events[2]["type"], "image")
        self.assertEqual(events[3]["type"], "done")


if __name__ == "__main__":
    unittest.main()
