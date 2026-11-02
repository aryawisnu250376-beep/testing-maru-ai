# AI Edukasi Agent

Agent yang **mencari ide sendiri → menulis script → minta ACC kamu → render video animasi + dubbing → menyiapkan upload TikTok**, dengan radar trend harian, dashboard, dan loop belajar dari performa.

**Tidak ada tombol yang perlu kamu tekan.** Delapan agent bekerja terus selama
proses hidup; kamu hanya masuk di satu titik: setujui atau revisi.

Mulai dari **Rp 0**: tanpa API key, tanpa kartu kredit, tanpa GPU.

```
riset → ide → skrip → [KAMU: ACC / revisi] → animasi → dubbing → QC → publikasi
 └──────────── 8 agent, jalan sendiri ─────────┘  └──── jalan setelah kamu ACC ────┘
```

---

## Bukti, bukan janji

| Klaim | Cara verifikasi |
|---|---|
| Pipeline jalan end-to-end | `make demo`, atau lihat `out/*/final.mp4` |
| Render + dubbing + caption jadi video | `out/<ep>/final.mp4` — 1080×1920, 44,1 kHz, −14 LUFS |
| Gerbang ACC benar-benar memblokir | `python -m src.cli render <ep>` sebelum ACC → ditolak |
| **69 test lulus** | `make test` |
| Lint bersih | `make lint` |
| Lingkungan sehat 10/11 | `make doctor` |
| Otonomi tidak melewati gerbang ACC | `test_otonomi_tidak_pernah_render_tanpa_acc` |
| Satu klik ACC → video jadi tanpa trigger | approve di studio → `animasi`/`dubbing` menyala sendiri |
| Musik latar terdengar & ducking nyata | `out/<ep>/work/music_*.wav`; test `test_musik_bed_terdengar_pada_level_config` |
| Animasi vektor Manim benar-benar ke video | `out/<ep>/work/manim_*.mp4` + field `animator` di `render_meta.json` |
| Animasi > realtime | 26,7 fps di 2 vCPU (butuh 24 fps) |
| QC teknis otomatis | `out/<ep>/qc_report.json` |
| Learning loop menyimpulkan pola | `python scripts/demo_learning.py` |

---

## Studio: dashboard-nya adalah animasi

`make studio` → <http://localhost:8080>. Yang tampil **hanya** studio:

- **8 meja agent** di atas panggung. Agent yang sedang bekerja menyala, cincin
  progres berputar, dan dokumen mengalir di garis antar-meja. Yang menganggur redup.
- **Node "KAMU"** di tengah: gerbang ACC. Menyala kuning selama ada naskah menunggu.
- **Tombol kiri**: daftar pekerjaan tiap agent (sedang apa, progres, berapa lama)
  dan antrean ACC dengan tombol **Setujui / Revisi / Tolak**.

Tidak ada tombol scan, tulis, atau render — memang tidak diperlukan. Semua
digerakkan `src/orchestrator.py`, dan animasinya membaca tabel `agent_tasks`
yang sama yang ditulis agent, jadi tampilannya tidak pernah mengarang.

### Delapan agent dan satu-satunya tugasnya

| Agent | Tugas |
|---|---|
| Riset | Pindai tren, sumber, dan watchlist referensi |
| Ide | Pilih sudut cerita yang belum pernah dibahas |
| Skrip | Tulis hook, beat narasi, spec visual |
| Revisi | Perbaiki naskah sesuai catatanmu (per aspek) |
| Animasi | Bangun scene: Pillow + Manim |
| Dubbing | Suara, musik latar, sfx |
| QC | Durasi, loudness, layout |
| Publikasi | Paket siap-upload TikTok |

### Yang tetap tidak otomatis

- **Render** hanya jalan setelah ada `decision.json` berisi `approve`. Itu
  diperiksa ulang di dalam orkestrator, bukan hanya di UI.
- **Upload publik** tetap manual (butuh audit TikTok). Agent menyiapkan paket.

---

## Mulai 3 menit

```bash
cd ai-edukasi-agent
make setup                            # pasang dependency + diagnosa lingkungan
make test                             # pastikan sehat
make scan                             # lihat apa yang naik hari ini
make demo                             # alur penuh, berhenti di gerbang ACC
```

Atau lewat dashboard:

```bash
make studio                           # http://localhost:8080 — agent mulai bekerja
```

Dashboard bisa: scan, tulis script, ACC/tolak, render, QC, siapkan paket upload, lihat antrean, dan memutar preview video — semuanya dari browser.

---

## Arsitektur

