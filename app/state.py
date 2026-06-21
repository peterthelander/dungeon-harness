import threading
import time

engine_state = {}
_state_lock = threading.RLock()
SESSION_TTL_SECONDS = 4 * 60 * 60

def get_or_create_session_state(session_id: str):
    """Return a process-local game session and refresh its expiry timer.

    Gemini chat objects are not serializable, so this remains an in-process store.
    The expiry and per-session lock prevent abandoned sessions from growing without
    bound and prevent overlapping turns from corrupting a chat history.
    """
    with _state_lock:
        cleanup_expired_session_state()
        state = engine_state.setdefault(session_id, {
            "chat_session": None,
            "latest_pdf": None,
            "action_lock": threading.Lock(),
            "last_accessed": time.monotonic(),
        })
        state["last_accessed"] = time.monotonic()
        return state

def cleanup_expired_session_state(now: float | None = None):
    """Remove idle sessions. Returns the number of sessions removed."""
    now = time.monotonic() if now is None else now
    with _state_lock:
        expired = [
            session_id for session_id, state in engine_state.items()
            if now - state.get("last_accessed", now) > SESSION_TTL_SECONDS
            and not state.get("action_lock", threading.Lock()).locked()
        ]
        for session_id in expired:
            del engine_state[session_id]
        return len(expired)
