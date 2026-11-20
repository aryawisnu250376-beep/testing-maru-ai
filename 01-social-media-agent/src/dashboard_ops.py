"""Storage and provider adapters for the authenticated Corporate HQ dashboard."""
from __future__ import annotations

import json
import os
import uuid
from urllib.parse import urlsplit
from pathlib import Path

from . import db, queue4
from .config import ROOT, load_config, out_dir
from .hq.agents import get_agent_profile
from .llm import LLM


def _prepare(conn):
    conn.execute('''CREATE TABLE IF NOT EXISTS dashboard_records (
        id INTEGER PRIMARY KEY, kind TEXT NOT NULL, body TEXT NOT NULL)''')


def _append(kind: str, *records: dict) -> None:
    with db.conn() as conn:
        _prepare(conn)
        conn.executemany('INSERT INTO dashboard_records(kind,body) VALUES (?,?)',
                         [(kind, json.dumps(row, ensure_ascii=False)) for row in records])


def records(kind: str, limit: int = 60) -> list[dict]:
    with db.conn() as conn:
        _prepare(conn)
        rows = conn.execute('SELECT body FROM dashboard_records WHERE kind=? ORDER BY id DESC LIMIT ?',
                            (kind, limit)).fetchall()
    return [json.loads(row[0]) for row in reversed(rows)]


def safe_url(value) -> str:
    if not isinstance(value, str) or not value or len(value) > 2048 or any(c.isspace() for c in value):
        return ''
    try:
        url = urlsplit(value)
        if url.scheme in ('https', 'http') and url.hostname and not url.username and not url.password:
            return value
    except ValueError:
        pass
    return ''


def watchlist(limit: int | None = None, offset: int = 0) -> list[dict]:
    source = Path(os.getenv('REFERENCE_WATCHLIST', str(ROOT / 'data' / 'reference_watchlist.json')))
    try:
        original = json.loads(source.read_text(encoding='utf8'))
    except (OSError, ValueError):
        original = []
    if isinstance(original, dict):
        original = original.get("items", [])
    original = original if isinstance(original, list) else []
    items = list({row['url']: row for row in [*original, *records('watchlist', -1)]
                  if isinstance(row, dict) and safe_url(row.get('url'))}.values())
    return items[offset:] if limit is None else items[offset:offset+limit]


def add_watchlist(payload: dict) -> dict:
    url = safe_url(payload.get('url'))
    if not url:
        raise ValueError('Gunakan URL referensi HTTP(S) yang valid.')
    _append('watchlist', {'url': url, 'catatan': str(payload.get('catatan') or '')[:500],
                          'transcript': str(payload.get('transcript') or '')[:3000]})
    return {'ok': True}


def text(payload: dict, field: str, length: int) -> str:
    raw = payload.get(field)
    if not isinstance(raw, str) or not raw.strip() or len(raw.strip()) > length:
        raise ValueError(f'{field} wajib diisi (maksimum {length} karakter).')
    return raw.strip()


def provider_text(llm, system: str, prompt: str, *, history=()) -> str:
    if not llm.available:
        raise RuntimeError('Provider AI belum dikonfigurasi.')
    try:
        output = llm.chat([{'role': 'system', 'content': system}, *history, {'role': 'user', 'content': prompt}])
    except Exception as exc:
        raise RuntimeError('Provider AI tidak dapat dihubungi atau gagal menjawab.') from exc
    if not output or not output.strip():
        raise RuntimeError('Provider AI mengembalikan jawaban kosong.')
    return output.strip()


