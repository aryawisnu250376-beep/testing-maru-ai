"""Authentication for the mobile studio. No secret is embedded in the HTML.

Sessions are opaque, short-lived bearer tokens. Only their SHA-256 hashes live
in memory. The browser keeps a token in sessionStorage (or memory in a sandbox).
No cookie means no ambient authority and no cross-site form submission.
"""
from __future__ import annotations

import hashlib
import hmac
import os
import secrets
import threading
import time
from dataclasses import dataclass, field

MIN_PASSWORD_LENGTH = 16
SESSION_TTL = 12 * 60 * 60


class AuthManager:
    def __init__(self, password: str = "", ttl: int = SESSION_TTL):
        self.password = password
        self.ttl = ttl
        self._sessions: dict[str, float] = {}
        self._attempts: dict[str, list[float]] = {}
        self._lock = threading.Lock()

    @property
    def configured(self) -> bool:
        return len(self.password) >= MIN_PASSWORD_LENGTH

    @staticmethod
    def _hash(token: str) -> str:
        return hashlib.sha256(token.encode()).hexdigest()

    def login(self, password: str, client: str, now: float | None = None) -> tuple[str | None, int]:
        now = time.time() if now is None else now
        with self._lock:
            attempts = [t for t in self._attempts.get(client, []) if now - t < 300]
            if len(attempts) >= 5:
                self._attempts[client] = attempts
                return None, max(1, int(300 - (now - attempts[0])))
            if not self.configured or not hmac.compare_digest(
                    password.encode(), self.password.encode()):
                attempts.append(now)
                self._attempts[client] = attempts
                return None, 0
            self._attempts.pop(client, None)
            self._sessions = {k: v for k, v in self._sessions.items() if v > now}
            token = secrets.token_urlsafe(32)
            self._sessions[self._hash(token)] = now + self.ttl
            return token, self.ttl

    def valid(self, token: str, now: float | None = None) -> bool:
        now = time.time() if now is None else now
        if not token or len(token) > 256:
            return False
        with self._lock:
            expiry = self._sessions.get(self._hash(token), 0)
            return expiry > now

    def logout(self, token: str) -> None:
        with self._lock:
            self._sessions.pop(self._hash(token), None)


@dataclass
class Runtime:
    auth: AuthManager
    orchestrate: bool = False
    started_at: float = field(default_factory=time.time)


def from_environment(host: str) -> Runtime:
    password = os.getenv("STUDIO_PASSWORD", "") or os.getenv("STUDIO_ACCESS_TOKEN", "")
    if password and len(password) < MIN_PASSWORD_LENGTH:
        raise RuntimeError("STUDIO_PASSWORD minimal 16 karakter.")
    public = host not in ("127.0.0.1", "localhost", "::1")
    if public and not password:
        raise RuntimeError("Akses non-lokal wajib memakai STUDIO_PASSWORD (minimal 16 karakter). "
                           "Jangan ekspos studio tanpa login.")
    if not password:
        password = secrets.token_urlsafe(24)
        print("Kata sandi sesi lokal (tidak disimpan): " + password)
    return Runtime(AuthManager(password))
