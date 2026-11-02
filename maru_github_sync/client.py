"""Client GitHub Contents REST API berbasis standard library (tanpa dependency tambahan).

Mendukung:
- Cek kesehatan koneksi & izin repo (`check_repo`)
- Baca file & SHA dari GitHub (`get_file`)
- Daftar isi folder rekursif lewat Git Trees API / Contents API (`list_directory`)
- Buat / perbarui file secara idempotent bila konten berubah (`put_file`)
"""
from __future__ import annotations

import base64
import hashlib
import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any, Callable

from .config import GitHubSyncConfig, redact_secret


class GitHubSyncError(RuntimeError):
    """Error terstruktur saat mengakses GitHub API (tanpa membocorkan token)."""


def git_blob_sha1(data: bytes) -> str:
    """Hitung Git blob SHA-1 untuk mendeteksi apakah file di GitHub sudah identik."""
    header = f"blob {len(data)}\0".encode("ascii")
    return hashlib.sha1(header + data).hexdigest()  # noqa: S324 - standar objek Git


class GitHubContentsClient:
    """Wrapper ringan untuk GitHub REST API v2022-11-28."""

    def __init__(
        self,
        config: GitHubSyncConfig,
        urlopen_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config
        self._urlopen = urlopen_fn or urllib.request.urlopen

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "maru-ai-github-sync/1.0",
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers

    def _request(
        self,
        method: str,
        path: str,
        payload: dict[str, Any] | None = None,
    ) -> Any:
        url = f"{self.config.api_base}{path}"
        body = None
        headers = self._headers()
        if payload is not None:
            body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json; charset=utf-8"

        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with self._urlopen(req, timeout=self.config.timeout_sec) as resp:
                raw = resp.read().decode("utf-8")
                return json.loads(raw) if raw else {}
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8", errors="replace")[:400]
            except Exception:
                detail = str(exc)
            safe_detail = redact_secret(detail, self.config.token)
            raise GitHubSyncError(
                f"GitHub API HTTP {exc.code} pada {method} {path}: {safe_detail}"
            ) from None
        except Exception as exc:
            safe_msg = redact_secret(str(exc), self.config.token)
            raise GitHubSyncError(f"Gagal menghubungi GitHub API ({method} {path}): {safe_msg}") from None

    def check_repo(self) -> dict[str, Any]:
        """Verifikasi akses ke repository target."""
        data = self._request("GET", f"/repos/{self.config.repo}")
        perms = data.get("permissions") or {}
        return {
            "ok": True,
            "full_name": data.get("full_name", self.config.repo),
            "private": bool(data.get("private", True)),
            "default_branch": data.get("default_branch", self.config.branch),
            "can_push": bool(perms.get("push", True)),
            "description": data.get("description") or "",
        }

    def get_file(self, remote_path: str) -> dict[str, Any] | None:
        """Ambil konten & SHA satu file dari branch target; return None bila 404."""
        clean_path = urllib.parse.quote(remote_path.lstrip("/"), safe="/")
        branch_q = urllib.parse.quote(self.config.branch, safe="")
        try:
            data = self._request(
                "GET", f"/repos/{self.config.repo}/contents/{clean_path}?ref={branch_q}"
            )
        except GitHubSyncError as exc:
            if "HTTP 404" in str(exc):
                return None
            raise

        if isinstance(data, list):
            raise GitHubSyncError(f"Path '{remote_path}' adalah direktori, bukan file.")
        encoded = (data.get("content") or "").replace("\n", "")
        raw_bytes = base64.b64decode(encoded) if encoded else b""
        return {
            "path": data.get("path", remote_path),
            "sha": data.get("sha", ""),
            "size": data.get("size", len(raw_bytes)),
            "bytes": raw_bytes,
        }

    def list_files_recursive(self, prefix: str = "") -> list[dict[str, str]]:
        """Daftar seluruh file pada branch memakai Git Trees API."""
        branch_q = urllib.parse.quote(self.config.branch, safe="")
        data = self._request(
            "GET", f"/repos/{self.config.repo}/git/trees/{branch_q}?recursive=1"
        )
        clean_prefix = prefix.strip("/")
        results: list[dict[str, str]] = []
        for item in data.get("tree") or []:
            if item.get("type") != "blob":
                continue
            item_path = str(item.get("path", ""))
            if clean_prefix and not (
                item_path == clean_prefix or item_path.startswith(clean_prefix + "/")
            ):
                continue
            results.append({"path": item_path, "sha": str(item.get("sha", ""))})
        return results

    def put_file(
        self,
        remote_path: str,
        content_bytes: bytes,
        message: str,
        known_sha: str | None = None,
    ) -> dict[str, Any]:
        """Unggah/perbarui satu file. Lewati (skipped=True) bila konten identik."""
        clean_path = remote_path.lstrip("/")
        local_blob_sha = git_blob_sha1(content_bytes)

        remote_sha = known_sha
        if remote_sha is None:
            existing = self.get_file(clean_path)
            if existing is not None:
                remote_sha = existing["sha"]

        if remote_sha and remote_sha == local_blob_sha:
            return {"path": clean_path, "status": "unchanged", "sha": remote_sha}

        payload: dict[str, Any] = {
            "message": message,
            "content": base64.b64encode(content_bytes).decode("ascii"),
            "branch": self.config.branch,
        }
        if remote_sha:
            payload["sha"] = remote_sha

        quoted_path = urllib.parse.quote(clean_path, safe="/")
        resp = self._request("PUT", f"/repos/{self.config.repo}/contents/{quoted_path}", payload)
        new_sha = ((resp.get("content") or {}).get("sha")) or local_blob_sha
        return {
            "path": clean_path,
            "status": "updated" if remote_sha else "created",
            "sha": new_sha,
        }
