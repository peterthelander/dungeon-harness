import importlib
import inspect
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


def make_chunk(text=None, function_calls=None, function_call_parts=None):
    parts = []
    if text is not None:
        parts.append(SimpleNamespace(text=text))
    for function_call in function_call_parts or []:
        parts.append(SimpleNamespace(function_call=function_call))
    content = SimpleNamespace(parts=parts)
    candidate = SimpleNamespace(content=content)
    return SimpleNamespace(candidates=[candidate], function_calls=function_calls or [])


class ProcessActionTests(unittest.TestCase):
    def setUp(self):
        self.engine = load_engine_module()

    def test_model_facing_scene_tool_hides_server_session(self):
        parameters = inspect.signature(self.engine.draw_scene_tool).parameters

        self.assertEqual(self.engine.draw_scene_tool.__name__, "draw_scene")
        self.assertEqual(list(parameters), ["visual_description"])

    def test_normalize_suggestions_filters_invalid_and_duplicate_labels(self):
        suggestions = self.engine._normalize_suggestions(
            [" Listen ", "listen", "", 7, "A" * 81, "Open door", "Ask guard"]
        )

        self.assertEqual(suggestions, ["Listen", "Open door", "Ask guard"])

    def test_suggestions_in_text_keeps_only_visible_phrases(self):
        suggestions = self.engine._suggestions_in_text(
            ["Fighter", "Examine entrance", "Magic-User"],
            "Choose a Fighter, Rogue, or Magic-User.",
        )

        self.assertEqual(suggestions, ["Fighter", "Magic-User"])

    def test_process_action_streams_suggestions(self):
        chat_session = MagicMock()
        suggestions_fc = SimpleNamespace(
            name="suggest_actions", args={"suggestions": ["Listen", "Inspect door"]}
        )
        chat_session.send_message_stream.side_effect = [
            iter([make_chunk(text="You could Listen or Inspect door.", function_calls=[suggestions_fc])]),
            iter([make_chunk()]),
        ]
        session_state = {"chat_session": chat_session}

        events = list(self.engine.process_action("wait", session_state))

        self.assertIn({"type": "suggestions", "items": ["Listen", "Inspect door"]}, events)

    def test_process_action_recovers_suggestions_when_turn_omits_them(self):
        chat_session = MagicMock()
        recovery_fc = SimpleNamespace(name="suggest_actions", args={"suggestions": ["Take cover"]})
        chat_session.send_message_stream.return_value = iter([make_chunk(text="The floor trembles. Take cover.")])
        chat_session.send_message.return_value = make_chunk(function_calls=[recovery_fc])
        session_state = {"chat_session": chat_session}

        events = list(self.engine.process_action("wait", session_state))

        self.assertIn({"type": "suggestions", "items": ["Take cover"]}, events)
        self.assertEqual(chat_session.send_message.call_count, 2)

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

    def test_process_action_recovers_from_empty_stream_with_non_streaming_response(self):
        chat_session = MagicMock()
        chat_session.send_message_stream.return_value = iter([make_chunk()])
        chat_session.send_message.return_value = make_chunk(text="Let's begin your character creation.")
        session_state = {"chat_session": chat_session}

        events = list(self.engine.process_action("yes", session_state))

        self.assertIn(
            {"type": "text_chunk", "text": "Let's begin your character creation."},
            events,
        )
        self.assertEqual(chat_session.send_message.call_count, 2)

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

    def test_process_action_reads_function_calls_from_candidate_parts(self):
        chat_session = MagicMock()
        draw_scene_fc = SimpleNamespace(name="draw_scene", args={"visual_description": "stormy battlements"})
        chat_session.send_message_stream.side_effect = [
            iter([make_chunk(function_call_parts=[draw_scene_fc])]),
            iter([make_chunk(text="Lightning cracks over the spire.")]),
        ]

        fake_future = MagicMock()
        fake_future.done.return_value = True
        fake_future.result.return_value = "data:image/png;base64,storm"

        session_state = {"chat_session": chat_session}

        with patch.object(self.engine.IMAGE_EXECUTOR, "submit", return_value=fake_future):
            events = list(self.engine.process_action("step outside", session_state))

        self.assertIn({"type": "image", "image_data": "data:image/png;base64,storm"}, events)
        self.assertIn({"type": "text_chunk", "text": "Lightning cracks over the spire."}, events)

    def test_upload_pdf_and_init_reads_function_calls_from_candidate_parts(self):
        uploaded_pdf = SimpleNamespace(name="module.pdf", state=SimpleNamespace(name="ACTIVE"))
        chat_session = MagicMock()
        draw_scene_fc = SimpleNamespace(name="draw_scene", args={"visual_description": "moonlit ruins"})
        initial_response = make_chunk(function_call_parts=[draw_scene_fc])
        followup_response = make_chunk(text="A ruined keep looms over the marsh. Are you ready to begin?")
        session_state = {}

        def fake_draw_scene(*_args, **_kwargs):
            return "data:image/png;base64,ruins"

        with (
            patch.object(self.engine.model_client, "upload_file", return_value=uploaded_pdf),
            patch.object(self.engine.model_client, "wait_for_file_processing", return_value=uploaded_pdf),
            patch.object(self.engine.model_client, "create_chat_session", return_value=chat_session),
            patch.object(
                self.engine.model_client,
                "send_message",
                side_effect=[initial_response, followup_response, make_chunk()],
            ),
            patch.object(self.engine, "draw_scene", side_effect=fake_draw_scene),
        ):
            dm_text, image_data, suggestions = self.engine.upload_pdf_and_init("/tmp/module.pdf", "module.pdf", session_state)

        self.assertEqual(dm_text, "A ruined keep looms over the marsh. Are you ready to begin?")
        self.assertEqual(image_data, "data:image/png;base64,ruins")
        self.assertEqual(suggestions, [])
        self.assertIs(session_state["chat_session"], chat_session)


if __name__ == "__main__":
    unittest.main()
