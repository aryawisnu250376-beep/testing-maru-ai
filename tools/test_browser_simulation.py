import urllib.request
import urllib.parse

# Uji endpoint login kit web langsung dari IP Indonesia dengan header lengkap browser
url = "https://www.tiktok.com/login"
req = urllib.request.Request(url, headers={
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
})
try:
    with urllib.request.urlopen(req, timeout=5) as r:
        print("tiktok.com/login:", r.status)
except Exception as e:
    print("tiktok.com/login err:", e)
