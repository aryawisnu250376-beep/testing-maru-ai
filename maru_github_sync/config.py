"""Konfigurasi aman untuk sinkronisasi Skill & Memori MARU AI ke GitHub.

Aturan keamanan (sesuai Master Prompt MARU):
- Token HANYA dibaca dari environment variable / file .env lokal yang di-ignore.
- Nilai token selalu disensor saat dicetak ke log atau repr().
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_REPO = "aryawisnu250376-beep/testing-maru-ai"
DEFAULT_BRANCH = "main"


def _load_dotenv_if_present(root: Path) -> dict[str, str]:
    """Baca key=value sederhana dari .env tanpa menimpa env yang sudah ada."""
    values: dict[str, str] = {}
    candidates = [
        root / ".env",
        root / "01-social-media-agent" / ".env",
        root / "02-academic-ai" / ".env",
    ]
    for env_file in candidates:
        if not env_file.is_file():
            continue
        try:
            for raw_line in env_file.read_text(encoding="utf-8").splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"').strip("'")
                if k and k not in values:
                    values[k] = v
        except Exception:
            continue
    return values


def redact_secret(text: str, token: str = "") -> str:
    """Sensor token dari pesan log/error."""
    if not text:
        return ""
    cleaned = text
    if token and len(token) >= 6:
        cleaned = cleaned.replace(token, "***REDACTED_TOKEN***")
    for prefix in ("github_pat_", "ghp_", "gho_", "ghs_"):
        if prefix in cleaned:
            idx = cleaned.find(prefix)
            end = idx
            while end < len(cleaned) and not cleaned[end].isspace() and cleaned[end] not in ('"', "'", ",", ")"):
                end += 1
            cleaned = cleaned[:idx] + "***REDACTED_TOKEN***" + cleaned[end:]
    return cleaned


@dataclass(frozen=True)
class GitHubSyncConfig:
    repo_root: Path
    enabled: bool = False
    repo: str = DEFAULT_REPO
    branch: str = DEFAULT_BRANCH
    token: str = ""
    timeout_sec: int = 20
    api_base: str = "https://api.github.com"

    def __repr__(self) -> str:
        masked = "***SET***" if self.token else "EMPTY"
        return (
            f"GitHubSyncConfig(enabled={self.enabled}, repo={self.repo!r}, "
            f"branch={self.branch!r}, token={masked})"
        )

    @property
    def is_ready(self) -> bool:
        return bool(self.enabled and self.repo and "/" in self.repo and self.token)

    @classmethod
    def from_env(cls, repo_root: Path | None = None) -> "GitHubSyncConfig":
        root = (repo_root or Path(__file__).resolve().parents[1]).resolve()
        file_env = _load_dotenv_if_present(root)

        def _get(name: str, default: str = "") -> str:
            val = os.getenv(name)
            if val is not None and val.strip() != "":
                return val.strip()
            return file_env.get(name, default).strip()

        raw_enabled = _get("MARU_GITHUB_SYNC_ENABLED", "")
        token = _get("MARU_GITHUB_TOKEN") or _get("GITHUB_TOKEN")
        if raw_enabled == "":
            enabled = bool(token)
        else:
            enabled = raw_enabled.lower() in {"1", "true", "yes", "on"}

        repo = _get("MARU_GITHUB_REPO", DEFAULT_REPO) or DEFAULT_REPO
        branch = _get("MARU_GITHUB_BRANCH", DEFAULT_BRANCH) or DEFAULT_BRANCH
        try:
            timeout_sec = max(5, min(120, int(_get("MARU_GITHUB_TIMEOUT", "20"))))
        except ValueError:
            timeout_sec = 20
        api_base = _get("MARU_GITHUB_API_BASE", "https://api.github.com").rstrip("/")

        return cls(
            repo_root=root,
            enabled=enabled,
            repo=repo,
            branch=branch,
            token=token,
            timeout_sec=timeout_sec,
            api_base=api_base,
        )
