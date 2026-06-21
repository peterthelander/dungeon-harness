import threading

from app import state


def test_cleanup_removes_idle_unlocked_session(monkeypatch):
    monkeypatch.setattr(state, "engine_state", {
        "old": {"last_accessed": 0, "action_lock": threading.Lock()},
        "current": {"last_accessed": 100, "action_lock": threading.Lock()},
    })

    removed = state.cleanup_expired_session_state(now=state.SESSION_TTL_SECONDS + 1)

    assert removed == 1
    assert "old" not in state.engine_state
    assert "current" in state.engine_state
