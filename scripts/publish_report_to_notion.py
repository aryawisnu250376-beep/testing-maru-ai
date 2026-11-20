#!/usr/bin/env python3
"""Stage immutable GitHub report blobs and publish to an existing Notion data source."""
from __future__ import annotations

import base64
import binascii
import datetime as dt
import hashlib
import json
import os
import re
import sys
import urllib.error
import urllib.request
import uuid
from pathlib import Path

API_GITHUB = "https://api.github.com"
API_NOTION = "https://api.notion.com/v1"
NOTION_VERSION = "2025-09-03"
MAX_BYTES = 64 * 1024
MAX_REPORTS = 8
MAX_BLOCKS = 100
MAX_REPLY = 4 * 1024 * 1024
SHA = re.compile(r"[a-f0-9]{40}")
REPO = re.compile(r"[A-Za-z0-9][A-Za-z0-9-]*/[A-Za-z0-9_][A-Za-z0-9_.-]*")
PART = r"[A-Za-z0-9][A-Za-z0-9_-]{0,79}"
REPORT = re.compile(rf"docs/reports/(?:{PART}/){{0,3}}{PART}\.md")
SAFE_ERROR_CODES = {
    "invalid_json", "invalid_request_url", "invalid_request", "validation_error",
    "missing_version", "unauthorized", "restricted_resource", "object_not_found",
    "conflict_error", "rate_limited", "internal_server_error", "service_unavailable",
}
SECRET_PATTERNS = tuple(map(re.compile, (
    r"(?i)-----BEGIN (?:[A-Z0-9]+ )*PRIVATE KEY-----",
    r"\b(?:github_pat_[A-Za-z0-9_]{12,}|gh[pousr]_[A-Za-z0-9]{20,})\b",
    r"\b(?:ntn|secret)_[A-Za-z0-9]{20,}\b",
    r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",
    r"\b(?:sk-(?:proj-)?[A-Za-z0-9_-]{20,}|xox[baprs]-[A-Za-z0-9-]{12,}|AIza[A-Za-z0-9_-]{35})\b",
    r"(?im)\b(?:authorization\s*:\s*bearer|(?:api[_ -]?key|access[_ -]?token|notion_token|password|secret)\s*[:=])\s*['\"]?[A-Za-z0-9_./+=-]{12,}",
    r"\beyJ[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\.[A-Za-z0-9_-]+\b",
)))


class ReportError(Exception):
    """Error safe to print without disclosing report or credential content."""


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def request_json(service, method, path, token, payload=None, *, opener=None):
    base = {"GitHub": API_GITHUB, "Notion": API_NOTION}[service]
    headers = {"Authorization": f"Bearer {token}", "User-Agent": "maru-report-pipeline"}
    headers["Content-Type"] = "application/json"
    if service == "Notion":
        headers["Notion-Version"] = NOTION_VERSION
    else:
        headers["Accept"] = "application/vnd.github+json"
        headers["X-GitHub-Api-Version"] = "2022-11-28"
    data = json.dumps(payload, ensure_ascii=False).encode() if payload is not None else None
    req = urllib.request.Request(base + path, data=data, headers=headers, method=method)
    opener = opener or urllib.request.build_opener(NoRedirect()).open
    create = service == "Notion" and method == "POST" and path == "/pages"
    ambiguous = " Check Source URL in Agent Documents before replaying; do not retry blindly." if create else ""
    try:
        with opener(req, timeout=15) as response:
            if service == "GitHub" and "/commits/" in path and 'rel="next"' in response.headers.get("Link", ""):
                raise ReportError("GitHub changed-file list is paginated; use a small report commit at the tip.")
            raw = response.read(MAX_REPLY + 1)
            if len(raw) > MAX_REPLY:
                raise ValueError("response too large")
            result = json.loads(raw)
            if not isinstance(result, dict):
                raise ValueError("response not an object")
            return result
    except urllib.error.HTTPError as exc:
        error_code = None
        if service == "Notion":
            try:
                value = json.loads(exc.read(4096)).get("code")
                if isinstance(value, str) and value in SAFE_ERROR_CODES:
                    error_code = value
            except (ValueError, AttributeError, OSError):
                pass
        detail = f" ({error_code})" if error_code else ""
        hint = ambiguous if exc.code >= 500 or exc.code in {408, 409, 429} else ""
        raise ReportError(f"{service} {method} HTTP {exc.code}{detail}.{hint}") from None
    except (OSError, ValueError):
        raise ReportError(f"{service} {method} failed: transport error or invalid JSON.{ambiguous}") from None


