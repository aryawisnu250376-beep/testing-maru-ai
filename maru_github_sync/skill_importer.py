"""Importer Skill dari Repository GitHub Eksternal / Publik ke Ekosistem MARU AI.

Mendukung berbagai format sumber GitHub:
1. URL folder GitHub : https://github.com/anthropics/skills/tree/main/skills/docx
2. URL file GitHub   : https://github.com/owner/repo/blob/main/skills/riset/SKILL.md
3. URL Raw GitHub    : https://raw.githubusercontent.com/owner/repo/main/SKILL.md
4. Shorthand         : owner/repo  atau  owner/repo/path/ke/skill
"""
from __future__ import annotations

import json
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from .client import GitHubSyncError
from .config import GitHubSyncConfig, redact_secret

VALID_DIVISIONS = ("academic", "social-media", "shared")
_SAFE_SLUG_RE = re.compile(r"[^a-z0-9-]+")


def slugify_skill_name(raw: str) -> str:
    slug = _SAFE_SLUG_RE.sub("-", raw.strip().lower()).strip("-")
    return slug or "custom-skill"


@dataclass(frozen=True)
class ParsedGitHubSkillSource:
    kind: str  # "raw" | "blob" | "tree" | "repo_root"
    owner: str
    repo: str
    ref: str
    path: str
    raw_url: str = ""


def parse_github_skill_source(source: str) -> ParsedGitHubSkillSource:
    """Urai URL atau shorthand GitHub menjadi komponen yang terstruktur."""
    src = source.strip().rstrip("/")
    if not src:
        raise ValueError("URL atau alamat repository GitHub tidak boleh kosong.")

    # 1. raw.githubusercontent.com/<owner>/<repo>/<ref>/<path...>
    if src.startswith("https://raw.githubusercontent.com/"):
        rest = src.removeprefix("https://raw.githubusercontent.com/")
        parts = rest.split("/", 3)
        if len(parts) < 4:
            raise ValueError(f"URL raw GitHub tidak lengkap: {source}")
        return ParsedGitHubSkillSource(
            kind="raw",
            owner=parts[0],
            repo=parts[1],
            ref=parts[2],
            path=parts[3],
            raw_url=src,
        )

    # 2. https://github.com/<owner>/<repo>[/tree|blob/<ref>/<path...>]
    if src.startswith(("https://github.com/", "http://github.com/")):
        parsed = urllib.parse.urlparse(src)
        parts = [p for p in parsed.path.strip("/").split("/") if p]
        if len(parts) < 2:
            raise ValueError(f"URL GitHub harus memuat owner/repo: {source}")
        owner, repo = parts[0], parts[1].removesuffix(".git")
        if len(parts) == 2:
            return ParsedGitHubSkillSource("repo_root", owner, repo, "", "")
        if len(parts) >= 4 and parts[2] in ("tree", "blob"):
            mode = parts[2]
            ref = parts[3]
            subpath = "/".join(parts[4:])
            return ParsedGitHubSkillSource(mode, owner, repo, ref, subpath)
        subpath = "/".join(parts[2:])
        return ParsedGitHubSkillSource("tree", owner, repo, "", subpath)

    # 3. Shorthand: owner/repo[/subpath...]
    if "://" not in src and "/" in src:
        parts = [p for p in src.strip("/").split("/") if p]
        if len(parts) >= 2:
            owner, repo = parts[0], parts[1].removesuffix(".git")
            subpath = "/".join(parts[2:])
            kind = "tree" if subpath else "repo_root"
            return ParsedGitHubSkillSource(kind, owner, repo, "", subpath)

    raise ValueError(
        f"Format sumber GitHub tidak dikenali: {source}. "
        "Contoh valid: https://github.com/anthropics/skills/tree/main/skills/pdf"
    )


