import unittest

from app.state import engine_state, get_or_create_session_state


class SessionStateTests(unittest.TestCase):
    def setUp(self):
        engine_state.clear()

    def test_get_or_create_session_state_creates_isolated_bucket_for_new_session(self):
        session_a = get_or_create_session_state("session-a")
        session_b = get_or_create_session_state("session-b")

        self.assertIsInstance(session_a, dict)
        self.assertIsInstance(session_b, dict)
        self.assertIsNot(session_a, session_b)
        self.assertEqual(
            session_a,
            {
                "chat_session": None,
                "latest_pdf": None,
                "previous_visual_desc": "",
            },
        )

    def test_get_or_create_session_state_returns_same_bucket_for_existing_session(self):
        session = get_or_create_session_state("session-ongoing")
        session["chat_session"] = "persisted-chat"

        fetched = get_or_create_session_state("session-ongoing")

        self.assertIs(fetched, session)
        self.assertEqual(fetched["chat_session"], "persisted-chat")


if __name__ == "__main__":
    unittest.main()
