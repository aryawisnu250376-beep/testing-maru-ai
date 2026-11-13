#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import sys
from pathlib import Path

def main():
    proj = Path(sys.argv[1] if len(sys.argv) > 1 else ".").resolve()
    tb_path = proj / "src" / "tiktok_bridge.py"
    hm_path = proj / "src" / "hermes_mausbot.py"

    print("=" * 60)
    print("PATCH TIKTOK RESMI & PERBAIKAN CHAT INTEGRASI MARU HQ")
    print("=" * 60)

    # 1. Pastikan tiktok_bridge.py selalu memakai redirect_uri yang tepat
    if tb_path.exists():
        code = tb_path.read_text(encoding="utf-8")
        code = code.replace("https://127.0.0.1:8443/api/tiktok/callback", "https://maru-hq.localtest.me:8443/api/tiktok/callback")
        code = code.replace("http://127.0.0.1:8080/api/tiktok/callback", "https://maru-hq.localtest.me:8443/api/tiktok/callback")
        tb_path.write_text(code, encoding="utf-8")
        print("  -> src/tiktok_bridge.py: Redirect URI di-lock ke https://maru-hq.localtest.me:8443")

    # 2. Perbaiki hermes_mausbot.py agar perintah tiktok selalu di-intercept pertama di grup & bot manapun
    if hm_path.exists():
        code = hm_path.read_text(encoding="utf-8")
        
        # Bersihkan intercept lama jika ada
        if "### TIKTOK INTERCEPT START ###" in code:
            parts = code.split("### TIKTOK INTERCEPT START ###")
            tail = parts[1].split("### TIKTOK INTERCEPT END ###")[1]
            code = parts[0] + tail

        # Sisipkan intercept bersih persis di awal chat_with_agent
        tiktok_block = '''### TIKTOK INTERCEPT START ###
    low = (prompt or "").lower().strip()
    if "hubungkan tiktok" in low or "connect tiktok" in low or "link tiktok" in low:
        from . import tiktok_bridge
        auth_url = tiktok_bridge.auth_url()
        reply_text = (
            "Berikut link otorisasi resmi TikTok untuk menghubungkan MARU HQ:\\n\\n"
            f"👉 {auth_url}\\n\\n"
            "Silakan klik tautan di atas dan klik 'Authorize' pada akun TikTok Anda!"
        )
        msg = _append_chat_message(bot_id, "assistant", reply_text, room=room)
        return {"ok": True, "reply": msg, "cards": sync_approval_cards()}

    if "status tiktok" in low or "cek tiktok" in low:
        from . import tiktok_bridge
        tok = tiktok_bridge.get_token()
        st = "✅ Terhubung ke TikTok (Token Aktif)" if tok else "⚠️ Belum terhubung ke TikTok. Ketik 'hubungkan tiktok' untuk otorisasi."
        msg = _append_chat_message(bot_id, "assistant", st, room=room)
        return {"ok": True, "reply": msg, "cards": sync_approval_cards()}
### TIKTOK INTERCEPT END ###
'''
        target_marker = 'def chat_with_agent(bot_id: str, prompt: str, room: str = "tim-maru") -> dict:'
        if target_marker in code:
            code = code.replace(target_marker, target_marker + "\n" + tiktok_block, 1)
            hm_path.write_text(code, encoding="utf-8")
            print("  -> src/hermes_mausbot.py: Intercept TikTok berhasil disuntikkan di puncak chat.")

    # 3. Import & Ambil Link
    import os
    sys.path.insert(0, str(proj))
    from src import tiktok_bridge
    link = tiktok_bridge.auth_url()
    print("\n" + "=" * 65)
    print("🔗 LINK OTORISASI TIKTOK RESMI (KLIK LANGSUNG DI BAWAH INI):")
    print(link)
    print("=" * 65 + "\n")

if __name__ == "__main__":
    main()
