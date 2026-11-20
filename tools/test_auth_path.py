# Uji coba apakah endpoint TikTok auth menggunakan format:
# https://www.tiktok.com/auth/authorize/ vs https://www.tiktok.com/v2/auth/authorize/
# Cek apakah ada IP ban dari Akamai pada browser Chrome user
import urllib.request
print("Memeriksa status Akamai...")
