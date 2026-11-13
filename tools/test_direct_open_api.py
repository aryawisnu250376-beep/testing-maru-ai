# Uji apakah endpoint open-api.tiktok.com/oauth/access_token merespons
import urllib.request
import urllib.parse

url = "https://open-api.tiktok.com/oauth/access_token/"
try:
    data = urllib.parse.urlencode({
        "client_key": "sbawpglo7h68u75jdb",
        "client_secret": "test",
        "code": "test_code",
        "grant_type": "authorization_code"
    }).encode('utf-8')
    req = urllib.request.Request(url, data=data)
    with urllib.request.urlopen(req, timeout=5) as r:
        print("open-api status:", r.status)
except urllib.error.HTTPError as e:
    print(f"open-api HTTP {e.code}: {e.read(200).decode('utf-8', errors='ignore')}")
except Exception as e:
    print("Err:", e)
