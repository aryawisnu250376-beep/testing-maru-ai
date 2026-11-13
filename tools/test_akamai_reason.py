import urllib.request
import urllib.parse

# Mari kita periksa: apakah URL authorize tanpa query parameter sama sekali ditolak oleh Akamai?
base_url = "https://www.tiktok.com/v2/auth/authorize/"
headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8"
}

req = urllib.request.Request(base_url, headers=headers)
try:
    urllib.request.urlopen(req, timeout=5)
    print("Base URL langsung: DITERIMA 200")
except urllib.error.HTTPError as e:
    print(f"Base URL langsung: DITOLAK {e.code} ({e.reason})")
    body = e.read(300).decode('utf-8', errors='ignore')
    print("Respon:", body[:180])
