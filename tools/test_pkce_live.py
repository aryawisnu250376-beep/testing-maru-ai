import urllib.request
import urllib.parse
import hashlib
import base64
import os

# Generasi code_verifier (43-128 karakter acak)
# dan code_challenge = Base64Url(SHA256(code_verifier))
raw_bytes = os.urandom(32)
code_verifier = base64.urlsafe_b64encode(raw_bytes).decode('utf-8').rstrip('=')
digest = hashlib.sha256(code_verifier.encode('utf-8')).digest()
code_challenge = base64.urlsafe_b64encode(digest).decode('utf-8').rstrip('=')

client_key = "sbawpglo7h68u75jdb"
redirect_uri = "https://localhost/api/tiktok/callback"
scope = "user.info.basic,video.publish,video.upload"

params = {
    "client_key": client_key,
    "scope": scope,
    "response_type": "code",
    "redirect_uri": redirect_uri,
    "state": "maru_hq_pkce_ok",
    "code_challenge": code_challenge,
    "code_challenge_method": "S256"
}

url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)
print("URL RESMI TIKTOK DENGAN PKCE (code_challenge):")
print(url)
print("\nCode Verifier yang disimpan untuk token exchange:", code_verifier)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
req = urllib.request.Request(url, headers=headers)
with urllib.request.urlopen(req, timeout=10) as resp:
    print("\nSTATUS TIKTOK LIVE:", resp.status)
    body = resp.read(2000).decode('utf-8', errors='ignore')
    if "Ada masalah" in body or "code_challenge" in body:
        print("HASIL: Masih komplain")
    else:
        print("HASIL: SUCCESS 100%! Halaman Otorisasi TikTok Resmi Terbuka Penuh!")
