import urllib.parse

# Analisis gambar 49:
# Di screenshot 49, ada tab: Web*, Desktop, Android, iOS
# Di tab Web*: user mengisi 'https://maru-hq.localtest.me:8443/api/tiktok/callback'
# Namun perhatikan: di screenshot 51, pada bagian Platform yang dicentang adalah:
# [x] Web  [ ] Desktop  [ ] Android  [ ] iOS
# URL yang dicoba dibuka di Chrome:
# https://www.tiktok.com/v2/auth/authorize/?client_key=sbawpglo7h68u75jdb&scope=user.info.basic&response_type=code&redirect_uri=https%3A%2F%2Fmaru-hq.localtest.me%3A8443%2Fapi%2Ftiktok%2Fcallback&state=maru_auth_test
