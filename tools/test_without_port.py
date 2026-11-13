import urllib.parse
# Di screenshot 49, perhatikan:
# Web Redirect URI yang lu isi adalah:
# https://maru-hq.localtest.me:8443/api/tiktok/callback
# Namun beberapa firewall Akamai menolak port number ':8443' di query param redirect_uri!
# Mari kita uji perbandingannya:
url_port = "https://www.tiktok.com/v2/auth/authorize/?client_key=sbawpglo7h68u75jdb&scope=user.info.basic&response_type=code&redirect_uri=" + urllib.parse.quote("https://maru-hq.localtest.me:8443/api/tiktok/callback")
url_noport = "https://www.tiktok.com/v2/auth/authorize/?client_key=sbawpglo7h68u75jdb&scope=user.info.basic&response_type=code&redirect_uri=" + urllib.parse.quote("https://maru-hq.localtest.me/api/tiktok/callback")
print("Port:", url_port)
print("No Port:", url_noport)
