import urllib.request
import urllib.parse

client_key = "sbawpglo7h68u75jdb"
redirect_uri = "https://maru-hq.localtest.me:8443/api/tiktok/callback"
scope = "user.info.basic,video.publish,video.upload"

# Uji variasi URL TikTok Authorization
candidates = [
    # 1. Standar docs v2 authorize
    f"https://www.tiktok.com/v2/auth/authorize/?client_key={client_key}&scope={urllib.parse.quote(scope)}&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&state=maru2026",
    # 2. Tanpa trailing slash authorize
    f"https://www.tiktok.com/v2/auth/authorize?client_key={client_key}&scope={urllib.parse.quote(scope)}&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&state=maru2026",
    # 3. Web auth v1 / open auth dialog
    f"https://open-api.tiktok.com/platform/oauth/connect/?client_key={client_key}&scope={urllib.parse.quote(scope)}&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&state=maru2026",
    # 4. Standard open auth v2
    f"https://www.tiktok.com/auth/authorize/?client_key={client_key}&scope={urllib.parse.quote(scope)}&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&state=maru2026"
]

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
}

for idx, url in enumerate(candidates, 1):
    print(f"\n--- Menguji Kandidat URL #{idx} ---")
    print(f"URL: {url}")
    req = urllib.request.Request(url, headers=headers)
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:
            body = resp.read(500).decode("utf-8", errors="ignore")
            print(f"Status: {resp.status} - OK!")
            print(f"Head: {body[:150]}...")
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        err_body = e.read(500).decode("utf-8", errors="ignore")
        print(f"Err Body: {err_body[:200]}")
    except Exception as e:
        print(f"General Error: {e}")
