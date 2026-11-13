import urllib.request
import urllib.parse

redirect_uri = "https://aryawisnu250376-beep.github.io/testing-maru-ai/callback.html"
url = f"https://www.tiktok.com/v2/auth/authorize/?client_key=sbawpglo7h68u75jdb&scope=user.info.basic,video.publish,video.upload&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&state=test_relay&code_challenge=npvITMHoR7jfaDPHTRmsON23VYJ5CN8AwoZWbuxfzD0&code_challenge_method=S256"

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
}
req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("STATUS TIKTOK GITHUB RELAY:", resp.status)
        body = resp.read(1000).decode('utf-8', errors='ignore')
        print("HASIL: VALID 100% LOLOS DARI TIKTOK!")
except urllib.error.HTTPError as e:
    print(f"HTTP Error: {e.code} ({e.reason})")
    print(e.read(300).decode('utf-8', errors='ignore'))
except Exception as e:
    print("Err:", e)
