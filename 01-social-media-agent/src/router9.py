"""Adaptor 9Router lokal (OpenAI-compatible).

Tidak menyimpan isi percakapan. Kredensial hanya dibaca dari environment/.env.
Nama model harus berasal dari dashboard 9Router, bukan ditebak.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.request
from dataclasses import dataclass


@dataclass
class RouterConfig:
    base_url: str
    api_key: str
    model: str

    @classmethod
    def from_env(cls) -> "RouterConfig":
        base = (os.getenv("ROUTER_BASE_URL") or os.getenv("LLM_BASE_URL") or "").rstrip("/")
        key = os.getenv("ROUTER_API_KEY") or os.getenv("LLM_API_KEY") or ""
        model = os.getenv("ROUTER_MODEL") or os.getenv("LLM_MODEL_STRONG") or os.getenv("LLM_MODEL") or ""
        return cls(base, key, model)

    @property
    def configured(self) -> bool:
        return bool(self.base_url)


def _request(cfg: RouterConfig, path: str, payload: dict | None = None, timeout: int = 30) -> dict:
    url = cfg.base_url.rstrip("/") + path
    headers = {"Content-Type": "application/json"}
    if cfg.api_key:
        headers["Authorization"] = "Bearer " + cfg.api_key
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers)
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read())


def list_models(cfg: RouterConfig | None = None) -> list[str]:
    cfg = cfg or RouterConfig.from_env()
    if not cfg.configured:
        raise RuntimeError("ROUTER_BASE_URL belum diisi")
    data = _request(cfg, "/models", timeout=15)
    return [m.get("id") for m in data.get("data", []) if m.get("id")]


def test_question(cfg: RouterConfig | None = None, question: str = "Jawab satu kata: siap?") -> dict:
    """Tahap 1: satu pertanyaan harus dijawab model. Tidak menebak nama model."""
    cfg = cfg or RouterConfig.from_env()
    if not cfg.configured:
        return {"ok": False, "error": "ROUTER_BASE_URL belum diisi"}
    try:
        models = list_models(cfg)
    except Exception as exc:
        return {"ok": False, "error": f"Tidak bisa membaca /models: {exc}"}
    if not models:
        return {"ok": False, "error": "Dashboard 9Router belum mengembalikan model"}
    model = cfg.model or models[0]
    if model not in models:
        return {"ok": False, "error": f"Model {model} tidak ada di dashboard", "models": models}
    try:
        out = _request(cfg, "/chat/completions", {
            "model": model,
            "messages": [{"role": "user", "content": question}],
            "max_tokens": 32,
            "temperature": 0,
        }, timeout=60)
        answer = (out.get("choices") or [{}])[0].get("message", {}).get("content", "")
        return {"ok": bool(answer.strip()), "model": model, "answer": answer.strip(), "models": models}
    except Exception as exc:
        return {"ok": False, "error": str(exc), "model": model, "models": models}


def chat(messages: list[dict], cfg: RouterConfig | None = None, model: str | None = None,
         temperature: float = 0.4, max_tokens: int = 2200) -> str:
    cfg = cfg or RouterConfig.from_env()
    if not cfg.configured:
        raise RuntimeError("9Router belum dikonfigurasi")
    chosen = model or cfg.model
    if not chosen:
        models = list_models(cfg)
        if not models:
            raise RuntimeError("Tidak ada model tersedia di 9Router")
        chosen = models[0]
    out = _request(cfg, "/chat/completions", {
        "model": chosen, "messages": messages,
        "temperature": temperature, "max_tokens": max_tokens,
    }, timeout=120)
    return (out.get("choices") or [{}])[0].get("message", {}).get("content", "")
