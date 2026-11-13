import zlib
import base64
from pathlib import Path

# Kita kemas studio_bulletproof.html ke file patch lokal
raw = Path("/home/user/studio_bulletproof.html").read_bytes()
compressed = base64.b64encode(zlib.compress(raw, 9)).decode("ascii")

script = f'''# -*- coding: utf-8 -*-
import zlib
import base64
from pathlib import Path

PAYLOAD = "{compressed}"

def main():
    target = Path("src/studio.html")
    if not target.exists():
        print("ERROR: src/studio.html tidak ditemukan. Pastikan berada di folder 01-social-media-agent.")
        return
    data = zlib.decompress(base64.b64decode(PAYLOAD.encode("ascii")))
    target.write_bytes(data)
    print("SUCCESS: src/studio.html telah diperbarui dengan pelindung DOM anti-null mutlak!")

if __name__ == "__main__":
    main()
'''

Path("/home/user/update_studio_bulletproof.py").write_text(script, encoding="utf-8")
print("update_studio_bulletproof.py siap! Ukuran:", len(script))
