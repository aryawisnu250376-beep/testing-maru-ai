import urllib.parse

redirect_uri = "https://maru-hq.localtest.me:8443/api/tiktok/callback"
client_key = "sbawpglo7h68u75jdb"
scope = "user.info.basic,video.publish,video.upload"
state = "test_state_123"

params = {
    "client_key": client_key,
    "scope": scope,
    "response_type": "code",
    "redirect_uri": redirect_uri,
    "state": state
}
url = "https://www.tiktok.com/v2/auth/authorize/?" + urllib.parse.urlencode(params)
print("URL Authorize Benar:")
print(url)
