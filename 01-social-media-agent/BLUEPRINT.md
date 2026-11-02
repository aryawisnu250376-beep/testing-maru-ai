# BLUEPRINT — AI Edukasi Agent

Keputusan desain, alasan di baliknya, dan apa yang belum dikerjakan.
`README.md` untuk cara pakai.

---

## 1. Prinsip

**1. Agent memutuskan, kode mengeksekusi.**
Hermes/Hermes-agent memilih tema dan menilai kualitas. Tapi render, TTS, caption, mux = kode deterministik dengan kontrak JSON. Menyerahkan seluruh loop ke agent membuat biaya token naik 5–10× dan hasil tidak reproducible.

**2. Manusia di satu titik yang tidak bisa diotomasi.**
Gerbang ACC diblokir di level kode (`render` melempar error tanpa `decision.json`), bukan di prompt. Prompt bisa dibujuk; kode tidak.

**3. Last mile pluggable.**
Upload publik TikTok adalah gerbang *audit*, bukan *engineering*. Sistem harus berguna penuh tanpa API itu.

**4. Default gratis, upgrade opsional.**
Tiap komponen punya jalur $0. Yang berbayar menaikkan kualitas, bukan syarat jalan.

**5. Jangan menyimpulkan dari data yang tipis.**
Learning loop butuh ≥3 video bermetrik. Di bawah itu ia diam — lebih baik tidak tahu daripada belajar dari kebetulan.

---

## 2. Kenapa frame-by-frame, bukan zoompan

Versi pertama memakai `zoompan` (satu gambar statis digeser/zoom). Cepat, tapi hanya bisa satu gerakan per scene. Untuk edukasi, yang menahan penonton adalah elemen yang **masuk bergantian**: kotak muncul satu-satu, panah tergambar, bar tumbuh dari nol, angka menghitung naik.

Semua butuh gambar ulang per frame.

Hasil pengukuran di 2 vCPU: **26,7 fps** untuk frame 1080×1920 — masih di atas 24 fps yang dibutuhkan, jadi layak. Kuncinya: background dibuat sekali per scene lalu di-`copy()` tiap frame, jadi biaya per frame hanya beberapa operasi draw.

Kalau nanti naik ke 4K atau 60 fps, jalur upgrade: pre-render background ke PNG, pakai numpy untuk komposit, atau pindah ke Remotion/Manim.

---

## 3. Kontrak JSON

Semua batas komponen lewat JSON. Ini yang membuat tiap bagian bisa dites terpisah.

**Cluster trend**
```json
{"theme":"on_device","label":"AI yang bisa jalan di HP sendiri",
 "angle_hint":"Kenapa AI sekarang muat di kantong, dan apa batasnya",
 "score":0.85,"sources":["github","huggingface"],
 "headline_signal":"...","evidence":[{"source":"github","title":"...","url":"...","score":0.8}]}
```

**Script**
```json
{"title":"...","format":"satu_konsep","hook":"maks 9 kata",
 "beats":[{"kind":"hook|point|limit|cta","narration":"maks 24 kata",
           "headline":"maks 5 kata","body":"maks 18 kata","source_refs":[0,2],
           "visual":{"type":"diagram","props":{"nodes":[{"title":"..","sub":".."}]}}}],
 "caption":"...","hashtags":["#AI"],"sources":[{"title":"...","url":"..."}],
 "generator":"llm|template","theme":"on_device"}
```

**Aturan yang ditegakkan validator** (ditolak sebelum render):
- 3–7 beat, narration ≤24 kata, body ≤18 kata, headline ≤5 kata
- tepat satu beat `kind=limit` (wajib menyebut batasan)
- beat pertama harus `hook`
- `sources[]` wajib, semua URL valid, **URL diambil dari cluster — model tidak boleh mengarang**
- visual wajib valid + props sesuai tipe (`diagram` butuh `nodes`, `stat` butuh `value`, …)
- daftar kata terlarang ("revolusioner", "game changer", …)
- peringatan kalau ada angka/versi model yang tidak ada di sumber

**Render meta** → `{video, cover, duration_sec, captions, layout:{ok,checked,problems}, timeline[]}`

**Publish package** → `{video, cover, caption, hashtags, full_caption, disclosure, sources, mode}`

---

## 4. Dua lapis penjagaan script

| Lapis | Fungsi | Contoh |
|---|---|---|
| **Sanitiser** | memperbaiki tanpa mengubah fakta | memotong narasi 31→24 kata, menambah beat `limit` yang hilang, mengganti visual tak dikenal dengan default |
| **Validator** | menolak kalau masih melanggar | tanpa `sources` → error; kata terlarang → error; `diagram` tanpa props → error |

