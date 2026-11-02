"""MCP SERVER (stdio, JSON-RPC 2.0) — supaya Hermes / Claude Desktop / agent lain
bisa memanggil pipeline ini sebagai *tool* resmi, tanpa scraping shell.

Kenapa MCP dan bukan cuma shell:
  - agent tahu skema parameter (tidak menebak)
  - hasil terstruktur, bukan teks bebas yang harus diparse ulang
  - izin per-tool bisa diatur di sisi agent

Dipakai:
    python -m src.mcp_server            # stdio transport

Contoh konfigurasi Hermes (config.yml):
    mcp_servers:
      konten-ai:
        command: python
        args: ["-m", "src.mcp_server"]
        cwd: "/home/user/ai-edukasi-agent"

Protokol yang diimplementasi: initialize, tools/list, tools/call, ping.
"""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOCOL_VERSION = "2024-11-05"


def _schema(props: dict | None = None, required: list[str] | None = None) -> dict:
    return {"type": "object", "properties": props or {}, "required": required or []}


TOOLS: list[dict] = [
    {
        "name": "scan_trends",
        "description": "Pindai sumber trend AI (Hacker News, HuggingFace, GitHub, Google Trends, "
                       "YouTube bila ada key) dan kembalikan tema yang layak jadi video edukasi "
                       "60 detik, lengkap dengan skor dan bukti sumber.",
        "inputSchema": _schema(),
        "cmd": ["-m", "src.cli", "scan", "--json"],
        "dangerous": False,
    },
    {
        "name": "list_topics",
        "description": "Ambil daftar tema hasil scan terakhir (tanpa memindai ulang).",
        "inputSchema": _schema(),
        "cmd": ["-m", "src.cli", "scan", "--json"],
        "dangerous": False,
    },
    {
        "name": "write_script",
        "description": "Tulis script video dari satu tema: hook, 5-7 beat, spec visual, caption, "
                       "hashtag, dan sumber. Hasil selalu divalidasi aturan editorial.",
        "inputSchema": _schema({"theme": {"type": "string",
                                         "description": "id tema dari scan_trends (opsional)"}}),
        "cmd": ["-m", "src.cli", "script", "--json"],
        "arg_map": {"theme": "--theme"},
        "dangerous": False,
    },
    {
        "name": "request_approval",
        "description": "Kirim script ke user (Telegram/CLI) untuk ACC. Wajib dipanggil sebelum "
                       "render_video. Render akan DITOLAK kalau belum di-ACC.",
        "inputSchema": _schema({"episode_id": {"type": "string"},
                                "wait_sec": {"type": "integer",
                                             "description": "detik menunggu balasan, 0 = tidak menunggu"}},
                               ["episode_id"]),
        "cmd": ["-m", "src.cli", "approve", "{episode_id}", "--json"],
        "arg_map": {"wait_sec": "--wait"},
        "dangerous": False,
    },
    {
        "name": "render_video",
        "description": "Render MP4 1080x1920 dengan animasi + dubbing Indonesia + caption sinkron. "
                       "Hanya berjalan kalau episode sudah di-ACC.",
        "inputSchema": _schema({"episode_id": {"type": "string"},
                                "voice": {"type": "string",
                                          "description": "voice edge-tts, default id-ID-ArdiNeural"}},
                               ["episode_id"]),
        "cmd": ["-m", "src.cli", "render", "{episode_id}", "--json"],
        "arg_map": {"voice": "--voice"},
        "dangerous": False,
    },
    {
        "name": "qc_video",
        "description": "QC teknis: durasi, resolusi, loudness (-14 LUFS), clipping, jeda hitam, "
                       "dan layout teks di area aman TikTok.",
        "inputSchema": _schema({"episode_id": {"type": "string"}}, ["episode_id"]),
        "cmd": ["-m", "src.cli", "qc", "{episode_id}", "--json"],
        "dangerous": False,
    },
    {
        "name": "publish_video",
        "description": "Siapkan paket upload manual setelah ACC dan QC lulus. Tidak memublikasikan ke TikTok.",
        "inputSchema": _schema({"episode_id": {"type": "string"},
                                "mode": {"type": "string", "enum": ["manual"]}},
                               ["episode_id"]),
        "cmd": ["-m", "src.cli", "publish", "{episode_id}", "--json"],
        "arg_map": {"mode": "--mode"},
        "dangerous": True,   # menyentuh dunia luar -> agent harus minta konfirmasi
    },
    {
        "name": "record_metrics",
        "description": "Catat performa video supaya pola pemenang bisa dipelajari otomatis.",
        "inputSchema": _schema({"episode_id": {"type": "string"},
                                "views": {"type": "integer"},
                                "avg_watch": {"type": "number"},
                                "likes": {"type": "integer"},
                                "comments": {"type": "integer"},
                                "shares": {"type": "integer"}}, ["episode_id", "views"]),
        "cmd": ["-m", "src.cli", "metrics", "{episode_id}", "--json"],
        "arg_map": {"views": "--views", "avg_watch": "--avg-watch", "likes": "--likes",
                    "comments": "--comments", "shares": "--shares"},
        "dangerous": False,
    },
    {
        "name": "learning_report",
        "description": "Laporan pola pemenang dari metrik: hook tipe apa yang menahan penonton, "
                       "visual apa yang efektif, dan insight lain.",
        "inputSchema": _schema(),
        "cmd": ["-m", "src.cli", "learn", "--json"],
        "dangerous": False,
    },
    {
        "name": "list_episodes",
        "description": "Daftar episode beserta status (draft/pending/approved/rendered/published).",
        "inputSchema": _schema(),
        "cmd": ["-m", "src.cli", "list", "--json"],
        "dangerous": False,
    },
]


