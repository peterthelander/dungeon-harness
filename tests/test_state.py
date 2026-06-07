import unittest

import app.state as state_module
from app.state import engine_state, get_or_create_session_state, get_session_count


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

    def test_session_store_evicts_oldest_when_max_sessions_exceeded(self):
        original_max = state_module._session_store.max_items
        try:
            state_module._session_store.max_items = 1
            get_or_create_session_state("session-one")
            get_or_create_session_state("session-two")
            self.assertEqual(get_session_count(), 1)
            self.assertIsNone(state_module._session_store.get("session-one"))
        finally:
            state_module._session_store.max_items = original_max

    def test_session_store_removes_expired_entries(self):
        original_ttl = state_module._session_store.ttl_seconds
        try:
            state_module._session_store.ttl_seconds = 1
            get_or_create_session_state("session-expired")
            state_module._session_store._entries["session-expired"]["last_accessed_at"] -= 5
            get_or_create_session_state("session-fresh")
            self.assertIsNone(state_module._session_store.get("session-expired"))
            self.assertIsNotNone(state_module._session_store.get("session-fresh"))
        finally:
            state_module._session_store.ttl_seconds = original_ttl


if __name__ == "__main__":
    unittest.main()