Alasannya: LLM yang gagal format lebih sering "hampir benar" daripada "benar-benar salah". Membuang seluruh output karena satu beat kepanjangan itu pemborosan. Tapi kalau setelah diperbaiki masih melanggar, output dibuang.

Validator ini **sempat menolak script yang ditulis manusia** (di file `examples/demo_script.json`) karena 3 beat kelebihan kata. Itu bukti aturannya nyata, bukan hiasan.

---

## 5. Caption sinkron tanpa whisper

`edge-tts` dengan `boundary="WordBoundary"` mengirim timestamp per kata (satuan 100-nanosecond). Dari situ dibangun file ASS yang di-burn libass.

Kenapa ini penting: banyak pipeline memakai faster-whisper untuk word timing — itu benar tapi menambah ~75 MB model dan beberapa detik CPU per video. Untuk kasus ini tidak perlu, karena TTS-nya sendiri sudah tahu kapan tiap kata diucapkan.

Batasan: kalau nanti pindah ke TTS lain (ElevenLabs), jalur ini hilang dan faster-whisper jadi wajib.

Detail teknis yang sempat salah dan sudah diperbaiki:
- ASS memakai format `&HAABBGGRR` (BGR terbalik) — kuning `RGB(255,226,92)` = `&H005CE2FF`
- `MarginV 540` menaruh caption di ~72% tinggi, di atas chip sumber dan footer, di luar area UI TikTok

---

## 6. Last mile TikTok

| Fakta | Konsekuensi desain |
|---|---|
| Client belum audit → konten **dipaksa** `SELF_ONLY` | auto-post publik tidak bisa diandalkan di awal |
| Error `unaudited_client_can_only_post_to_private_accounts` | ditangani sebagai jalur normal, bukan crash |
| Unaudited: maks 5 user/24 jam, akun harus private | cukup untuk uji coba, tidak untuk produksi |
| Audit: URL verification + app review + compliance audit | 2–4 minggu, sering ditolak |
| Rate limit 6 init/menit, ~15 post/hari | cukup untuk 1–3 video/hari |

**Rencana berurutan**
- **A (sekarang)** `manual`: paket + `SIAP_UPLOAD.md`, 30 detik kerja manusia
- **B** `draft`: `MEDIA_UPLOAD` → masuk inbox TikTok, kamu tap publish
- **C** `direct`: setelah domain terverifikasi + app review + audit lulus

**Tidak akan dilakukan:** uploader unofficial (Playwright/Selenium ke UI TikTok). Begitu akun kena flag, seluruh pipeline kehilangan tujuan.

---

## 7. Learning loop

```
metrik (views, avg_watch, likes) → fitur script (tipe hook, visual, jumlah beat)
→ agregasi per fitur → pola pemenang → prompt scriptwriter berikutnya
```

Keputusan penting:

- **Retensi (`avg_watch / durasi`) dipakai sebagai sinyal utama, bukan views.** Views bisa naik karena keberuntungan algoritma; retensi lebih jujur soal apakah kontennya bekerja.
- **Skor gabungan** = 0,7 × retensi + 0,3 × engagement (komentar & share dibobot lebih tinggi dari like).
- **Minimum 3 sampel** sebelum menyimpulkan. Di bawah itu, `prompt_block()` mengembalikan string kosong — lebih baik tidak menyimpulkan apa pun.
- **Dimensi tanpa variasi diabaikan.** Kalau semua video punya 6 beat, "6 beat" bukan pola, itu kebetulan.
- Insight ditulis sebagai kalimat yang bisa ditindak, bukan tabel angka.

Yang disuntik ke prompt contohnya:
```
POLA YANG TERBUKTI DI KANAL INI (dari data metrik nyata, patuhi):
- tipe hook 'pertanyaan': retensi 55% (n=5)
- visual utama 'diagram': retensi 55% (n=5)
```

---

## 8. Antrean & konkurensi

Render 1 video ≈ 40–90 detik CPU. Kalau dipanggil langsung dari dashboard/cron, kegagalan tidak meninggalkan jejak dan dua render bisa tabrakan di 2 vCPU.

Solusi: tabel `jobs` di SQLite + klaim atomik `BEGIN IMMEDIATE`. Status: `queued → running → done | failed`, retry sampai `max_attempts`.

