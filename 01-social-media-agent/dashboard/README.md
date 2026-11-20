# MARU Corporate HQ — dashboard

Dari root repository, jalankan:

```sh
cd 01-social-media-agent
python -m pip install -e '.[dev]'
export STUDIO_PASSWORD="$(python -c 'import secrets; print(secrets.token_urlsafe(24))')"
python -m src.dashboard --host 127.0.0.1 --port 8080 --skip-preflight --no-orchestrator
```

Buka `http://127.0.0.1:8080`. Atur `STUDIO_PASSWORD` minimal 16 karakter melalui environment server atau secret manager. Gunakan nilai yang sudah Anda simpan untuk bisa login; contoh menghasilkan nilai sementara (baca variabel itu di terminal privat bila perlu). Server tidak mencetak kata sandi. Untuk bind nonlokal, gunakan reverse proxy HTTPS. Jangan menaruh kata sandi atau API key di HTML. `--skip-preflight` hanya mode pemeriksaan lokal; untuk instalasi render produksi, jalankan preflight normal dan penuhi kebutuhan FFmpeg serta dependensi media.

- Mulai dari **Virtual Office 3D** di sidebar. Three.js dan OrbitControls dimuat saat kantor dibuka; tanpa akses CDN/WebGL, tombol fallback membuka roster 2D.
- **Projects** menampilkan antrean HQ. Jalankan dari direktori kerja yang sama pada setiap startup karena `data/hq_core.db` bersifat relatif; ini berbeda dari database `data/pipeline.db` untuk Studio. Salinan modul HQ di root diperiksa agar identik dengan paket Social Media.
- Worker HQ memakai provider yang dikonfigurasi server (lihat `.env.example`; ekspor env melalui shell atau pengelola layanan). Tanpa provider, tugas tetap antre. `--no-worker` menghentikan worker HQ maupun Media; `--no-orchestrator` menonaktifkan orkestrator Media saja. Keluaran AI adalah rekomendasi; tidak mengesahkan atau menerbitkan konten.
- Chat dan draf Hermes memerlukan provider; reference watchlist tersimpan lokal dan dapat dipakai radar ketika ringkasan diisi. Saldo menampilkan tidak tersedia sampai sumber resmi disambungkan. `psutil` membaca kondisi host server, bukan perangkat browser.
- Tes lokal: `python -m pytest tests`. Tes browser opsional: `python -m pip install playwright && python -m playwright install chromium`, lalu `python -m pytest tests/test_corporate_browser.py`.

## Phase 6.2 server contracts

- Set `MARU_INTERNAL_BOOTSTRAP_SECRET` to a unique, randomly generated server secret before starting the standalone HQ orchestrator; never pass it to a browser or an agent. Internal memory writes and non-public reads require an authority-issued token. `reader_agent_id`/`actor_id` remain compatibility hints but no longer provide authorization. Only records intentionally classified `ORGANIZATIONAL` remain readable anonymously at the in-process API.
- `GET /api/hq/jobs/{task_id}` exposes completed output and recorded review to an authenticated Studio owner. `POST /api/action` with `action: hq_job_review`, `task_id`, and `decision: APPROVED|REVISION` records one owner decision; it does not publish or auto-execute recommendations.
- `GET /api/watchlist?offset=N` exposes the authenticated paginated list. Reference radar uses the untruncated list.
- Direct TikTok upload is `DIKIRIM_TIKTOK` until Ootto polls a confirmed `PUBLISH_COMPLETE`; `python -m ootto run-due` (see `python -m ootto --help`) must be scheduled for reconciliation. No TikTok call is needed to start Studio or HQ.
- `ootto_attach_approved_video` is an authenticated API handoff for a Queue4 item already approved by the owner. Send `content_id`, `episode_id`, and `confirmed: true` only after verifying the video matches the draft. The episode must have independent current script approval, a rendered file under its output directory, and matching QC. This does not create the episode, schedule a post, or transmit a video.
- Browser-submitted Hermes source files must be inside the configured `HERMES_INPUT_DIR` (default `masuk/`). Pass a path relative to that directory. The standalone Hermes CLI retains its local-operator input contract.

### Alur pemilik di Studio

- **Workflow** → **Tinjau naskah & sumber** untuk membaca isi sebelum ACC. Jika naskah episode berubah setelah panel dibuka, buka ulang panel dan periksa versi terbaru.
- Pada kartu draf yang sudah ACC, **Tautkan video lolos QC** memakai ID episode yang sudah ACC, dirender, dan lolos QC. Studio tidak membuat atau merender episode baru dari teks bebas. Jadwal baru tersedia setelah ada artefak sah dan QC tercatat; jadwal tidak langsung melakukan upload.
- **Periksa kegagalan** hanya menawarkan pengembalian ke antrean tinjauan jika upload diketahui belum dicoba. Jadwal dan tautan sebelumnya dilepas. Jika hasil upload belum diketahui, periksa secara manual di TikTok; Studio tidak menawarkan kirim ulang.
- **Office** → **Projects** → pilih tugas untuk melihat hasil/kesalahan dan mencatat keputusan. Status `COMPLETED` tetap berbeda dari keputusan pemilik. **Studio** memuat watchlist 100 referensi per halaman; panel chat hanya menampilkan percakapan agen yang dipilih.
