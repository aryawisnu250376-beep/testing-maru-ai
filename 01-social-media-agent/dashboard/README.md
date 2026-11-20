# MARU Corporate HQ — dashboard

Dari root repository, jalankan:

```sh
cd 01-social-media-agent
python -m pip install -e '.[dev]'
python -m src.dashboard --host 127.0.0.1 --port 8080 --skip-preflight --no-orchestrator
```

Buka `http://127.0.0.1:8080`. Untuk bind lokal tanpa `STUDIO_PASSWORD`, server membuat kata sandi sesi yang dicetak di terminal. Untuk bind nonlokal, atur `STUDIO_PASSWORD` minimal 16 karakter melalui environment server sebelum startup, dan gunakan reverse proxy HTTPS. Jangan menaruh kata sandi atau API key di HTML. `--skip-preflight` hanya mode pemeriksaan lokal; untuk instalasi render produksi, jalankan preflight normal dan penuhi kebutuhan FFmpeg serta dependensi media.

- Mulai dari **Virtual Office 3D** di sidebar. Three.js dan OrbitControls dimuat saat kantor dibuka; tanpa akses CDN/WebGL, tombol fallback membuka roster 2D.
- **Projects** menampilkan antrean HQ. Jalankan dari direktori kerja yang sama pada setiap startup karena `data/hq_core.db` bersifat relatif; ini berbeda dari database `data/pipeline.db` untuk Studio. Salinan modul HQ di root diperiksa agar identik dengan paket Social Media.
- Worker HQ memakai provider yang dikonfigurasi server (lihat `.env.example`; ekspor env melalui shell atau pengelola layanan). Tanpa provider, tugas tetap antre. `--no-worker` menghentikan worker HQ maupun Media; `--no-orchestrator` menonaktifkan orkestrator Media saja. Keluaran AI adalah rekomendasi; tidak mengesahkan atau menerbitkan konten.
- Chat dan draf Hermes memerlukan provider; reference watchlist tersimpan lokal dan dapat dipakai radar ketika ringkasan diisi. Saldo menampilkan tidak tersedia sampai sumber resmi disambungkan. `psutil` membaca kondisi host server, bukan perangkat browser.
- Tes lokal: `python -m pytest tests`. Tes browser opsional: `python -m pip install playwright && python -m playwright install chromium`, lalu `python -m pytest tests/test_corporate_browser.py`.