def _run(tool: dict, args: dict) -> dict:
    cmd = [sys.executable] + [c.format(**args) if "{" in c else c for c in tool["cmd"]]
    for key, flag in (tool.get("arg_map") or {}).items():
        if args.get(key) not in (None, ""):
            cmd += [flag, str(args[key])]
    try:
        out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True, timeout=900)
    except subprocess.TimeoutExpired:
        return {"isError": True, "text": "timeout: proses lebih dari 15 menit"}
    if out.returncode != 0:
        return {"isError": True, "text": (out.stderr or out.stdout)[-1200:]}
    last = [ln for ln in out.stdout.strip().splitlines() if ln.strip()]
    if not last:
        return {"isError": False, "text": "ok"}
    try:
        return {"isError": False, "text": last[-1]}
    except Exception:
        return {"isError": False, "text": out.stdout[-2000:]}


def _resp(msg_id, result=None, error=None) -> dict:
    r = {"jsonrpc": "2.0", "id": msg_id}
    if error is not None:
        r["error"] = {"code": -32000, "message": str(error)}
    else:
        r["result"] = result
    return r


def handle(msg: dict) -> dict | None:
    method = msg.get("method")
    mid = msg.get("id")

    if method == "initialize":
        return _resp(mid, {
            "protocolVersion": PROTOCOL_VERSION,
            "capabilities": {"tools": {"listChanged": False}},
            "serverInfo": {"name": "ai-edukasi-agent", "version": "2.1.0"},
        })
    if method in ("notifications/initialized", "initialized"):
        return None
    if method == "ping":
        return _resp(mid, {})
    if method == "tools/list":
        return _resp(mid, {"tools": [
            {"name": t["name"], "description": t["description"], "inputSchema": t["inputSchema"]}
            for t in TOOLS]})
    if method == "tools/call":
        params = msg.get("params") or {}
        name = params.get("name")
        args = params.get("arguments") or {}
        tool = next((t for t in TOOLS if t["name"] == name), None)
        if not tool:
            return _resp(mid, error=f"tool tidak dikenal: {name}")
        res = _run(tool, args)
        return _resp(mid, {"content": [{"type": "text", "text": res["text"]}],
                           "isError": res["isError"]})
    if method is None:
        return None
    return _resp(mid, error=f"method tidak didukung: {method}")


def main() -> None:
    """stdio loop: satu pesan JSON per baris (newline-delimited JSON-RPC)."""
    print(f"mcp server siap ({len(TOOLS)} tool) — stdio", file=sys.stderr)
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            msg = json.loads(line)
        except json.JSONDecodeError:
            print(json.dumps(_resp(None, error="JSON tidak valid")), flush=True)
            continue
        try:
            resp = handle(msg)
        except Exception as e:
            resp = _resp(msg.get("id"), error=str(e))
        if resp is not None:
            print(json.dumps(resp), flush=True)


if __name__ == "__main__":
    main()
