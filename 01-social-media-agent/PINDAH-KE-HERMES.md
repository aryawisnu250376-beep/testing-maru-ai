# Memindahkan Proyek ke Hermes (Windows 10 + WSL2)

Tujuan: Hermes menjadi "otak" yang memanggil 9Router, sementara dashboard & Ootto
tetap berjalan di proyek ini. Antrean persetujuan tetap satu lokasi.

## 0. Prasyarat
- Windows 10 dengan WSL2 (Ubuntu) terpasang.
- Python 3.14 & Node.js 24 di Windows; Python 3 di WSL2.
- 9Router sudah jalan di Windows: `http://localhost:20128` (dashboard `/dashboard`).

## 1. Ekstrak proyek di Windows
Ekstrak ZIP ke folder yang **bisa dibaca WSL2**, misalnya:
`C:\Users\<nama>\ai-edukasi-agent`
Di WSL2 folder itu terbaca sebagai `/mnt/c/Users/<nama>/ai-edukasi-agent`.

> Hindari menaruh proyek di `\\wsl$` jika dashboard dijalankan di Windows; pilih satu
> lokasi yang dibaca kedua sisi. Paling sederhana: proyek di drive C:, Hermes di WSL2.

## 2. Siapkan Hermes di WSL2
```bash
# di WSL2
pip install hermes-agent          # atau sesuai petunjuk resmi Nous Research
mkdir -p ~/.hermes
```
Salin konfigurasi contoh:
```bash
cp /mnt/c/Users/<nama>/ai-edukasi-agent/config/hermes/config.yaml ~/.hermes/config.yaml
```
Isi `ROUTER_API_KEY` (dari dashboard 9Router) sebagai environment variable di WSL2:
```bash
export ROUTER_API_KEY="isi_dari_dashboard_9router"
```

## 3. Arahkan Hermes ke 9Router
`config/hermes/config.yaml` sudah memakai `provider: custom` + `base_url`.
- WSL2 **mirrored networking** (Windows 11 / WSL terbaru): `http://localhost:20128/v1` biasanya langsung jalan.
- WSL2 lama / NAT: `localhost` WSL2 ≠ Windows. Pakai IP host Windows:
  ```bash
  ip route show default | awk '{print $3}'   # dapat IP Windows, mis. 172.30.x.x
  ```
  Ubah `base_url` menjadi `http://172.30.x.x:20128/v1` dan pastikan 9Router
  mengizinkan koneksi dari WSL2 (bind 0.0.0.0 atau port-proxy Windows).
  **Jangan** ekspos 9Router ke internet.

## 4. Daftarkan skill
Skill ada di `skills/` (format agentskills). Hermes mendukung `external_dirs`:
```yaml
skills:
  external_dirs:
    - /mnt/c/Users/<nama>/ai-edukasi-agent/skills
```
Uji satu per satu lewat Hermes:
```
/ringkas-modul /mnt/c/Users/<nama>/ai-edukasi-agent/masuk/CONTOH.md
/naskah-video
/cek-mutu
/usul-jadwal
```
Jika Hermes belum bisa, **fallback mandiri** tetap jalan dari Windows:
```powershell
python -c "from src.hermes4 import run_file; print(run_file('masuk/CONTOH.md'))"
```

## 5. Satu antrean, dua sisi
- Dashboard (Windows) menulis `antrean/<id>.json`.
- Hermes (WSL2) membaca/menulis folder `antrean/` yang sama lewat `/mnt/c/...`.
- Hanya **pemilik** yang memberi `DISETUJUI` lewat dashboard. Hermes tidak boleh.
- Uji baca-tulis dua sisi: buat file di Windows, pastikan terbaca di WSL2, dan sebaliknya.

## 6. Urutan menjalankan (satu perintah per komponen)
```powershell
# Terminal 1 (Windows): 9Router
9router
# Terminal 2 (Windows): dashboard + worker
.\scripts\start.ps1
# Terminal 3 (WSL2): Hermes (opsional, bila sudah terpasang)
hermes
# Terminal 4 (Windows): Ootto saat jatuh tempo
python -m ootto run-due
```

## 7. Keamanan yang tidak boleh dilanggar
- Token hanya di `.env` / environment, tidak di kode/Git.
- Repo **private**, perubahan lewat branch + PR.
- Tidak ada tayang tanpa `DISETUJUI` dari pemilik.
- Bawaan TikTok = draf/inbox; direct dikunci `OOTTO_ALLOW_DIRECT=false`.
- Bot Telegram & tugas terjadwal hanya satu mesin pada satu waktu.

## 8. Checklist lulus
- [ ] `python scripts/test-router.py` menjawab satu pertanyaan lewat 9Router.
- [ ] Hermes bisa ringkas `masuk/CONTOH.md` dengan nomor halaman bila PDF.
- [ ] File `antrean/<id>.json` terbaca dari Windows dan WSL2.
- [ ] Tombol SETUJU/TOLAK/REVISI di dashboard mengubah status + tercatat di log.
- [ ] Ootto menolak konten yang belum `DISETUJUI`.