def validate_report_path(path):
    if not isinstance(path, str) or not REPORT.fullmatch(path) or path.casefold() == "docs/reports/readme.md":
        raise ReportError("Expected a Markdown report in docs/reports/ (README is not a report).")
    return path


def validate_source(repo, commit):
    if not REPO.fullmatch(repo) or not SHA.fullmatch(commit):
        raise ReportError("Expected repository owner/name and a full lowercase 40-character commit SHA.")


def source_permalink(repo, commit, path):
    validate_source(repo, commit)
    return f"https://github.com/{repo}/blob/{commit}/{validate_report_path(path)}"


def scan_credentials(raw):
    if any(pattern.search(raw) for pattern in SECRET_PATTERNS):
        raise ReportError("Possible credential in report; no matching text was logged.")


def parse_frontmatter(raw):
    raw = raw.replace("\r\n", "\n")
    lines = raw.split("\n")
    if not lines or lines[0] != "---":
        raise ReportError("Required report frontmatter is missing.")
    try:
        end = lines.index("---", 1)
    except ValueError:
        raise ReportError("Frontmatter is not closed with an exact --- line.") from None
    metadata = {}
    for line in lines[1:end]:
        if not line.strip() or line.startswith("#"):
            continue
        key, sep, value = line.partition(":")
        value = value.strip()
        if not sep or key not in {"title", "date", "status"} or key in metadata or not value:
            raise ReportError("Frontmatter supports unique title, date and status scalar fields only.")
        if value[0] in {"'", '"'}:
            if len(value) < 2 or value[-1] != value[0]:
                raise ReportError("Unbalanced quotes in frontmatter.")
            value = value[1:-1]
        metadata[key] = value
    date = metadata.get("date", "")
    try:
        if dt.date.fromisoformat(date).isoformat() != date:
            raise ValueError
    except ValueError:
        raise ReportError("Frontmatter date must be a valid YYYY-MM-DD.") from None
    title = metadata.get("title", "").strip()
    if not title or len(title.encode("utf-16-le")) > 400:
        raise ReportError("Frontmatter title is required and limited to 200 UTF-16 units.")
    metadata["title"] = title
    metadata.setdefault("status", "Draft")
    if metadata["status"] not in {"Draft", "Active"}:
        raise ReportError("Frontmatter status must be Draft or Active.")
    return metadata, "\n".join(lines[end + 1:])


def rich_text(text):
    # 900 Unicode code points never exceed Notion's 2000-unit limit, including emoji.
    return [{"type": "text", "text": {"content": text[i:i+900]}} for i in range(0, len(text), 900)]


def markdown_to_blocks(markdown):
    blocks, paragraph, code = [], [], []
    fence = None

    def emit(kind, text):
        block = {"rich_text": rich_text(text)}
        if kind == "code":
            block["language"] = "plain text"
        blocks.append({"type": kind, kind: block})
        if len(blocks) > MAX_BLOCKS:
            raise ReportError("Report exceeds the Notion block limit; split it before publishing.")

    def flush():
        if paragraph:
            emit("paragraph", "\n".join(paragraph))
            paragraph.clear()

    for line in markdown.splitlines():
        stripped = line.strip()
        if fence is not None:
            if re.fullmatch(re.escape(fence[0]) + "{" + str(len(fence)) + ",}", stripped):
                emit("code", "\n".join(code))
                code.clear()
                fence = None
            else:
                code.append(line)
            continue
        opening = re.match(r"^(`{3,}|~{3,})", stripped)
        if opening:
            flush()
            fence = opening[1]
            continue
        if not stripped:
            flush()
            continue
        for pattern, kind in ((r"^(#{1,3})\s+(.+)$", "heading"),
                              (r"^[-*+]\s+(.+)$", "bulleted_list_item"),
                              (r"^\d+[.)]\s+(.+)$", "numbered_list_item"),
                              (r"^>\s?(.*)$", "quote")):
            match = re.fullmatch(pattern, stripped)
            if match:
                flush()
                emit(f"heading_{len(match[1])}" if kind == "heading" else kind, match.groups()[-1])
                break
        else:
            paragraph.append(line)
    if fence is not None:
        raise ReportError("Report contains an unclosed Markdown code fence.")
    flush()
    if not blocks:
        raise ReportError("Report body is empty.")
    return blocks


def prepare(raw):
    if len(raw) > MAX_BYTES:
        raise ReportError("Report exceeds 64 KiB.")
    scan_credentials(raw.decode("utf-8"))
    metadata, body = parse_frontmatter(raw.decode("utf-8-sig"))
    return metadata, markdown_to_blocks(body)