```
┌─ TREND RADAR (cron / dashboard)
│   HN · HuggingFace · GitHub · Google Trends ID · YouTube(opsional)
│   → skor: relevansi × momentum × kebaruan × kecocokan-format
│   → klasifikasi 10 tema + bonus bukti silang antar sumber
│
├─ SCRIPTWRITER (LLM kalau ada, template kalau tidak)
│   → JSON ketat: hook, 5-7 beat, **spec visual per beat**, caption, sumber
│   → sanitiser (perbaiki) + validator (tolak kalau masih langgar)
│
├─ ★ APPROVAL GATE (Telegram / CLI / file)
│   → render DIBLOKIR di level kode sebelum ACC
│
├─ RENDER (hybrid: Pillow frame-by-frame + Manim vector)
│   edge-tts + word boundary → ukur durasi → 9 tipe scene
│   per beat: `animator: auto` pilih pillow atau manim → stream ke ffmpeg
│   → musik latar + sfx (sidechain ducking) → caption ASS per kata → loudnorm
│
├─ QC TEKNIS
│   durasi · resolusi · fps · loudness −14 LUFS · clipping · jeda hitam
│   + cek layout: teks tidak masuk area UI TikTok
│
├─ PUBLISH ADAPTER
│   manual (default) · draft inbox · direct API (butuh audit TikTok)
│
└─ LEARNING LOOP
    metrik → fitur → pola pemenang → disuntik ke prompt berikutnya
```

Komponen: `trend_radar` · `trends_tiktok` · `scriptwriter` · `revisor` · `approve` · `anim`+`visuals`+`manim_scene` · `captions` · `audio` · `render` · `qc` · `publish` · `learning` · `queue` · `watch` · `providers` · `dashboard` · `mcp_server` · `cli`

---

## Tampilan video

9 tipe scene, dipilih otomatis dari `visual.type` di script. Enam di antaranya bisa dirender sebagai **Manim** (vektor, `-q l`, 1080×1920@24) bila `manim` terpasang — kalau tidak, otomatis fallback ke Pillow:

| Tipe | Dipakai untuk |
|---|---|
| `card` | pernyataan besar + penjelasan |
| `diagram` | alur kotak berurutan, panah tergambar |
| `steps` | daftar langkah bernomor |
| `bars` | perbandingan yang tumbuh dari nol |
| `stat` | angka besar menghitung naik |
| `compare` | dua kolom (dulu/sekarang, mitos/fakta) |
| `code` | blok terminal yang mengetik |
| `quote` | kutipan besar untuk CTA |
| `manim` | override eksplisit; spec Manim dari 6 scene di atas |

**Audio**: musik latar disintesis sendiri (`numpy`, tanpa file berlisensi) dengan mood otomatis dari tema — `tech` / `calm` / `curious` — plus sfx `whoosh`/`pop`/`riser`. Musik ditekan otomatis saat narator bicara via `sidechaincompress` (terbukti −74 % energi musik).

Plus: caption sinkron **per kata** (highlight kuning, dari timestamp edge-tts — tanpa whisper), progress bar per scene, chip sumber, dan layout yang sadar area aman TikTok.

---

## Biaya: semua nol

| Komponen | Yang dipakai | Biaya |
|---|---|---|
| Trend | HN, HuggingFace, GitHub, Google Trends RSS | $0 |
| Script | template offline **atau** LLM gratis (Ollama/Groq/Gemini/9Router) | $0 |
| Dubbing | `edge-tts` `id-ID-ArdiNeural` | $0 |
| Animasi | Pillow + ffmpeg | $0 |
| Caption | edge-tts word boundary + libass | $0 |
| State | SQLite | $0 |
| Dashboard | `http.server` stdlib (tanpa Flask) | $0 |
| ACC | Telegram Bot API | $0 |

Yang berbayar (belum dipakai): ElevenLabs, Veo/Kling, VPS, audit TikTok.

---

## Perintah

```bash
# produksi
python -m src.cli scan                        # radar trend
python -m src.cli script [--theme on_device]  # tulis script + validasi
python -m src.cli approve <ep> [--wait 600]   # kirim untuk ACC
python -m src.cli resume <ep>                 # lanjut + render kalau ACC
python -m src.cli render <ep>                 # render ulang
python -m src.cli qc <ep>                     # QC teknis
python -m src.cli publish <ep> [--mode draft] # paket upload

# operasional
python -m src.cli enqueue render <ep>         # masuk antrean
python -m src.cli worker [--once]             # proses antrean
python -m src.cli jobs                        # lihat antrean
python -m src.cli learn                       # laporan pola pemenang
python -m src.cli metrics <ep> --views 1200 --avg-watch 22 --likes 80
python -m src.cli list                        # status semua episode
python -m src.cli doctor                      # diagnosa: ffmpeg, paket, 9Router
python -m src.cli dashboard                   # web UI :8080
python -m src.mcp_server                      # MCP server untuk Hermes

# otonom selama laptop nyala
python -m src.cli studio                      # agent bekerja sendiri, tanpa trigger
python -m src.cli studio --once               # satu langkah kerja (untuk debug)
./scripts/autostart.sh install                # pasang launchd/systemd: hidup sendiri
./scripts/autostart.sh status                 # cek apakah studio jalan
python -m src.cli watch --interval 6          # mode lama: hanya siapkan episode

# revisi per-aspek sebelum ACC
python -m src.cli revise <ep> list            # hook|body|narration|visual|length|caption|sources
python -m src.cli revise <ep> narration --shortcut hook_lebih_pendek

# referensi & model
python -m src.cli harvest                     # amati referensi → pola + tema
python -m src.cli providers                   # probe semua model 9Router
```

