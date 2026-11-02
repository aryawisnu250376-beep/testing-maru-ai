"""PEMERIKSA MODEL — mana yang benar-benar jalan, mana yang cuma muncul di daftar.

Dua lapis pemeriksaan:
  1. **Reachability** (gratis, cepat): apakah model muncul di `/models` endpoint
     provider, dan apakah ia merespons 1 token. Ini menangkap kasus paling sering:
     model terdaftar tapi kuota habis / key mati / endpoint salah.
  2. **Bench** (opsional): panggil dengan prompt pendek, ukur latensi & validitas
     output. Dipakai untuk memilih model termurah yang masih layak.

Status yang dilaporkan per model:
  ok              respons baik
  quota           error kuota/kredit (mis. "insufficient user quota")
  unauthorized    API key salah/tidak ada
  not_found       model tidak dikenal provider
  rate_limited    429
  timeout         tidak menjawab dalam batas waktu
  unreachable     base_url tidak bisa dihubungi (mis. 9Router belum dijalankan)
  unlisted        tidak muncul di daftar /models

Kenapa penting: rantai fallback LLM yang memuat model mati akan membuang waktu
tiap panggilan. Probe mengubah itu jadi keputusan, bukan harapan.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor

from . import db

# Daftar model dari dashboard 9Router pengguna (dikelompokkan per provider 9Router).
# Prefix = provider/connector di 9Router. Ini hanya kandidat — probe yang memutuskan.
CANDIDATES: dict[str, list[str]] = {
    "kiro (kr)": [
        "kr/claude-opus-5.5(max)", "kr/claude-opus-5.5-thinking(max)",
        "kr/claude-opus-5.5-agentic(max)", "kr/claude-opus-5(max)",
        "kr/claude-opus-4.8(max)", "kr/claude-sonnet-5(max)", "kr/claude-sonnet-4.5",
        "kr/claude-haiku-4.5", "kr/deepseek-3.2", "kr/qwen3-coder-next",
        "kr/glm-5", "kr/minimax-m2.5", "kr/gpt-5.6-sol", "kr/gpt-5.6-terra",
        "kr/gpt-5.6-luna",
    ],
    "opencode (oc)": [
        "oc/big-pickle", "oc/mimo-v2.6-flash-free", "oc/space-bunny-free",
        "oc/exo-free", "oc/longcat-2.5-preview-free", "oc/step-5-preview-free",
        "oc/ling-3.0-flash-fin-free", "oc/nemotron-3-ultra-free",
        "oc/nemotron-3.5-lightning-free", "oc/ling-3.1-flash-free",
        "oc/muse-spark-1.2-contributor-free", "oc/muse-spark-1.3-contributor-free",
        "oc/union-alpha",
    ],
    "openrouter": [
        "openrouter/thinkingmachines/inkling:small:free",
        "openrouter/thinkingmachines/inkling:free",
        "openrouter/nvidia/nemotron-3.5-lightning:free",
    ],
    "nvidia": [
        "nvidia/minimaxai/minimax-m2.7", "nvidia/minimaxai/minimax-m3",
        "nvidia/z-ai/glm-5.2", "nvidia/deepseek-ai/deepseek-v4-pro",
        "nvidia/deepseek-ai/deepseek-v4-flash", "nvidia/moonshotai/kimi-k2.6(max)",
        "nvidia/nvidia/nemotron-3-ultra-550b-a55b",
    ],
    "gemini": [
        "gemini/gemini-4-argon", "gemini/gemini-3.8-flash", "gemini/gemini-3.7-flash",
        "gemini/gemini-3.5-flash-lite", "gemini/gemini-2.5-pro", "gemini/gemini-2.5-flash",
        "gemini/gemini-2.5-flash-lite", "gemini/gemma-4-31b-it",
    ],
    "cloudflare (cf)": [
        "cf/@cf/meta/llama-3.2-1b-instruct", "cf/@cf/meta/llama-3.2-3b-instruct",
        "cf/@cf/meta/llama-3.1-8b-instruct-fp8-fast", "cf/@cf/meta/llama-3.1-8b-instruct-awq",
        "cf/@cf/mistralai/mistral-small-3.1-24b-instruct", "cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
        "cf/@cf/deepseek-ai/deepseek-r1-distill-qwen-32b",
        "cf/@cf/moonshotai/kimi-k2.5", "cf/@cf/moonshotai/kimi-k2.6",
        "cf/@cf/zai-org/glm-4.7-flash(thinking)", "cf/@cf/qwen/qwq-32b",
        "cf/@cf/qwen/qwen2.5-coder-32b-instruct",
    ],
    "ollama": [
        "ollama/gpt-oss:120b", "ollama/kimi-k2.5", "ollama/glm-5(thinking)",
        "ollama/minimax-m2.5(thinking)", "ollama/glm-4.7-flash(thinking)",
        "ollama/qwen3.5", "ollama/deepseek-v4.1-flash:cloud",
    ],
    "poolside (ps)": ["ps/poolside/laguna-s-2.1", "ps/poolside/laguna-xs-2.1"],
    "agnes": ["agnes/agnes-2.5-flash", "agnes/agnes-2.5-pro", "agnes/agnes-2.5-pro-beta",
              "agnes/agnes-3.0-flash"],
}

# Model yang paling mungkin berguna untuk pipeline ini (script berbahasa Indonesia,
# instruksi panjang, output JSON ketat). Urutan preferensi untuk tier "strong".
PREFERRED_STRONG = [
    "kr/claude-sonnet-4.5", "kr/claude-sonnet-5(max)", "kr/gpt-5.6-terra",
    "gemini/gemini-2.5-pro", "kr/deepseek-3.2", "kr/glm-5",
    "ollama/gpt-oss:120b", "cf/@cf/meta/llama-3.3-70b-instruct-fp8-fast",
]
PREFERRED_CHEAP = [
    "gemini/gemini-2.5-flash-lite", "kr/claude-haiku-4.5", "oc/mimo-v2.6-flash-free",
    "cf/@cf/meta/llama-3.1-8b-instruct-fp8-fast", "gemini/gemini-2.5-flash",
]


def _classify(status_code: int | None, body: str) -> str:
    b = (body or "").lower()
    if status_code == 401 or status_code == 403:
        return "unauthorized"
    if status_code == 404:
        return "not_found"
    if status_code == 429 or "rate limit" in b or "too many requests" in b:
        return "rate_limited"
    if "insufficient" in b and ("quota" in b or "credit" in b or "balance" in b):
        return "quota"
    if "quota" in b or "exceeded your current quota" in b:
        return "quota"
    if status_code and 500 <= status_code < 600:
        return "server_error"
    if status_code == 400 and ("model" in b and ("not" in b or "unknown" in b)):
        return "not_found"
    return "error" if status_code else "unknown"


def probe_model(base_url: str, api_key: str, model: str, timeout: int = 25) -> dict:
    """Satu panggilan minimal untuk membuktikan model hidup."""
    base = (base_url or "").rstrip("/")
    if not base:
        return {"model": model, "status": "unreachable", "latency_ms": 0,
                "error": "base_url kosong"}
    payload = json.dumps({"model": model, "messages": [{"role": "user", "content": "hi"}],
                          "max_tokens": 1, "temperature": 0}).encode()
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    req = urllib.request.Request(f"{base}/chat/completions", data=payload,
                                headers=headers, method="POST")
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            json.loads(r.read())
        return {"model": model, "status": "ok",
                "latency_ms": int((time.time() - t0) * 1000), "error": ""}
    except urllib.error.HTTPError as e:
        body = e.read()[:400].decode(errors="ignore")
        return {"model": model, "status": _classify(e.code, body),
                "latency_ms": int((time.time() - t0) * 1000), "error": body[:220]}
    except Exception as e:
        msg = str(e).lower()
        status = "timeout" if "timed out" in msg or "timeout" in msg else "unreachable"
        return {"model": model, "status": status,
                "latency_ms": int((time.time() - t0) * 1000), "error": str(e)[:220]}


def health(base_url: str, api_key: str = "") -> dict:
    """Cek endpoint + ambil daftar model yang terdaftar."""
    base = (base_url or "").rstrip("/")
    if not base:
        return {"reachable": False, "models": [], "error": "base_url kosong"}
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    try:
        req = urllib.request.Request(f"{base}/models", headers=headers)
        with urllib.request.urlopen(req, timeout=8) as r:
            data = json.loads(r.read())
        ids = [m.get("id") for m in data.get("data", []) if m.get("id")]
        return {"reachable": True, "models": ids, "error": ""}
    except Exception as e:
        return {"reachable": False, "models": [], "error": str(e)[:220]}


def check_all(base_url: str, api_key: str = "", models: list[str] | None = None,
              workers: int = 6, persist: bool = True, verbose: bool = True) -> dict:
    h = health(base_url, api_key)
    listing = models or [m for group in CANDIDATES.values() for m in group]

    if not h["reachable"]:
        if verbose:
            print(f"  ✖ endpoint tidak bisa dihubungi: {h['error']}")
            print("     penyebab paling umum: 9Router belum jalan (jalankan `9router` "
                  "atau `docker start 9router`), atau base_url salah.")
            print("     hasil probe ditandai 'unreachable' — bukan berarti modelnya mati.")
        results = [{"model": m, "status": "unreachable", "latency_ms": 0,
                    "error": h["error"]} for m in listing]
    else:
        with ThreadPoolExecutor(max_workers=workers) as ex:
            results = list(ex.map(lambda m: probe_model(base_url, api_key, m), listing))

    out = {"endpoint": base_url, "reachable": h["reachable"], "endpoint_error": h["error"],
           "registry_count": len(h["models"]), "checked": len(results),
           "results": results,
           "summary": _summarize(results),
           "recommend": recommend(results, h["models"])}

    if persist:
        db.init()
        with db.conn() as c:
            for r in results:
                c.execute(
                    "INSERT OR REPLACE INTO model_status (model, provider, ok, latency_ms, error, checked_at)"
                    " VALUES (?,?,?,?,?,?)",
                    (r["model"], r["model"].split("/")[0], 1 if r["status"] == "ok" else 0,
                     r["latency_ms"], (r["status"] + " " + (r.get("error") or ""))[:300], db.now()))

    if verbose:
        s = out["summary"]
        print(f"\n  endpoint: {base_url}  (registry: {out['registry_count']} model)")
        for status, n in sorted(s.items(), key=lambda x: -x[1]):
            print(f"    {status:14} {n}")
        ok = [r for r in results if r["status"] == "ok"]
        if ok:
            print("\n  model yang BENAR-BENAR menjawab:")
            for r in sorted(ok, key=lambda x: x["latency_ms"])[:12]:
                print(f"    ✔ {r['model']:52} {r['latency_ms']:5} ms")
    return out


def _summarize(results: list[dict]) -> dict:
    s: dict[str, int] = {}
    for r in results:
        s[r["status"]] = s.get(r["status"], 0) + 1
    return s


def recommend(results: list[dict], registry: list[str]) -> dict:
    """Pilih model untuk tiap tier berdasarkan hasil probe."""
    ok = {r["model"]: r for r in results if r["status"] == "ok"}
    picked = {}
    for tier, prefs in (("strong", PREFERRED_STRONG), ("cheap", PREFERRED_CHEAP)):
        picked[tier] = next((m for m in prefs if m in ok), None)
    if not picked["strong"] and ok:
        picked["strong"] = min(ok, key=lambda m: ok[m]["latency_ms"])
    if not picked["cheap"] and ok:
        picked["cheap"] = picked["strong"]
    return {
        "strong": picked["strong"], "cheap": picked["cheap"],
        "note": ("tier 'strong' untuk nulis script, 'cheap' untuk klasifikasi trend"
                 if ok else "belum ada model yang menjawab — jalankan dengan 9Router aktif"),
    }


def env_snippet(rec: dict) -> str:
    """Potongan .env siap tempel berdasarkan model yang hidup."""
    if not rec.get("strong"):
        return "# belum ada model yang menjawab — jalankan 9Router dulu"
    return "\n".join([
        "LLM_BASE_URL=http://localhost:20128/v1",
        "LLM_API_KEY=<ambil dari 9Router: Endpoint & Key>",
        f"LLM_MODEL_STRONG={rec['strong']}",
        f"LLM_MODEL_CHEAP={rec.get('cheap') or rec['strong']}",
        f"LLM_MODEL={rec['strong']}",
    ])


if __name__ == "__main__":
    import os
    import sys

    base = os.getenv("LLM_BASE_URL", "http://localhost:20128/v1")
    key = os.getenv("LLM_API_KEY", "")
    if len(sys.argv) > 1:
        base = sys.argv[1]
    out = check_all(base, key)
    print("\n" + env_snippet(out["recommend"]))