Yang terverifikasi jalan: job render tanpa ACC **ditolak dan di-retry lalu gagal** (2/2 percobaan), bukan menggantung.

Catatan operasional: satu worker cukup. Dashboard sudah menjalankan satu worker di thread latar; kalau kamu menjalankan `python -m src.cli worker` bersamaan, keduanya akan membagi job (tidak dobel, karena klaim atomik, tapi throughput tidak bertambah di 2 vCPU).

Jalur multi-mesin: ganti `BEGIN IMMEDIATE` jadi `FOR UPDATE SKIP LOCKED` di Postgres. Sisa kode tidak berubah.

---

## 9. Kenapa stdlib untuk dashboard

Flask/FastAPI menambah dependency dan attack surface untuk sesuatu yang isinya: satu halaman, 3 endpoint, streaming file. `http.server` stdlib cukup, tetap $0, dan tidak ada masalah versi.

Yang sudah ditangani: `Range` request untuk seek video, path traversal (`/artefact/../..` → 400), dan validasi `episode_id` dengan regex ketat.

Kalau nanti butuh multi-user/auth, baru pindah ke FastAPI.

---

## 10. Roadmap

### Sudah
- [x] Radar 5 sumber + scorer + 10 tema + bukti silang
- [x] Scriptwriter 2 lapis (sanitiser + validator) + LLM fallback chain
- [x] Render animasi 8 tipe scene + dubbing + caption per kata
- [x] Gerbang ACC (Telegram/CLI/file) yang memblokir render
- [x] QC teknis + QC layout area aman
- [x] Publish adapter 3 mode
- [x] Antrean + worker + retry
- [x] Dashboard (state, aksi, preview, antrean, pola)
- [x] Learning loop + memory pola
- [x] MCP server + Hermes config + cron installer
- [x] Docker, docker-compose, CI, workflow harian
- [x] 28 test

### Berikutnya (butuh data nyata, bukan kode)
- [ ] **Produksi 5 video & ukur retensi** ← gerbang keputusan sebenarnya
- [ ] Manim untuk scene konsep yang butuh diagram matematis/mekanisme
- [ ] A/B hook: dua varian, pilih berdasar retensi
- [ ] TikTok Display API untuk metrik otomatis (sekarang manual)
- [ ] Mode `draft` (TikTok app + OAuth)
- [ ] Multi-bahasa (struktur sudah siap: persona + voice per bahasa)
- [ ] Audit TikTok → `direct`

---

## 11. Definisi selesai

1. **7 video berturut-turut** tanpa intervensi selain ACC
2. Trend terdeteksi → siap publish **≤ 24 jam**
3. Intervensi manusia **≤ 5 menit per video**
4. QC teknis lulus **100%** tanpa perbaikan manual
5. Minimal **1 dari 7** video retensinya di atas rata-rata kanal

Jumlah fitur bukan ukuran. Kalau 1–5 tercapai, sistemnya jalan. Kalau tidak, menambah fitur hanya mempercepat produksi konten yang tidak ditonton.

---

## 12. Risiko & mitigasi

| Risiko | Dampak | Mitigasi |
|---|---|---|
| Konten terasa AI slop | akun mati | validator + wajib beat `limit` + analogi wajib + library format |
| Halusinasi fakta AI | kredibilitas hilang | URL dari cluster (bukan dari model) + warning versi model |
| TikTok membatasi/ToS | pipeline tanpa tujuan | mode manual default, tanpa UI automation |
| 9Router jalur OAuth consumer | akun provider kena | pakai API key resmi saja |
| TTS gratis rate-limit | render gagal | retry 3× + fallback durasi estimasi + audio senyap |
| Belajar dari sampel tipis | keputusan salah | minimum 3 sampel, abaikan dimensi tanpa variasi |
| Monoton setelah 30 video | retensi turun | library format + dedupe tema + learning loop |
| Render bertumpuk | CPU jenuh | antrean 1 job paralel |

---

## 13. Yang sengaja TIDAK dibangun

- **Uploader unofficial TikTok** — jalur tercepat akun kena flag
- **AI video generatif sebagai tulang punggung** — $1–5 per klip dan identitas visual tidak konsisten antar episode; edukasi butuh konsistensi
- **Agent yang bebas menjalankan semua langkah** — biaya naik, hasil tidak reproducible
- **Auto-post tanpa ACC** — kualitas turun dan risiko platform naik
- **Prediksi trend viral** — tidak ada yang bisa; yang realistis adalah deteksi dini + kecepatan eksekusi
