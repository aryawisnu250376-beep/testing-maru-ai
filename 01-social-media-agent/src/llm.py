"""LLM layer v2 — registry provider + fallback berantai + routing per task.

Kenapa registry, bukan satu base_url:
  Pipeline ini memanggil LLM untuk 4 tugas dengan profil berbeda. Dengan satu
  provider, satu rate-limit = pipeline mati. Dengan rantai fallback, run tetap
  selesai walau provider utama kena kuota.

  Urutan default (semua bisa gratis):
    1. local      (Ollama / llama.cpp — 100% offline)
    2. router     (9Router / OpenRouter / apa pun yang OpenAI-compatible)
    3. groq       (free tier cepat)
    4. gemini     (free tier)
    5. none       -> pemanggil pakai fallback non-LLM yang deterministik

Semua provider bicara protokol OpenAI `/chat/completions`, jadi tidak ada
adapter khusus per vendor.
"""
from __future__ import annotations

import json
import os
import re
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------- JSON utils

def extract_json(text: str) -> dict:
    text = (text or "").strip()
    fence = re.search(r"```(?:json)?\s*(.+?)```", text, re.S)
    if fence:
        text = fence.group(1).strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start = text.find("{")
    if start < 0:
        raise ValueError("tidak ada JSON di output model")
    depth = 0
    for i, ch in enumerate(text[start:], start):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return json.loads(text[start:i + 1])
    raise ValueError("JSON tidak tertutup")


# ---------------------------------------------------------------- provider

@dataclass
class Provider:
    name: str
    base_url: str = ""
    api_key: str = ""
    model: str = ""
    models: dict[str, str] = field(default_factory=dict)
    timeout: int = 120
    # statistik runtime (dipakai dashboard)
    calls: int = 0
    failures: int = 0
    total_latency: float = 0.0

    @property
    def available(self) -> bool:
        return bool(self.base_url)

    def model_for(self, tier: str) -> str:
        return self.models.get(tier) or self.models.get("default") or self.model

    def _headers(self) -> dict:
        h = {"Content-Type": "application/json"}
        if self.api_key:
            h["Authorization"] = f"Bearer {self.api_key}"
        return h

    def list_models(self) -> list[str]:
        try:
            req = urllib.request.Request(self.base_url.rstrip("/") + "/models",
                                         headers=self._headers())
            with urllib.request.urlopen(req, timeout=15) as r:
                data = json.loads(r.read())
            return [m.get("id") for m in data.get("data", []) if m.get("id")]
        except Exception:
            return []

    def chat(self, messages: list[dict], tier: str = "default",
             temperature: float = 0.7, max_tokens: int = 2200) -> str:
        model = self.model_for(tier)
        if not model:
            ids = self.list_models()
            if not ids:
                raise RuntimeError(f"{self.name}: tidak ada model tersedia")
            model = ids[0]
            self.model = model
        body = json.dumps({"model": model, "messages": messages,
                           "temperature": temperature, "max_tokens": max_tokens}).encode()
        req = urllib.request.Request(self.base_url.rstrip("/") + "/chat/completions",
                                     data=body, headers=self._headers(), method="POST")
        t0 = time.time()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as r:
                data = json.loads(r.read())
            self.calls += 1
            self.total_latency += time.time() - t0
            return data["choices"][0]["message"]["content"]
        except urllib.error.HTTPError as e:
            self.failures += 1
            body_txt = e.read()[:300].decode(errors="ignore")
            raise RuntimeError(f"{self.name} HTTP {e.code}: {body_txt}") from e
        except Exception as e:
            self.failures += 1
            raise RuntimeError(f"{self.name}: {e}") from e

    def stats(self) -> dict:
        return {"provider": self.name, "calls": self.calls, "failures": self.failures,
                "avg_latency_sec": round(self.total_latency / self.calls, 2) if self.calls else 0}


# ---------------------------------------------------------------- registry

