# Maru AI (Social Media Corporation)

Paket gabungan dari file Drive yang masih berguna. Ini **bukan satu aplikasi tunggal**,
melainkan bundel rapi agar mudah dipindah/ dicadangkan.

## Isi utama

| Folder | Isi | Keterangan |
|---|---|---|
| `01-social-media-agent/` | AI Edukasi Agent v3 + kerangka 4 Bot | Proyek utama konten edukasi: 9Router, Hermes, MausBot fallback, Ootto. |
| `02-academic-ai/` | Academic AI hybrid Manager-Ollama v5 | Aplikasi belajar/ Telegram/ web yang sudah ada di laptop. |
| `03-academic-data/` | Data Academic AI | PDF ber-hash, database, vectorstore. Jangan dihapus jika ingin data lama tetap terbaca. |
| `04-materi-kuliah/` | Salinan materi per mata kuliah | Nama file asli, dikelompokkan per mapel. Berasal dari data yang sama. |
| `05-demo-teknis/` | Demo render Nara | Hanya uji teknis; bukan persetujuan publikasi. |

## Mana yang asli?

- Untuk **konten edukasi / sosial media**: pakai `01-social-media-agent/`.
- Untuk **aplikasi belajar Academic AI**: pakai `02-academic-ai/` + `03-academic-data/`.
- `04-materi-kuliah/` adalah salinan mudah dibaca; sumber aplikasi tetap `03-academic-data/`.

## Cara pakai singkat

### Social Media Agent
```powershell
cd 01-social-media-agent
copy .env.example .env
notepad .env
.\scripts\start.ps1
```
Baca `FRAMEWORK4.md` dan `PINDAH-KE-HERMES.md`.

### Academic AI
```powershell
cd 02-academic-ai
copy .env.example .env
notepad .env
```
Ikuti `MANUAL_BOOK_PEMASANGAN.md` / `.docx` dan `PANDUAN_OLLAMA_HERMES.md`.
Jika ingin memakai data lama, salin folder `data/` dari `03-academic-data/` ke folder aplikasi
**setelah mencadangkan data yang sudah ada**.

## Keamanan

- Tidak ada `.env` asli, token, atau private key yang sengaja disertakan.
- Database Academic AI dapat memuat data pengguna/aktivitas. Jangan bagikan paket ini ke publik.
- Social Media Agent tetap memakai aturan: tidak ada unggah TikTok tanpa persetujuan manusia.
- Jangan jalankan dua bot Telegram dengan token sama di dua mesin sekaligus.

## Catatan integrasi

Kedua aplikasi bisa sama-sama memakai 9Router/Hermes, tetapi tetap dipisah agar dependensi
dan database tidak bentrok. Integrasi penuh dapat dilakukan bertahap setelah paket ini dijalankan.
