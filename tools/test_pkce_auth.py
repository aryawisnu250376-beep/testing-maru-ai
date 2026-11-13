import urllib.request
import urllib.parse
import hashlib
import base64
import os

client_key = "sbawpglo7h68u75jdb"
redirect_uri = "https://maru-hq.localtest.me:8443/api/tiktok/callback"
scope = "user.info.basic"

# Buat code_verifier & code_challenge (PKCE)
code_verifier = base64.urlsafe_b64encode(os.urandom(32)).decode('utf-8').rstrip('=')
code_challenge = base64.urlsafe_b64encode(hashlib.sha256(code_verifier.encode('utf-8')).digest()).decode('utf-8').rstrip('=')

params = {
    "client_key": client_key,
    "scope": scope,
    "response_type": "code",
    "redirect_uri": redirect_uri,
    "state": "test_state_desktop",
    "code_challenge": code_challenge,
    "code_challenge_method": "S256"
}

url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)
print("URL dengan PKCE:")
print(url)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=5) as resp:
        print("Status PKCE:", resp.status)
except urllib.error.HTTPError as e:
    print(f"HTTP Error PKCE: {e.code} - {e.reason}")
    print(e.read(200).decode('utf-8', errors='ignore'))
except Exception as e:
    print("Err:", e)
