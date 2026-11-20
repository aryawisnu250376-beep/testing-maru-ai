import urllib.request
import urllib.parse

client_key = "sbawpglo7h68u75jdb"
redirect_uri = "https://maru-hq.localtest.me:8443/api/tiktok/callback"

endpoints = [
    "https://open-api.tiktok.com/platform/oauth/connect/",
    "https://open.tiktokapis.com/v2/auth/authorize/",
    "https://auth.tiktok.com/v2/auth/authorize/",
    "https://login.tiktok.com/v2/auth/authorize/",
    "https://web.tiktok.com/v2/auth/authorize/",
    "https://www.tiktok.com/v2/auth/authorize/"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}

for ep in endpoints:
    url = f"{ep}?client_key={client_key}&scope=user.info.basic&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&state=test"
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as r:
            print(f"OK ({r.status}): {ep}")
    except urllib.error.HTTPError as e:
        print(f"HTTP {e.code} ({e.reason}): {ep}")
    except Exception as e:
        print(f"FAIL ({type(e).__name__}): {ep} -> {e}")
