"""In-memory conversation memory keyed by session_id (so 'is it edible?' can follow 'what is this?')."""
from __future__ import annotations

import time
import uuid
from dataclasses import dataclass, field


@dataclass
class Session:
    id: str
    turns: list[dict] = field(default_factory=list)   # {question, answer_json, ts}
    last_image: bytes | None = None
    last_media_type: str = "image/jpeg"
    updated: float = field(default_factory=time.time)


class SessionStore:
    def __init__(self, ttl_s: int = 1800, max_turns: int = 8):
        self.ttl = ttl_s
        self.max_turns = max_turns
        self._s: dict[str, Session] = {}

    def get_or_create(self, session_id: str | None) -> Session:
        self._sweep()
        if session_id and session_id in self._s:
            s = self._s[session_id]
            s.updated = time.time()
            return s
        sid = session_id or uuid.uuid4().hex[:16]
        s = Session(id=sid)
        self._s[sid] = s
        return s

    def record(self, s: Session, question: str, answer_json: str, image: bytes | None, media_type: str) -> None:
        s.turns.append({"question": question, "answer_json": answer_json, "ts": time.time()})
        s.turns = s.turns[-self.max_turns :]
        if image is not None:
            s.last_image = image
            s.last_media_type = media_type
        s.updated = time.time()

    def _sweep(self) -> None:
        now = time.time()
        for k in [k for k, v in self._s.items() if now - v.updated > self.ttl]:
            del self._s[k]