def _extract_frontmatter_name(markdown_text: str) -> str:
    lines = markdown_text.splitlines()
    if lines and lines[0].strip() == "---":
        for ln in lines[1:25]:
            s = ln.strip()
            if s == "---":
                break
            if s.lower().startswith("name:"):
                val = s.split(":", 1)[1].strip().strip('"').strip("'")
                if val:
                    return val
    return ""


def _inject_provenance_comment(markdown_text: str, source_url: str) -> str:
    marker = f"<!-- maru-imported-from: {source_url} -->"
    if "maru-imported-from:" in markdown_text:
        return markdown_text
    return markdown_text.rstrip() + f"\n\n{marker}\n"


class GitHubSkillImporter:
    """Pengunduh & pemasang SKILL.md dari GitHub ke repositori MARU AI."""

    def __init__(
        self,
        config: GitHubSyncConfig,
        urlopen_fn: Callable[..., Any] | None = None,
    ) -> None:
        self.config = config
        self._urlopen = urlopen_fn or urllib.request.urlopen

    def _headers(self, accept_raw: bool = False) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github.raw+json" if accept_raw else "application/vnd.github+json",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "maru-ai-skill-importer/1.0",
        }
        if self.config.token:
            headers["Authorization"] = f"Bearer {self.config.token}"
        return headers

    def _get_json(self, url: str) -> Any:
        req = urllib.request.Request(url, headers=self._headers(), method="GET")
        try:
            with self._urlopen(req, timeout=self.config.timeout_sec) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = exc.read().decode("utf-8", errors="replace")[:300]
            raise GitHubSyncError(
                f"Gagal mengambil metadata skill ({exc.code}): {redact_secret(detail, self.config.token)}"
            ) from None
        except Exception as exc:
            raise GitHubSyncError(
                f"Gagal menghubungi GitHub: {redact_secret(str(exc), self.config.token)}"
            ) from None

    def _get_text(self, url: str, use_auth: bool = False) -> str:
        headers = self._headers(accept_raw=True) if use_auth else {"User-Agent": "maru-ai-skill-importer/1.0"}
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with self._urlopen(req, timeout=self.config.timeout_sec) as resp:
                return resp.read().decode("utf-8")
        except Exception as exc:
            raise GitHubSyncError(
                f"Gagal mengunduh konten SKILL.md: {redact_secret(str(exc), self.config.token)}"
            ) from None

    def fetch_skill_markdown(self, source: str) -> tuple[str, str, str]:
        """Return (inferred_name, skill_markdown, canonical_source_url)."""
        parsed = parse_github_skill_source(source)

        if parsed.kind == "raw":
            text = self._get_text(parsed.raw_url, use_auth=False)
            parent_name = Path(parsed.path).parent.name or Path(parsed.path).stem
            inferred = _extract_frontmatter_name(text) or (
                parsed.repo if parent_name.lower() in ("", ".", "skills") else parent_name
            )
            return slugify_skill_name(inferred), text, parsed.raw_url

        api_base = self.config.api_base
        ref = parsed.ref
        if not ref:
            repo_meta = self._get_json(f"{api_base}/repos/{parsed.owner}/{parsed.repo}")
            ref = str(repo_meta.get("default_branch") or "main")

        # Jika menunjuk ke file langsung (.md)
        if parsed.kind == "blob" or parsed.path.lower().endswith(".md"):
            clean_path = urllib.parse.quote(parsed.path.lstrip("/"), safe="/")
            ref_q = urllib.parse.quote(ref, safe="")
            api_url = f"{api_base}/repos/{parsed.owner}/{parsed.repo}/contents/{clean_path}?ref={ref_q}"
            text = self._get_text(api_url, use_auth=True)
            stem = Path(parsed.path).stem
            parent = Path(parsed.path).parent.name
            fallback_name = parent if stem.upper() == "SKILL" and parent else stem
            inferred = _extract_frontmatter_name(text) or fallback_name or parsed.repo
            canonical = f"https://github.com/{parsed.owner}/{parsed.repo}/blob/{ref}/{parsed.path}"
            return slugify_skill_name(inferred), text, canonical

        # Jika menunjuk ke folder / root repo: cari SKILL.md (atau README.md sebagai fallback)
        folder = parsed.path.strip("/")
        folder_q = urllib.parse.quote(folder, safe="/")
        ref_q = urllib.parse.quote(ref, safe="")
        contents_url = (
            f"{api_base}/repos/{parsed.owner}/{parsed.repo}/contents/{folder_q}?ref={ref_q}"
            if folder
            else f"{api_base}/repos/{parsed.owner}/{parsed.repo}/contents?ref={ref_q}"
        )
        listing = self._get_json(contents_url)
        if isinstance(listing, dict) and listing.get("type") == "file":
            dl_url = f"{api_base}/repos/{parsed.owner}/{parsed.repo}/contents/{folder_q}?ref={ref_q}"
            text = self._get_text(dl_url, use_auth=True)
            inferred = _extract_frontmatter_name(text) or Path(folder).stem or parsed.repo
            canonical = f"https://github.com/{parsed.owner}/{parsed.repo}/blob/{ref}/{folder}"
            return slugify_skill_name(inferred), text, canonical

        if not isinstance(listing, list):
            raise GitHubSyncError(f"Tidak menemukan daftar file skill di {source}")

        chosen_item = None
        for candidate_name in ("SKILL.md", "skill.md", "README.md"):
            chosen_item = next(
                (it for it in listing if str(it.get("name", "")) == candidate_name and it.get("type") == "file"),
                None,
            )
            if chosen_item:
                break

        if not chosen_item:
            md_files = [
                it for it in listing if it.get("type") == "file" and str(it.get("name", "")).lower().endswith(".md")
            ]
            if len(md_files) == 1:
                chosen_item = md_files[0]

        if not chosen_item:
            subfolders = [it.get("path") for it in listing if it.get("type") == "dir"][:8]
            hint = f" Subfolder yang tersedia: {', '.join(str(s) for s in subfolders)}" if subfolders else ""
            raise GitHubSyncError(
                f"File SKILL.md tidak ditemukan di '{folder or '/'}' pada {parsed.owner}/{parsed.repo}.{hint}"
            )

        item_path = str(chosen_item["path"])
        item_q = urllib.parse.quote(item_path, safe="/")
        api_file_url = f"{api_base}/repos/{parsed.owner}/{parsed.repo}/contents/{item_q}?ref={ref_q}"
        text = self._get_text(api_file_url, use_auth=True)
        folder_leaf = Path(folder).name if folder else parsed.repo
        inferred = _extract_frontmatter_name(text) or folder_leaf
        canonical = f"https://github.com/{parsed.owner}/{parsed.repo}/blob/{ref}/{item_path}"
        return slugify_skill_name(inferred), text, canonical

    def install_skill(
        self,
        source: str,
        *,
        division: str = "shared",
        custom_name: str | None = None,
    ) -> dict[str, Any]:
        """Unduh skill dari GitHub lalu pasang ke folder `skills/<division>/<slug>/SKILL.md`."""
        if division not in VALID_DIVISIONS:
            raise ValueError(f"Divisi tidak valid: {division}. Pilih salah satu: {VALID_DIVISIONS}")

        inferred_slug, text, canonical_url = self.fetch_skill_markdown(source)
        slug = slugify_skill_name(custom_name) if custom_name else inferred_slug
        final_text = _inject_provenance_comment(text, canonical_url)

        dest = self.config.repo_root / "skills" / division / slug / "SKILL.md"
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_text(final_text, encoding="utf-8")

        return {
            "ok": True,
            "skill_id": f"{division}/{slug}",
            "division": division,
            "name": slug,
            "local_path": str(dest.relative_to(self.config.repo_root)).replace("\\", "/"),
            "source_url": canonical_url,
        }
