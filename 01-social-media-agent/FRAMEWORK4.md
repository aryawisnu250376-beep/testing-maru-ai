# Kerangka Kerja 4 Bot — 9Router · Hermes · MausBot · Ootto

Dibangun **di atas** AI Edukasi Agent — Studio Otonom, bukan dari nol.
Aturan utama: **tidak ada konten tayang di TikTok tanpa persetujuan manusia.**

## Arsitektur (kode nyata di repo ini)

| Komponen | Kode | Peran | Batas keras |
|---|---|---|---|
| 9Router | `src/router9.py` | Satu pintu model, fallback | Tidak menyimpan isi percakapan |
| Hermes | `src/hermes4.py`, `src/skills4.py`, `skills/` | Otak: ringkas, naskah, cek-mutu, usul-jadwal | Tidak mengubah ACC, tidak memanggil Ootto |
| MausBot | `src/dashboard.py` + `src/studio.html` (halaman **4 Bot**) | Tampilan + antrean persetujuan | Tidak mengarang konten |
| Ootto | `ootto/` | Penjadwal + konektor TikTok | Hanya memproses `DISETUJUI` |

Antrean bersama: `src/queue4.py` → satu file JSON per konten di `antrean/<id>.json`.
Semua perubahan status dicatat di `log/aktivitas.log` (waktu, pelaku, alasan).

### Status
`DRAF → MENUNGGU → (pemilik) DISETUJUI / DITOLAK / REVISI → (Ootto) TERJADWAL → DRAF_TIKTOK / TAYANG / GAGAL`

- Hanya **pemilik** yang boleh menulis `DISETUJUI` (uji: `test_hermes_tidak_bisa_setuju`, `test_ootto_tidak_bisa_memberi_acc`).
- Ootto menolak semua status selain `DISETUJUI` dan mencatat alasannya (`test_ootto_menolak_non_disetujui`).
- Label AI wajib; tanpa label, Ootto menolak (`test_label_ai_wajib`).

## Hasil verifikasi dokumentasi resmi (sebelum membangun)

| Hal | Hasil | Tindakan |
|---|---|---|
| 9Router endpoint OpenAI kustom | **Ya.** `http://localhost:20128/v1`, dashboard `/dashboard`. [1](https://9router.com/) | Dipakai apa adanya; nama model dari dashboard, tidak ditebak |
| Hermes endpoint OpenAI kustom | **Ya.** `provider: custom` + `base_url` di `config.yaml`. [2](https://hermes-agent.nousresearch.com/docs/integrations/providers) | `config/hermes/config.yaml`; fallback skill Python memanggil 9Router langsung |
| MausBot pakai Hermes/9Router | **Sebagian.** MausBot/OpenMausBot mendukung instance `openai-compat`, tapi jalur chat+reasoning saja tanpa tool calls. [3](https://github.com/milind-soni/OpenMausBot/blob/main/docs/custom-engines.md) | **Dashboard web cadangan** membaca antrean JSON yang sama; contoh instance di `config/mausbot.contoh.json` |
| Batas TikTok belum audit | **Benar.** Direct Post unaudited = `SELF_ONLY`, maks 5 pengguna/24 jam; aplikasi uji/pribadi tidak diterima. [4](https://developers.tiktok.com/docs/en/content-sharing-guidelines) | Bawaan **draft/inbox**; direct dikunci `OOTTO_ALLOW_DIRECT=false` |
| Ootto | Tidak teridentifikasi sebagai alat baku | Dibangun sebagai modul sesuai 3 fungsi: `jadwalkan`, `status`, `batalkan` |
| WSL2 baca folder Windows | Perlu pemetaan jalur / mirrored networking. [2](https://hermes-agent.nousresearch.com/docs/integrations/providers) | Antrean satu lokasi; uji baca-tulis di mesin pemilik |

> **Penting soal jadwal:** TikTok Content Posting API tidak menyediakan jadwal publik
> native untuk semua akun. Ootto menjadwalkan **pengiriman secara lokal**, lalu mengunggah
> saat jatuh tempo. Jangan menjanjikan tayang publik otomatis sebelum audit lulus.

## Cara menjalankan (pemula, satu perintah per komponen)

```powershell
# Windows: dashboard + worker
.\scripts\start.ps1
```
```bash
# Linux/macOS/WSL2
bash scripts/start.sh
```

Komponen lain (opsional, terpisah):
```bash
npm install -g 9router && 9router          # 9Router, lalu isi ROUTER_* di .env
python scripts/test-router.py              # Tahap 1: satu pertanyaan harus dijawab
python -c "from src.hermes4 import run_file; print(run_file('masuk/CONTOH.md'))"  # Hermes mandiri
python scripts/ootto-auth.py               # OAuth TikTok resmi (bukan password)
python -m ootto schedule <id> 2026-11-03T19:00:00+07:00
python -m ootto run-due                    # kirim yang jatuh tempo (hanya DISETUJUI→TERJADWAL)
```

## Keamanan
- Semua token/key di `.env` (di-ignore Git). `.env.example` tanpa nilai rahasia.
- Repo harus **private**; perubahan lewat branch + pull request, bukan push ke `main`.
- Tidak ada komponen meminta password TikTok; OAuth bisa dicabut (`ootto.tiktok.revoke`).
- Bot Telegram & tugas terjadwal hanya satu mesin pada satu waktu.

## Alat riset opsional (`src/research4.py`)
SearXNG, Crawl4AI, MarkItDown, youtube-transcript-api. Semuanya mengembalikan error
jujur bila belum terpasang. Prioritas lanjut: Miniflux, Remotion, Manim, Firecrawl.

## Uji
```bash
python -m pytest tests/test_framework4.py -q   # 12 uji aturan persetujuan
python -m pytest -q                            # seluruh suite
```
