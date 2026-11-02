"""Adapter Hermes Agent — satu sumber kebenaran untuk definisi tool.

Pipeline ini diekspos ke agent lewat **MCP** (lihat src/mcp_server.py), jadi
tidak ada duplikasi skema. File ini menyediakan:

  - `openai_tools()`  : konversi skema MCP -> function-calling OpenAI/9Router,
                        untuk agent yang belum bicara MCP
  - `call(name, **kw)`: panggil tool langsung dari Python (dipakai cron/skrip)
  - `print_hermes_config()`: cetak blok YAML siap tempel ke config Hermes

Aturan keras yang harus dipatuhi agent (juga tertulis di SKILL.md):
  1. render_video hanya setelah request_approval mengembalikan acc
  2. publish_video mode=direct hanya setelah audit TikTok lulus
"""
from __future__ import annotations

import json
import subprocess
import sys

from .mcp_server import TOOLS, ROOT


def openai_tools() -> list[dict]:
    """Skema function-calling yang kompatibel dengan 9Router/OpenAI."""
    return [{
        "type": "function",
        "function": {
            "name": t["name"],
            "description": t["description"],
            "parameters": t["inputSchema"],
        },
    } for t in TOOLS]


def call(name: str, **kwargs) -> dict:
    """Jalankan tool pipeline dari Python. Return dict hasil atau {error}."""
    tool = next((t for t in TOOLS if t["name"] == name), None)
    if not tool:
        return {"error": f"tool tidak dikenal: {name}"}
    cmd = [sys.executable] + [c.format(**kwargs) if "{" in c else c for c in tool["cmd"]]
    for key, flag in (tool.get("arg_map") or {}).items():
        if kwargs.get(key) not in (None, ""):
            cmd += [flag, str(kwargs[key])]
    out = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if out.returncode != 0:
        return {"error": (out.stderr or out.stdout)[-800:]}
    lines = [ln for ln in out.stdout.strip().splitlines() if ln.strip()]
    try:
        return json.loads(lines[-1]) if lines else {"ok": True}
    except Exception:
        return {"raw": out.stdout[-1500:]}


def hermes_config_yaml() -> str:
    return f"""# tempel ke ~/.hermes/config.yaml
mcp_servers:
  konten-ai:
    command: "{sys.executable}"
    args: ["-m", "src.mcp_server"]
    cwd: "{ROOT}"
    env:
      # opsional; kosong = pipeline jalan tanpa LLM (template)
      LLM_BASE_URL: "${{LLM_BASE_URL}}"
      LLM_API_KEY: "${{LLM_API_KEY}}"
      TELEGRAM_BOT_TOKEN: "${{TELEGRAM_BOT_TOKEN}}"
      TELEGRAM_CHAT_ID: "${{TELEGRAM_CHAT_ID}}"

approvals:
  mode: smart
  require_confirmation:
    - "publish_video"     # menyentuh dunia luar
"""


def print_hermes_config() -> None:
    print(hermes_config_yaml())


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "config":
        print_hermes_config()
    elif len(sys.argv) > 1 and sys.argv[1] == "schema":
        print(json.dumps({"tools": openai_tools()}, indent=2, ensure_ascii=False)[:2000])
    else:
        print(f"{len(TOOLS)} tool terdaftar:")
        for t in TOOLS:
            flag = " ⚠ butuh konfirmasi" if t.get("dangerous") else ""
            print(f"  - {t['name']}{flag}")
        print("\nHermes memakai MCP: python -m src.mcp_server")
        print("Cetak config:  python -m src.hermes_skill config")
