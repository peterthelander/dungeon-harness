import importlib
import sys
import types
import unittest
from types import SimpleNamespace
from unittest.mock import MagicMock, patch


def load_engine_module():
    fake_types = SimpleNamespace(
        GenerateContentConfig=lambda **kwargs: kwargs,
        AutomaticFunctionCallingConfig=lambda **kwargs: kwargs,
        Part=SimpleNamespace(
            from_function_response=staticmethod(lambda name, response: {"name": name, "response": response})
        ),
    )

    class FakeClient:
        def __init__(self, *args, **kwargs):
            self.chats = SimpleNamespace(create=MagicMock())
            self.models = SimpleNamespace(generate_content=MagicMock())
            self.files = SimpleNamespace(upload=MagicMock(), get=MagicMock())

    fake_genai = types.ModuleType("google.genai")
    fake_genai.Client = FakeClient
    fake_genai.types = fake_types

    fake_google = types.ModuleType("google")
    fake_google.genai = fake_genai

    sys.modules.pop("app.engine", None)
    with patch.dict(sys.modules, {"google": fake_google, "google.genai": fake_genai}):
        engine = importlib.import_module("app.engine")
        return importlib.reload(engine)


def make_chunk(text=None, function_calls=None):
    parts = []
    if text is not None:
        parts.append(SimpleNamespace(text=text))
    content = SimpleNamespace(parts=parts)
    candidate = SimpleNamespace(content=content)
    return SimpleNamespace(candidates=[candidate], function_calls=function_calls or [])


class ProcessActionTests(unittest.TestCase):
    def setUp(self):
        self.engine = load_engine_module()

    def test_process_action_streams_text_chunks(self):
        chat_session = MagicMock()
        chat_session.send_message_stream.return_value = iter(
            [
                make_chunk(text="Hello "),
                make_chunk(text="adventurer!"),
            ]
        )
        session_state = {"chat_session": chat_session}

        events = list(self.engine.process_action("look around", session_state))

        self.assertEqual(
            events,
            [
                {"type": "text_chunk", "text": "Hello "},
                {"type": "text_chunk", "text": "adventurer!"},
                {"type": "done"},
            ],
        )

    def test_process_action_intercepts_draw_scene_and_yields_image(self):
        chat_session = MagicMock()
        draw_scene_fc = SimpleNamespace(name="draw_scene", args={"visual_description": "misty dungeon hall"})
        chat_session.send_message_stream.side_effect = [
            iter([make_chunk(function_calls=[draw_scene_fc])]),
            iter([make_chunk(text="The chamber opens before you.")]),
        ]

        fake_future = MagicMock()
        fake_future.done.return_value = True
        fake_future.result.return_value = "data:image/png;base64,abc123"

        session_state = {"chat_session": chat_session}

        with patch.object(self.engine.IMAGE_EXECUTOR, "submit", return_value=fake_future) as submit_mock:
            events = list(self.engine.process_action("open the door", session_state))

        self.assertIn({"type": "image", "image_data": "data:image/png;base64,abc123"}, events)
        self.assertIn({"type": "done"}, events)
        submit_mock.assert_called_once()
        called_args = submit_mock.call_args[0]
        self.assertEqual(called_args[1], "misty dungeon hall")
        self.assertIs(called_args[2], session_state)


if __name__ == "__main__":
    unittest.main()