def _port_open(host: str, port: int, timeout: float = 0.25) -> bool:
    import socket

    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def providers_from_config(cfg: dict) -> list[Provider]:
    """Bangun rantai provider dari config + env. Kosong = mode tanpa LLM."""
    llm = cfg.get("llm", {})
    tiers_src = {
        "strong": llm.get("model_strong") or llm.get("model"),
        "cheap": llm.get("model_cheap") or llm.get("model"),
        "qc": llm.get("model_qc") or llm.get("model"),
        "default": llm.get("model"),
    }
    out: list[Provider] = []

    def add(name: str, base: str, key: str, model: str, models: dict | None = None):
        if not base:
            return
        t = {k: v for k, v in tiers_src.items()}
        if models:
            t.update(models)
        if not t.get("default"):
            t["default"] = model
        for k, v in list(t.items()):
            if not v:
                t[k] = t["default"]
        out.append(Provider(name=name, base_url=base, api_key=key, model=model or t["default"],
                            models=t))

    # provider eksplisit dari config/env (prioritas tertinggi)
    add("primary", llm.get("base_url", ""), llm.get("api_key", ""), llm.get("model", ""))

    # rantai gratis tambahan — hanya dipakai kalau env tersedia
    if not out:
        # Ollama hanya ikut kalau di-opt-in eksplisit, supaya `available` jujur
        ollama_url = os.getenv("OLLAMA_BASE_URL", "")
        if ollama_url or _port_open("127.0.0.1", 11434):
            add("ollama", ollama_url or "http://localhost:11434/v1", "ollama",
                os.getenv("OLLAMA_MODEL", ""))
        add("groq", "https://api.groq.com/openai/v1" if os.getenv("GROQ_API_KEY") else "",
            os.getenv("GROQ_API_KEY", ""), os.getenv("GROQ_MODEL", "llama-3.3-70b-versatile"))
        add("gemini", ("https://generativelanguage.googleapis.com/v1beta/openai/"
                       if os.getenv("GEMINI_API_KEY") else ""),
            os.getenv("GEMINI_API_KEY", ""), os.getenv("GEMINI_MODEL", "gemini-2.5-flash"))
    return [p for p in out if p.available]


class LLM:
    """Fasad: satu `chat()` untuk rantai provider, dengan fallback otomatis."""

    def __init__(self, providers: list[Provider] | None = None):
        self.providers = providers or []
        self.last_error: str | None = None

    @classmethod
    def from_config(cls, cfg: dict) -> "LLM":
        return cls(providers_from_config(cfg))

    @property
    def available(self) -> bool:
        return bool(self.providers)

    def chat(self, messages: list[dict], tier: str = "default", temperature: float = 0.7,
             max_tokens: int = 2200) -> str:
        errors = []
        for p in self.providers:
            try:
                return p.chat(messages, tier=tier, temperature=temperature,
                              max_tokens=max_tokens)
            except Exception as e:
                errors.append(str(e))
                print(f"  [llm] {p.name} gagal, coba berikutnya: {str(e)[:110]}")
        self.last_error = " | ".join(errors)[-500:]
        raise RuntimeError(f"semua provider LLM gagal: {self.last_error}")

    def chat_json(self, messages: list[dict], tier: str = "default",
                  temperature: float = 0.7, retries: int = 2) -> dict[str, Any]:
        for attempt in range(retries + 1):
            raw = self.chat(messages, tier=tier, temperature=temperature)
            try:
                return extract_json(raw)
            except Exception as e:
                if attempt == retries:
                    raise RuntimeError(f"gagal dapat JSON valid: {e}") from e
                messages = messages + [
                    {"role": "assistant", "content": raw[:1200]},
                    {"role": "user",
                     "content": "Output bukan JSON valid. Ulangi HANYA JSON, tanpa penjelasan."},
                ]
        raise RuntimeError("unreachable")

    def stats(self) -> dict:
        return {"providers": [p.stats() for p in self.providers],
                "available": self.available, "last_error": self.last_error}