def github_reports(repo, commit, github):
    validate_source(repo, commit)
    root = f"/repos/{repo}"
    commit_data = github("GET", f"{root}/commits/{commit}?per_page=100")
    if commit_data.get("sha") != commit or not isinstance(commit_data.get("files"), list):
        raise ReportError("GitHub did not return the expected commit and changed-file list.")
    files = commit_data["files"]
    # Never silently process a partial GitHub commit diff.
    if len(files) >= 100:
        raise ReportError("Commit has 100 or more changed paths; push a small report commit at the tip.")
    paths = []
    for row in files:
        name = row.get("filename", "")
        if not name.startswith("docs/reports/") or not name.lower().endswith(".md"):
            continue
        if name.casefold() == "docs/reports/readme.md" or row.get("status") == "removed":
            continue
        paths.append(validate_report_path(name))
    if len(paths) > MAX_REPORTS or len(set(paths)) != len(paths):
        raise ReportError("Commit contains too many or duplicate report paths.")
    if not paths:
        return {}
    trees = {}

    def entry_at(tree_sha, path):
        segments = path.split("/")
        for i, segment in enumerate(segments):
            if not isinstance(tree_sha, str) or not SHA.fullmatch(tree_sha):
                raise ReportError("GitHub returned an invalid Git tree identifier.")
            if tree_sha not in trees:
                response = github("GET", f"{root}/git/trees/{tree_sha}")
                if response.get("sha") != tree_sha or response.get("truncated") is not False:
                    raise ReportError("GitHub returned an incomplete Git tree.")
                trees[tree_sha] = response["tree"]
            matches = [row for row in trees[tree_sha] if row.get("path") == segment]
            if len(matches) != 1:
                raise ReportError("Changed path is not present in the expected Git tree.")
            entry = matches[0]
            if i == len(segments) - 1:
                return entry
            if entry.get("type") != "tree" or entry.get("mode") != "040000":
                raise ReportError("A report path parent is not a Git directory.")
            tree_sha = entry.get("sha")

    reports = {}
    for path in paths:
        entry = entry_at(commit_data["commit"]["tree"]["sha"], path)
        size = entry.get("size")
        sha = entry.get("sha", "")
        if entry.get("type") != "blob" or entry.get("mode") != "100644" or not SHA.fullmatch(sha):
            raise ReportError("Git report must be a regular non-executable blob (no symlink or submodule).")
        if not isinstance(size, int) or not 0 < size <= MAX_BYTES:
            raise ReportError("Git report size is outside the permitted range.")
        blob = github("GET", f"{root}/git/blobs/{sha}")
        if blob.get("sha") != sha or blob.get("encoding") != "base64" or blob.get("size") != size:
            raise ReportError("GitHub blob metadata does not match its Git tree entry.")
        data = base64.b64decode("".join(blob["content"].split()), validate=True)
        if len(data) != size or hashlib.sha1(f"blob {size}\0".encode() + data).hexdigest() != sha:
            raise ReportError("GitHub blob failed integrity check.")
        prepare(data)
        reports[path] = data
    return reports


def schema_status_kind(schema, statuses):
    props = schema.get("properties", {})
    for key, kind in {"Name": "title", "Source URL": "url", "Type": "select", "Date": "date"}.items():
        if props.get(key, {}).get("type") != kind:
            raise ReportError("Agent Documents needs Name (title), Source URL (url), Type (select) and Date (date).")
    if "Document" not in {x.get("name") for x in props["Type"]["select"].get("options", [])}:
        raise ReportError("Agent Documents Type must already offer the Document option.")
    kind = props.get("Status", {}).get("type")
    if kind not in {"select", "status"} or not statuses <= {
        row.get("name") for row in props["Status"][kind].get("options", [])
    }:
        raise ReportError("Agent Documents Status options do not match the requested status.")
    return kind


def verify_page(notion, page_id, source_id, metadata, link, kind, blocks):
    page_id = str(uuid.UUID(page_id))
    page = notion("GET", f"/pages/{page_id}")
    props = page.get("properties", {})
    title = "".join(x.get("plain_text", "") for x in (props.get("Name", {}).get("title") or []))
    parent_id = page.get("parent", {}).get("data_source_id", "")
    if (page.get("id") != page_id or parent_id != source_id or page.get("archived") or page.get("in_trash")
            or props.get("Source URL", {}).get("url") != link or title != metadata["title"]
            or (props.get("Type", {}).get("select") or {}).get("name") != "Document"
            or (props.get("Status", {}).get(kind) or {}).get("name") != metadata["status"]
            or (props.get("Date", {}).get("date") or {}).get("start") != metadata["date"]):
        raise ReportError("Notion read-back mismatch in document properties. Do not create a duplicate.")
    result = notion("GET", f"/blocks/{page_id}/children?page_size=100")
    wanted = [(b["type"], "".join(t["text"]["content"] for t in b[b["type"]]["rich_text"])) for b in blocks]
    found = [(b["type"], "".join(t.get("plain_text", "") for t in b[b["type"]]["rich_text"]))
             for b in result.get("results", [])]
    if result.get("has_more") is not False or found != wanted:
        raise ReportError("Notion read-back mismatch in document blocks. Do not create a duplicate.")
    return f"https://www.notion.so/{page_id.replace('-', '')}"


