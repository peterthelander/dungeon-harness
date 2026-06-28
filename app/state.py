import threading
import time
from collections import OrderedDict
from dataclasses import dataclass, field
from typing import Any, Callable


@dataclass
class SessionState:
    """Mutable state for one active game session."""

    chat_session: Any = None
    latest_pdf: Any = None
    action_lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    history: list = field(default_factory=list)
    hero_image_url: Any = None


class SessionStore:
    """Thread-safe, bounded in-memory store for active game sessions."""

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
            if now - entry["last_accessed_at"] >= self.ttl_seconds and not entry["value"].action_lock.locked()
        ]
        for key in expired:
            self._entries.pop(key, None)

        while len(self._entries) > self.max_items:
            evictable_key = next(
                (key for key, entry in self._entries.items() if not entry["value"].action_lock.locked()),
                None,
            )
            if evictable_key is None:
                break
            self._entries.pop(evictable_key)

    def get_or_create(self, key: str, factory: Callable[[], SessionState] = SessionState) -> SessionState:
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

    def clear(self):
        with self._lock:
            self._entries.clear()

    def size(self) -> int:
        with self._lock:
            self._cleanup_locked()
            return len(self._entries)
