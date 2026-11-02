# -*- coding: utf-8 -*-
"""
probe_models.py — uji SEMUA model di 9Router (dan Ollama Manager) satu per satu.

Cara pakai (di laptop, dari folder project, venv aktif):

    python tools/probe_models.py                 # uji + tulis hasil_uji_model.md
    python tools/probe_models.py --patch-env     # uji + perbarui baris MODEL_* di .env
    python tools/probe_models.py --cepat         # lewati uji payload besar/timeout (lebih cepat)

Hasil:
    hasil_uji_model.md  -> daftar model: OK/GAGAL + latensi + jenis error + rekomendasi
    .env (dengan --patch-env) -> hanya baris MODEL_* yang diganti; sisanya utuh

Skrip ini berdiri sendiri (hanya butuh httpx yang sudah ada di venv).
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
import time
from pathlib import Path

import httpx

SMALL_PROMPT = "Balas satu kata: OK"
LONG_OUTPUT_TOKENS = 1800
BIG_PROMPT_CHARS = 16000
PREF_A = ["kr/claude-haiku-4.5", "kr/glm-5", "kr/deepseek-3.2"]
PREF_B = ["kr/glm-5", "kr/deepseek-3.2", "kr/MiniMax-M2.5", "kr/qwen3-coder-next"]
PREF_C = ["kr/deepseek-3.2", "kr/MiniMax-M2.5", "kr/qwen3-coder-next", "kr/glm-5"]
SUBJECTS = ["PP", "PA", "BING", "PR", "ILKOM", "KAP", "DJ"]


def load_env(path: Path) -> dict:
    env: dict[str, str] = {}
    if not path.exists():
        print(f"[!] {path} tidak ditemukan. Jalankan dari folder project.")
        sys.exit(1)
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            env[key.strip()] = value.strip()
    return env


def pick(model: str, ok_models: list[str], preferences: list[str], used: set[str]) -> str:
    """Pilih model OK: pertahankan yang lama bila lolos, else preferensi, else bebas."""
    if model in ok_models:
        return model
    for candidate in preferences:
        if candidate in ok_models:
            return candidate
    for candidate in ok_models:
        if candidate not in used:
            return candidate
    return model or (ok_models[0] if ok_models else "")


async def probe_chat_models(
    client: httpx.AsyncClient, base: str, models: list[str], label: str
) -> list[dict]:
    results: list[dict] = []
    for model in models:
        start = time.time()
        row = {"model": model, "endpoint": label, "status": "GAGAL", "ms": 0, "error": ""}
        try:
            response = await client.post(
                f"{base}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": SMALL_PROMPT}],
                    "max_tokens": 8,
                    "temperature": 0.0,
                },
                timeout=45.0,
            )
            row["ms"] = int((time.time() - start) * 1000)
            if response.status_code == 200:
                text = (
                    response.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                    or ""
                ).strip()
                if text:
                    row["status"] = "OK"
                else:
                    row["error"] = "output kosong"
            else:
                row["error"] = f"HTTP {response.status_code}: {response.text[:120]}"
        except Exception as exc:  # noqa: BLE001
            row["ms"] = int((time.time() - start) * 1000)
            row["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        results.append(row)
        mark = "OK " if row["status"] == "OK" else "X  "
        print(f"  [{mark}] {label:10} {model:45} {row['ms']:>6} ms  {row['error'][:60]}")
    return results


async def probe_embedding_models(
    client: httpx.AsyncClient, base: str, models: list[str]
) -> list[dict]:
    results: list[dict] = []
    for model in models:
        start = time.time()
        row = {"model": model, "endpoint": "embedding", "status": "GAGAL", "ms": 0, "error": ""}
        try:
            response = await client.post(
                f"{base}/embeddings",
                json={"model": model, "input": ["uji embedding"]},
                timeout=45.0,
            )
            row["ms"] = int((time.time() - start) * 1000)
            if response.status_code == 200 and response.json().get("data"):
                row["status"] = "OK"
            else:
                row["error"] = f"HTTP {response.status_code}: {response.text[:120]}"
        except Exception as exc:  # noqa: BLE001
            row["ms"] = int((time.time() - start) * 1000)
            row["error"] = f"{type(exc).__name__}: {str(exc)[:120]}"
        results.append(row)
        mark = "OK " if row["status"] == "OK" else "X  "
        print(f"  [{mark}] {'embedding':10} {model:45} {row['ms']:>6} ms  {row['error'][:60]}")
    return results


async def probe_manager_deep(
    client: httpx.AsyncClient, base: str, model: str, quick: bool
) -> list[dict]:
    """Uji berat khusus Manager: payload besar (konteks) + output panjang (timeout)."""
    rows: list[dict] = []
    if quick:
        return rows
    big = "Kamu adalah verifier akademik. Berikut cuplikan materi kuliah.\n" + (
        "Komunikasi antarpribadi melibatkan penyampaian pesan, umpan balik, dan empati. " * 300
    )[:BIG_PROMPT_CHARS]
    for name, payload, max_tokens, timeout in (
        ("Manager payload besar (konteks)", big, 250, 120.0),
        ("Manager output panjang (timeout)", "Tulis 25 kalimat tentang komunikasi.", LONG_OUTPUT_TOKENS, 300.0),
    ):
        start = time.time()
        row = {"model": model, "endpoint": name, "status": "GAGAL", "ms": 0, "error": ""}
        try:
            response = await client.post(
                f"{base}/chat/completions",
                json={
                    "model": model,
                    "messages": [{"role": "user", "content": payload}],
                    "max_tokens": max_tokens,
                    "temperature": 0.0,
                },
                timeout=timeout,
            )
            row["ms"] = int((time.time() - start) * 1000)
            if response.status_code == 200:
                text = (
                    response.json()
                    .get("choices", [{}])[0]
                    .get("message", {})
                    .get("content")
                    or ""
                ).strip()
                row["status"] = "OK" if text else "GAGAL"
                row["error"] = "" if text else "output kosong (konteks terpotong?)"
            else:
                row["error"] = f"HTTP {response.status_code}: {response.text[:140]}"
        except Exception as exc:  # noqa: BLE001
            row["ms"] = int((time.time() - start) * 1000)
            row["error"] = f"{type(exc).__name__}: {str(exc)[:140]}"
        rows.append(row)
        mark = "OK " if row["status"] == "OK" else "X  "
        print(f"  [{mark}] {name:32} {row['ms']:>6} ms  {row['error'][:70]}")
    return rows


async def list_models(client: httpx.AsyncClient, base: str, path: str = "/models") -> list[str]:
    try:
        response = await client.get(f"{base}{path}", timeout=20.0)
        if response.status_code != 200:
            print(f"  [!] {base}{path} -> HTTP {response.status_code}")
            return []
        data = response.json().get("data", [])
        return sorted(str(item.get("id", "")) for item in data if item.get("id"))
    except Exception as exc:  # noqa: BLE001
        print(f"  [!] {base}{path} gagal dibaca ({type(exc).__name__})")
        return []


def patch_env(path: Path, updates: dict[str, str]) -> list[str]:
    """Ganti/ tambahkan baris KEY=value; baris lain utuh. Return daftar perubahan."""
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    changes: list[str] = []
    seen: set[str] = set()
    out: list[str] = []
    for line in lines:
        match = re.match(r"^\s*([A-Z0-9_]+)\s*=", line)
        key = match.group(1) if match else ""
        if key and key in updates:
            seen.add(key)
            new_line = f"{key}={updates[key]}"
            if new_line.strip() != line.strip():
                changes.append(f"{key}: {line.strip()} -> {new_line}")
            out.append(new_line)
        else:
            out.append(line)
    for key, value in updates.items():
        if key not in seen:
            out.append(f"{key}={value}")
            changes.append(f"{key}: (baru) {key}={value}")
    path.write_text("\n".join(out) + "\n", encoding="utf-8")
    return changes


async def main() -> None:
    parser = argparse.ArgumentParser(description="Uji semua model satu per satu.")
    parser.add_argument("--env", default=".env", help="path file .env")
    parser.add_argument("--patch-env", action="store_true", help="perbarui baris MODEL_* di .env")
    parser.add_argument("--cepat", action="store_true", help="lewati uji payload besar/timeout")
    args = parser.parse_args()

    env_path = Path(args.env)
    env = load_env(env_path)

    chat_base = (env.get("CHAT_BASE_URL") or env.get("NINE_ROUTER_BASE_URL") or "").rstrip("/")
    manager_base = (env.get("MANAGER_CHAT_BASE_URL") or chat_base).rstrip("/")
    embedding_base = (env.get("EMBEDDING_BASE_URL") or env.get("NINE_ROUTER_BASE_URL") or "").rstrip("/")
    stt_base = (env.get("STT_BASE_URL") or env.get("NINE_ROUTER_BASE_URL") or "").rstrip("/")
    if not chat_base:
        print("[!] NINE_ROUTER_BASE_URL belum diisi di .env.")
        sys.exit(1)

    print("=" * 78)
    print("UJI SEMUA MODEL — Academic AI")
    print(f"  Chat spesialis : {chat_base}")
    print(f"  Chat Manager   : {manager_base}")
    print(f"  Embedding      : {embedding_base}")
    print("=" * 78)

    timeout = httpx.Timeout(60.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        print("\n[1] Membaca katalog...")
        chat_models = await list_models(client, chat_base)
        manager_models = (
            chat_models if manager_base == chat_base else await list_models(client, manager_base)
        )
        embedding_models = await list_models(client, embedding_base, "/models/embedding")
        stt_models = await list_models(client, stt_base, "/models/stt") if stt_base else []
        if not embedding_models:
            embedding_models = await list_models(client, embedding_base, "/models")

        print(f"    chat={len(chat_models)} manager={len(manager_models)} "
              f"embedding={len(embedding_models)} stt={len(stt_models)}")

        print("\n[2] Uji chat model satu per satu (spesialis)...")
        chat_rows = await probe_chat_models(client, chat_base, chat_models, "spesialis")

        print("\n[3] Uji embedding model satu per satu...")
        emb_rows = await probe_embedding_models(client, embedding_base, embedding_models)

        print("\n[4] Uji AI Manager (verifier)...")
        manager_model = env.get("MODEL_MANAGER", "")
        manager_rows: list[dict] = []
        if manager_model:
            manager_rows = await probe_chat_models(client, manager_base, [manager_model], "manager")
            manager_rows += await probe_manager_deep(client, manager_base, manager_model, args.cepat)
        else:
            print("  [!] MODEL_MANAGER kosong di .env.")

    ok_chat = [r["model"] for r in chat_rows if r["status"] == "OK"]
    ok_emb = [r["model"] for r in emb_rows if r["status"] == "OK"]
    manager_ok = bool(manager_rows) and all(r["status"] == "OK" for r in manager_rows)

    # Rekomendasi penugasan
    used: set[str] = set()
    assign: dict[str, str] = {}
    for subject in SUBJECTS:
        for role, prefs in (("A", PREF_A), ("B", PREF_B), ("C", PREF_C)):
            current = env.get(f"MODEL_{subject}_{role}", "")
            chosen = pick(current, ok_chat, prefs, used)
            if chosen:
                used.add(chosen)
            assign[f"MODEL_{subject}_{role}"] = chosen
    manager_new = env.get("MODEL_MANAGER", "")
    if manager_rows and not manager_ok and manager_models:
        manager_new = pick("", manager_models, [manager_model], set())
    embedding_new = env.get("MODEL_EMBEDDING", "")
    if ok_emb and embedding_new not in ok_emb:
        embedding_new = ok_emb[0]

    # Laporan
    report = ["# Hasil Uji Model — Academic AI", ""]
    report.append(f"- Endpoint chat spesialis: `{chat_base}`")
    report.append(f"- Endpoint chat Manager  : `{manager_base}`")
    report.append(f"- Endpoint embedding     : `{embedding_base}`")
    report.append("")
    report.append("## Chat model (spesialis)")
    report.append("| Model | Status | Latensi | Keterangan |")
    report.append("|---|---|---|---|")
    for row in chat_rows:
        report.append(f"| `{row['model']}` | {row['status']} | {row['ms']} ms | {row['error'][:80]} |")
    report.append("")
    report.append("## Embedding model")
    report.append("| Model | Status | Latensi | Keterangan |")
    report.append("|---|---|---|---|")
    for row in emb_rows:
        report.append(f"| `{row['model']}` | {row['status']} | {row['ms']} ms | {row['error'][:80]} |")
    report.append("")
    report.append("## AI Manager (verifier)")
    report.append("| Uji | Status | Latensi | Keterangan |")
    report.append("|---|---|---|---|")
    for row in manager_rows:
        report.append(f"| {row['endpoint']} | {row['status']} | {row['ms']} ms | {row['error'][:100]} |")
    if not manager_rows:
        report.append("| (MODEL_MANAGER kosong) | - | - | - |")
    report.append("")
    report.append("## Rekomendasi MODEL_* untuk .env")
    report.append("```")
    for key, value in assign.items():
        report.append(f"{key}={value}")
    report.append(f"MODEL_MANAGER={manager_new}")
    report.append(f"MODEL_EMBEDDING={embedding_new}")
    report.append("```")
    report.append("")
    verdict = "SEMUA UJI MANAGER LOLOS" if manager_ok else "MANAGER MASIH BERMASALAH — cek baris uji Manager di atas"
    report.append(f"**Verdict:** {verdict}. Chat model OK: {len(ok_chat)}/{len(chat_rows)}. "
                  f"Embedding OK: {len(ok_emb)}/{len(emb_rows)}.")
    Path("hasil_uji_model.md").write_text("\n".join(report) + "\n", encoding="utf-8")
    print("\n-> Laporan ditulis: hasil_uji_model.md")

    if args.patch_env:
        updates = dict(assign)
        updates["MODEL_MANAGER"] = manager_new
        updates["MODEL_EMBEDDING"] = embedding_new
        changes = patch_env(env_path, updates)
        print(f"-> .env diperbarui ({len(changes)} perubahan):")
        for change in changes:
            print(f"   {change}")
        print("-> Restart web_run.py setelah ini.")
    else:
        print("-> Jalankan lagi dengan --patch-env untuk menulis rekomendasi ke .env.")

    if stt_models:
        print(f"-> Model STT tersedia (uji butuh audio): {', '.join(stt_models[:6])}")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[attr-defined]
    except Exception:
        pass
    asyncio.run(main())
