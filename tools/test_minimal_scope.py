import urllib.parse
import urllib.request

# Kunci dari user
client_key = "sbawpglo7h68u75jdb"
redirect_uri = "https://maru-hq.localtest.me:8443/api/tiktok/callback"

# Uji 1: Scope bawaan wajib Login Kit saja (user.info.basic)
url1 = f"https://www.tiktok.com/v2/auth/authorize/?client_key={client_key}&scope=user.info.basic&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&state=test_basic"

# Uji 2: Scope video.publish + video.upload (Content Posting)
url2 = f"https://www.tiktok.com/v2/auth/authorize/?client_key={client_key}&scope=user.info.basic,video.publish,video.upload&response_type=code&redirect_uri={urllib.parse.quote(redirect_uri)}&state=test_all"

print("Uji 1 (user.info.basic saja):")
print(url1)
print("\nUji 2 (dengan scope posting):")
print(url2)
