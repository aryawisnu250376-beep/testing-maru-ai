import urllib.request
import urllib.parse

# Coba panggil https://www.tiktok.com/v2/auth/authorize/ dengan header lengkap Chrome
client_key = "sbawpglo7h68u75jdb"
redirect_uri = "https://maru-hq.localtest.me:8443/api/tiktok/callback"
scope = "user.info.basic,video.publish,video.upload"

url = (
    "https://www.tiktok.com/v2/auth/authorize/?"
    f"client_key={client_key}&scope={urllib.parse.quote(scope)}"
    f"&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&state=test_ok"
)

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/130.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
    "Accept-Language": "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7",
    "Sec-Ch-Ua": '"Chromium";v="130", "Google Chrome";v="130", "Not?A_Brand";v="99"',
    "Sec-Ch-Ua-Mobile": "?0",
    "Sec-Ch-Ua-Platform": '"Windows"',
    "Sec-Fetch-Dest": "document",
    "Sec-Fetch-Mode": "navigate",
    "Sec-Fetch-Site": "cross-site",
    "Upgrade-Insecure-Requests": "1"
}

req = urllib.request.Request(url, headers=headers)
try:
    with urllib.request.urlopen(req, timeout=10) as resp:
        print("Status code:", resp.status)
        content = resp.read(500).decode("utf-8", errors="ignore")
        print("Respon Berhasil:", content[:200])
except urllib.error.HTTPError as e:
    print(f"HTTP Error {e.code}: {e.reason}")
    body = e.read(500).decode("utf-8", errors="ignore")
    print(f"Detail Body: {body[:250]}")
except Exception as e:
    print("Error:", e)
