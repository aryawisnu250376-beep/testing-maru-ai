"""Otorisasi OAuth TikTok resmi (bisa dicabut). Tidak meminta password.
Jalankan: python scripts/ootto-auth.py
Buka URL yang muncul, login TikTok, lalu tempel kode callback.
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from ootto import tiktok
redirect = "http://localhost:8765/callback"
url, state = tiktok.authorization_url(redirect)
print("Buka URL ini di browser:\n" + url)
code = input("Tempel kode otorisasi: ").strip()
print(tiktok.exchange_code(code, redirect))
