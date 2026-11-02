from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import parse_qs, urlparse

VIDEO_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]{11}$")


class InvalidYouTubeUrl(ValueError):
    """The input is not a supported YouTube video URL."""


class YouTubeCaptionsUnavailable(RuntimeError):
    """Public captions could not be fetched for a video."""


@dataclass(frozen=True)
class PublicCaptions:
    video_id: str
    url: str
    text: str
    language: str
    truncated: bool


def extract_video_id(url: str) -> str:
    """Extract a video ID without fetching arbitrary URLs."""
    parsed = urlparse(url.strip())
    hostname = (parsed.hostname or "").lower().removeprefix("www.")
    allowed_hosts = {"youtube.com", "m.youtube.com", "youtu.be", "youtube-nocookie.com"}
    if parsed.scheme not in {"http", "https"} or hostname not in allowed_hosts:
        raise InvalidYouTubeUrl("Masukkan URL video YouTube yang valid.")

    video_id = ""
    if hostname == "youtu.be":
        video_id = parsed.path.strip("/").split("/", 1)[0]
    elif parsed.path.rstrip("/") == "/watch":
        video_id = parse_qs(parsed.query).get("v", [""])[0]
    else:
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2 and parts[0] in {"shorts", "embed", "live"}:
            video_id = parts[1]

    if not VIDEO_ID_PATTERN.fullmatch(video_id):
        raise InvalidYouTubeUrl("URL tidak memuat ID video YouTube yang valid.")
    return video_id


def _timestamp(seconds: float) -> str:
    total = max(0, int(seconds))
    hours, remainder = divmod(total, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def fetch_public_captions(url: str, *, max_chars: int = 60_000) -> PublicCaptions:
    """Fetch public captions only. This intentionally never downloads video/audio."""
    video_id = extract_video_id(url)
    canonical_url = f"https://www.youtube.com/watch?v={video_id}"
    try:
        from youtube_transcript_api import YouTubeTranscriptApi

        transcript_list = YouTubeTranscriptApi().list(video_id)
        try:
            transcript = transcript_list.find_transcript(["id", "en"])
        except Exception:
            # Captions can be public in a language other than Indonesian or English.
            transcript = next(iter(transcript_list), None)
        if transcript is None:
            raise YouTubeCaptionsUnavailable
        fetched = transcript.fetch()
    except YouTubeCaptionsUnavailable:
        raise
    except Exception as exc:
        raise YouTubeCaptionsUnavailable from exc

    limit = max(1, int(max_chars))
    lines: list[str] = []
    used_chars = 0
    truncated = False
    for snippet in fetched:
        text = str(getattr(snippet, "text", "") or "").replace("\n", " ").strip()
        if not text:
            continue
        start = float(getattr(snippet, "start", 0.0) or 0.0)
        prefix = f"[{_timestamp(start)}] "
        line = prefix + text
        separator_chars = 1 if lines else 0
        remaining = limit - used_chars - separator_chars
        if len(line) > remaining:
            text_budget = remaining - len(prefix)
            if text_budget > 0:
                lines.append(prefix + text[:text_budget])
                used_chars = limit
            truncated = True
            break
        lines.append(line)
        used_chars += len(line) + separator_chars
        if used_chars >= limit:
            truncated = True
            break

    text = "\n".join(lines).strip()
    if not text:
        raise YouTubeCaptionsUnavailable
    language = str(
        getattr(transcript, "language_code", "") or getattr(transcript, "language", "") or "unknown"
    )
    return PublicCaptions(
        video_id=video_id,
        url=canonical_url,
        text=text,
        language=language,
        truncated=truncated,
    )
