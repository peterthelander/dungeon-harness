import os
import queue
import time
import threading
from collections import OrderedDict


class _ExpiringBoundedStore:
    """Thread-safe expiring store with max-key eviction."""

    def __init__(self, ttl_seconds: int, max_items: int):
        self.ttl_seconds = ttl_seconds
        self.max_items = max_items
        self._entries = OrderedDict()
        self._lock = threading.Lock()

    def _cleanup_locked(self):
        now = time.time()
        expired = [
            key
            for key, entry in self._entries.items()
            if now - entry["last_accessed_at"] >= self.ttl_seconds
            and not entry["value"].get("action_lock", threading.Lock()).locked()
        ]
        for key in expired:
            self._entries.pop(key, None)
        while len(self._entries) > self.max_items:
            evictable_key = next(
                (
                    key for key, entry in self._entries.items()
                    if not entry["value"].get("action_lock", threading.Lock()).locked()
                ),
                None,
            )
            if evictable_key is None:
                break
            self._entries.pop(evictable_key)

    def get_or_create(self, key: str, factory):
        with self._lock:
            self._cleanup_locked()
            entry = self._entries.get(key)
            if entry is None:
                entry = {"value": factory(), "last_accessed_at": time.time()}
                self._entries[key] = entry
            else:
                entry["last_accessed_at"] = time.time()
                self._entries.move_to_end(key)
            return entry["value"]

    def set(self, key: str, value):
        with self._lock:
            self._cleanup_locked()
            self._entries[key] = {"value": value, "last_accessed_at": time.time()}
            self._entries.move_to_end(key)
            self._cleanup_locked()

    def get(self, key: str):
        with self._lock:
            self._cleanup_locked()
            entry = self._entries.get(key)
            if entry is None:
                return None
            entry["last_accessed_at"] = time.time()
            self._entries.move_to_end(key)
            return entry["value"]

    def clear(self):
        with self._lock:
            self._entries.clear()

    def size(self) -> int:
        with self._lock:
            self._cleanup_locked()
            return len(self._entries)


_session_ttl = int(os.environ.get("SESSION_TTL_SECONDS", "3600"))
_max_sessions = int(os.environ.get("MAX_SESSIONS", "500"))

_session_store = _ExpiringBoundedStore(ttl_seconds=_session_ttl, max_items=_max_sessions)
_active_queue_store = _ExpiringBoundedStore(ttl_seconds=_session_ttl, max_items=_max_sessions)


def _default_session_bucket():
    return {
        "chat_session": None,
        "latest_pdf": None,
        "previous_visual_desc": "",
        "action_lock": threading.Lock(),
    }


def get_or_create_session_state(session_id: str):
    return _session_store.get_or_create(session_id, _default_session_bucket)


def set_active_queue(session_id: str, q: queue.Queue):
    _active_queue_store.set(session_id, q)


def get_active_queue(session_id: str):
    return _active_queue_store.get(session_id)


def get_session_count() -> int:
    return _session_store.size()


class _EngineStateProxy:
    def clear(self):
        _session_store.clear()


engine_state = _EngineStateProxy()
