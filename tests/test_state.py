import unittest

from app.state import SessionState, SessionStore


class SessionStateTests(unittest.TestCase):
    def setUp(self):
        self.store = SessionStore(ttl_seconds=3600, max_items=500)

    def test_get_or_create_creates_isolated_typed_sessions(self):
        session_a = self.store.get_or_create("session-a")
        session_b = self.store.get_or_create("session-b")

        self.assertIsInstance(session_a, SessionState)
        self.assertIsNot(session_a, session_b)
        self.assertIsNone(session_a.chat_session)
        self.assertIsNone(session_a.latest_pdf)
        self.assertIsNone(session_a.module_source_type)
        self.assertIsNone(session_a.module_source_url)
        self.assertIsNone(session_a.module_source_name)
        self.assertTrue(session_a.action_lock.acquire(blocking=False))
        session_a.action_lock.release()

    def test_get_or_create_returns_same_session(self):
        session = self.store.get_or_create("session-ongoing")
        session.chat_session = "persisted-chat"

        fetched = self.store.get_or_create("session-ongoing")

        self.assertIs(fetched, session)
        self.assertEqual(fetched.chat_session, "persisted-chat")

    def test_session_state_reset(self):
        session = self.store.get_or_create("session-reset")
        session.chat_session = "active-chat"
        session.latest_pdf = "active.pdf"
        session.history.append({"type": "message"})
        session.hero_image_url = "http://hero"
        session.module_source_type = "url"
        session.module_source_url = "https://example.com/module.pdf"
        session.module_source_name = "module.pdf"

        session.reset()

        self.assertIsNone(session.chat_session)
        self.assertIsNone(session.latest_pdf)
        self.assertEqual(len(session.history), 0)
        self.assertIsNone(session.hero_image_url)
        self.assertIsNone(session.module_source_type)
        self.assertIsNone(session.module_source_url)
        self.assertIsNone(session.module_source_name)


    def test_store_evicts_oldest_when_max_sessions_exceeded(self):
        self.store.max_items = 1
        self.store.get_or_create("session-one")
        self.store.get_or_create("session-two")

        self.assertEqual(self.store.size(), 1)
        self.assertNotIn("session-one", self.store._entries)

    def test_store_removes_expired_entries(self):
        self.store.ttl_seconds = 1
        self.store.get_or_create("session-expired")
        self.store._entries["session-expired"]["last_accessed_at"] -= 5
        self.store.get_or_create("session-fresh")

        self.assertNotIn("session-expired", self.store._entries)
        self.assertIn("session-fresh", self.store._entries)


if __name__ == "__main__":
    unittest.main()