Semua subcommand mendukung `--json` (output manusia ke stderr, JSON ke stdout) — aman dipanggil agent.

---

## Integrasi Hermes Agent

Pakai **MCP**, bukan shell bebas:

```bash
python -m src.hermes_skill config     # cetak YAML siap tempel
```

10 tool yang diekspos: `scan_trends`, `list_topics`, `write_script`, `request_approval`, `render_video`, `qc_video`, `publish_video`, `record_metrics`, `learning_report`, `list_episodes`.

`publish_video` ditandai butuh konfirmasi. Skill & jadwal ada di `config/hermes/`.

Tanpa Hermes pun jalan: `scripts/install_cron.sh` memasang jadwal 07:00 & 16:00.

---

## Deploy

```bash
docker compose up -d --build      # dashboard + worker, volume data/out
make docker                        # sama, plus lihat log
```

CI di `.github/workflows/ci.yml` (test + smoke test tiap push), produksi harian di `daily.yml` (menyiapkan episode, **tidak** render otomatis).

---

## Batas jujur versi ini

- **Visual = motion graphics**, bukan animasi karakter/3D. Konsisten dan murah; bukan gaya "animasi penuh".
- **Template tanpa LLM tulisannya generik.** Jaring pengaman, bukan pengganti LLM.
- **Trend radar tidak membaca TikTok.** Tidak ada API trend publik; pengganti: HN+HF+GitHub+Google Trends+YouTube (opsional). Sinyal TikTok datang lewat metrik akun sendiri.
- **Learning butuh ≥3 video bermetrik** sebelum menyimpulkan apa pun (sengaja, supaya tidak belajar dari kebetulan).
- **Upload publik TikTok butuh audit.** Default `manual` — 30 detik kerja manusia per video.
- **Satu mesin.** Antrean pakai SQLite; kalau butuh multi-mesin, ganti klaim ke Postgres.
- **Belum ada model LLM yang terbukti hidup.** Semua 71 model di `src/providers.py` berstatus `unreachable` karena 9Router tidak jalan di mesin build. Jalankan 9Router di `localhost:20128`, lalu `python -m src.cli providers` (atau tombol **Cek model** di dashboard) untuk membuktikan mana yang hidup.
- **`data/reference_watchlist.json` masih berisi 1 contoh.** Isi dengan akun referensi nyata sebelum produksi; `harvest` hanya sekuat daftar ini.
- **Studio butuh prosesnya hidup.** Kalau laptop sleep atau terminal ditutup, agent berhenti. `scripts/autostart.sh` memasangnya sebagai service user supaya ikut nyala saat login, tapi tetap mati saat laptop benar-benar tidur.
- **Otonomi ≠ tanpa pengawasan.** Agent berhenti menambah episode begitu antrean ACC penuh (`max_pending_approval`, default 2). Kalau kamu tidak pernah membuka ACC, ia akan diam dan hanya belajar — itu disengaja.
- **Belum ada LLM.** Semua langkah jalan dengan penulis template. Begitu 9Router hidup, `scriptwriter` otomatis memakai LLM dan kualitas naskah naik tanpa mengubah alur.

---

## Dokumen

- **[ANALISIS.md](ANALISIS.md) — kekurangan, roadmap prioritas, dan kerangka berpikir agent**
- [BLUEPRINT.md](BLUEPRINT.md) — keputusan desain, kontrak JSON, roadmap, rencana audit TikTok
- [config/persona.yaml](config/persona.yaml) — suara brand & rubrik kualitas
- [config/hermes/skills/konten-ai/SKILL.md](config/hermes/skills/konten-ai/SKILL.md) — aturan agent


---

## Kerangka 4 Bot (tambahan)

Proyek ini sekarang juga menjalankan kerangka **9Router · Hermes · MausBot · Ootto**
di atas pipeline yang sudah ada. Lihat **[FRAMEWORK4.md](FRAMEWORK4.md)**.

- Antrean persetujuan bersama: `src/queue4.py` (satu JSON per konten).
- Hanya **pemilik** yang boleh memberi `DISETUJUI`; Ootto menolak status lain.
- Bawaan TikTok = **draf/inbox**, bukan tayang publik otomatis.
- Dashboard web punya halaman **4 Bot** sebagai cadangan MausBot.
- Uji aturan persetujuan: `python -m pytest tests/test_framework4.py -q`.