def publish_report(notion, source_id, repo, commit, path, metadata, blocks, kind):
    link = source_permalink(repo, commit, path)
    existing = notion("POST", f"/data_sources/{source_id}/query", {
        "filter": {"property": "Source URL", "url": {"equals": link}}, "page_size": 2,
    })
    matches = existing.get("results")
    if not isinstance(matches, list) or existing.get("has_more") is not False or len(matches) > 1:
        raise ReportError("Notion returned an incomplete or duplicate Source URL lookup; no page was created.")
    if matches:
        page = matches[0]
    else:
        page = notion("POST", "/pages", {
            "parent": {"type": "data_source_id", "data_source_id": source_id},
            "properties": {
                "Name": {"title": rich_text(metadata["title"])}, "Source URL": {"url": link},
                "Type": {"select": {"name": "Document"}}, "Status": {kind: {"name": metadata["status"]}},
                "Date": {"date": {"start": metadata["date"]}},
            },
            "children": blocks,
        })
    try:
        page_url = verify_page(notion, page["id"], source_id, metadata, link, kind, blocks)
    except ReportError as exc:
        raise ReportError(f"Notion verification failed: {exc} Check Source URL before replaying.") from None
    except (TypeError, KeyError, ValueError, AttributeError):
        raise ReportError("Notion verification failed: malformed read-back. Check Source URL before replaying.") from None
    return {"status": "already_published" if matches else "published", "page_url": page_url, "source_url": link}


def main():
    if len(sys.argv) == 3 and sys.argv[1] == "validate":
        path = Path(validate_report_path(sys.argv[2]))
        if path.absolute() != path.resolve() or not path.is_file():
            raise ReportError("Local report must be a regular file without symlink components.")
        with path.open("rb") as report:
            prepare(report.read(MAX_BYTES + 1))
        print("Report validation passed.")
        return
    if sys.argv[1:] not in (["stage"], ["publish"]):
        raise ReportError("Usage: publish_report_to_notion.py stage|publish|validate <report>")
    repo, commit = os.getenv("GITHUB_REPOSITORY", ""), os.getenv("REPORT_SHA", "")
    validate_source(repo, commit)
    stage = Path(os.environ["RUNNER_TEMP"]) / "maru-arena-reports" / "reports.json"
    if sys.argv[1] == "stage":
        token = os.environ["REPORT_GITHUB_TOKEN"]
        reports = github_reports(repo, commit, lambda method, path: request_json("GitHub", method, path, token))
        stage.parent.mkdir(mode=0o700)
        stage.write_text(json.dumps({"repo": repo, "commit": commit, "reports": {
            p: base64.b64encode(b).decode() for p, b in reports.items()}}), encoding="utf-8")
        print(f"Validated {len(reports)} immutable report(s).")
        return
    document = json.loads(stage.read_text(encoding="utf-8"))
    if document["repo"] != repo or document["commit"] != commit:
        raise ReportError("Staged reports are not bound to this workflow's commit.")
    reports = {validate_report_path(p): prepare(base64.b64decode(b, validate=True))
               for p, b in document["reports"].items()}
    if not reports:
        print("No publishable report changes at the tip of this push.")
        return
    source_id = str(uuid.UUID(os.environ["NOTION_DATA_SOURCE_ID"]))
    token = os.environ["NOTION_TOKEN"]
    if not token.strip():
        raise ReportError("Set NOTION_TOKEN in the protected publisher environment.")
    notion = lambda method, path, payload=None: request_json("Notion", method, path, token, payload)
    schema = notion("GET", f"/data_sources/{source_id}")
    if schema.get("id") != source_id:
        raise ReportError("Notion returned the wrong data source.")
    kind = schema_status_kind(schema, {meta["status"] for meta, _ in reports.values()})
    for path, (meta, blocks) in reports.items():
        print(json.dumps(publish_report(notion, source_id, repo, commit, path, meta, blocks, kind)))


if __name__ == "__main__":
    try:
        main()
    except ReportError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)
    except (KeyError, ValueError, TypeError, AttributeError, OSError, binascii.Error):
        print("ERROR: Missing configuration, invalid UTF-8, malformed data, or local I/O failure.", file=sys.stderr)
        sys.exit(1)