def chat(llm, payload: dict) -> dict:
    prompt = text(payload, 'prompt', 3000)
    bot_id = str(payload.get('bot_id') or 'EMP-L02')
    profile = get_agent_profile(bot_id)
    if not profile:
        raise ValueError('Agen chat tidak dikenal.')
    with db.conn() as conn:
        _prepare(conn)
        rows = conn.execute("SELECT body FROM dashboard_records WHERE kind='chat' AND json_extract(body,'$.bot_id')=? ORDER BY id DESC LIMIT 12", (bot_id,)).fetchall()
    history = [{'role': row['role'], 'content': row['text'][:1200]} for row in
               (json.loads(r[0]) for r in reversed(rows)) if row['role'] in ('user', 'assistant')]
    answer = provider_text(llm, profile.system_prompt + ' Jawab dalam bahasa Indonesia. Jangan klaim telah menjalankan tindakan eksternal.', prompt, history=history)
    _append('chat', {'role': 'user', 'bot_id': bot_id, 'bot_name': 'Pemilik', 'text': prompt},
            {'role': 'assistant', 'bot_id': bot_id, 'bot_name': profile.name, 'text': answer})
    return {'ok': True}


def draft(llm, payload: dict) -> dict:
    topic = text(payload, 'topic', 120)
    notes = str(payload.get('notes') or '')[:3000]
    script = provider_text(llm, 'Tulis naskah video pendek bahasa Indonesia. Ini draf untuk persetujuan manusia. Jangan mengarang sumber atau hasil riset.',
                           f'Topik: {topic}\nCatatan pemilik: {notes}')
    key = 'k-' + uuid.uuid4().hex[:14]
    queue4.create(key, topic, naskah=script, actor='hermes')
    queue4.transition(key, 'MENUNGGU', 'hermes', 'Draf dari provider AI; perlu ditinjau pemilik.')
    return {'content_id': key}


def approved_video(episode_id: str) -> Path:
    """Resolve the actual approved/rendered episode, not a client-supplied path or QC flag."""
    from . import approve
    if not queue4.SAFE_ID.fullmatch(episode_id) or episode_id in ('.', '..'):
        raise ValueError('ID episode tidak valid.')
    episode = db.get_episode(episode_id)
    if not episode:
        raise ValueError('Episode tidak ditemukan.')
    approve.require_approval(episode_id, episode['script'])
    video_path = (episode.get('paths') or {}).get('video')
    if not video_path:
        raise ValueError('Render episode belum tersedia.')
    video = Path(video_path).resolve()
    if not video.is_relative_to(out_dir(episode_id).resolve()) or not video.is_file():
        raise ValueError('Artefak video episode tidak valid.')
    qc_path = video.parent / 'qc_report.json'
    if not qc_path.is_file():
        raise ValueError('Laporan QC belum tersedia.')
    qc = json.loads(qc_path.read_text(encoding='utf-8'))
    if not isinstance(qc, dict) or not qc.get('video') or Path(qc['video']).resolve() != video or qc.get('passed') is not True or qc_path.stat().st_mtime_ns < video.stat().st_mtime_ns:
        raise ValueError('Video belum lulus QC yang berlaku.')
    return video


def attach_approved_video(payload: dict) -> dict:
    if payload.get('confirmed') is not True:
        raise ValueError('Konfirmasi pemilik bahwa video sesuai dengan konten diperlukan.')
    content_id = text(payload, 'content_id', 100)
    episode_id = text(payload, 'episode_id', 100)
    video = approved_video(episode_id)
    return queue4.transition(content_id, 'DISETUJUI', 'pemilik', 'Pemilik menautkan video episode dengan QC lulus',
                             expected_status='DISETUJUI', episode_id=episode_id, video=str(video), qc_passed=True,
                             verified_episode_video=True)


def execute_hq_job(job, token) -> dict:
    """Module-level handler for process-isolated HQWorker; model output is advisory only."""
    token.check()
    profile = get_agent_profile(job.assigned_agent)
    if not profile or profile.division != job.division:
        raise ValueError('Agen HQ tidak cocok dengan divisi tugas.')
    prompt = json.dumps({'goal': job.goal, 'criteria': job.acceptance_criteria, 'input': job.input_payload},
                        ensure_ascii=False)
    result = provider_text(LLM.from_config(load_config()), profile.system_prompt +
                           ' Hasil ini adalah rekomendasi; keputusan final tetap di HQ. Jangan klaim tindakan eksternal.', prompt)
    token.check()
    return {'recommendation': result, 'requires_hq_review': True}
