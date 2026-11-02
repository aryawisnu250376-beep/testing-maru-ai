# ANALISIS & ROADMAP — AI Edukasi Agent

Dokumen ini jujur soal **apa yang sudah jalan, apa yang belum, dan apa yang
harus dikerjakan lebih dulu**. Semua angka di sini hasil pengukuran di mesin
build (2 vCPU, tanpa GPU), bukan perkiraan.

Tanggal: 1 November 2026 · versi kode: 2.0.0 · 69 test lulus · lint bersih

---

## 0. Ringkasan satu layar

| Aspek | Status | Catatan |
|---|---|---|
| Pipeline riset → skrip → ACC → render → paket upload | ✅ jalan end-to-end | 4 episode sudah diproduksi tanpa disentuh manusia |
| Automasi tanpa trigger (studio 8 agent) | ✅ jalan | dibuktikan lewat klik ACC di browser → video jadi sendiri |
| Gerbang ACC | ✅ kuat | diuji: render **tidak bisa** jalan tanpa `decision.json` |
| Kualitas naskah | ⚠️ lemah | masih penulis template; LLM belum pernah hidup |
| Kualitas visual | ⚠️ sedang | motion-graphics 2D; belum bergaya cerita seperti referensi |
| Upload ke TikTok | ❌ belum | butuh audit TikTok (2–4 minggu, sering ditolak) |
| Umpan balik performa | ⚠️ ada tapi kosong | tabelnya siap, datanya belum pernah masuk |
| Biaya | ✅ $0 | semua komponen gratis, terbukti jalan |

---

## 1. Kekurangan yang nyata (bukan teori)

### 1.1 Naskah masih generik
`scriptwriter.write_with_template()` yang dipakai setiap kali LLM tidak ada.
Hasilnya rapi tapi datar: hook berpola sama, analogi itu-itu saja. Ini
jaring pengaman, bukan pengganti LLM. **Dampak: retensi rendah.**

Bukti: 4 episode terakhir semuanya membuka dengan "Minggu ini di AI." / "Ada
satu hal di dunia AI yang minggu ini muncul terus."

### 1.2 Nol model LLM pernah terbukti hidup
Seluruh 71 kandidat di `src/providers.py` berstatus `unreachable` karena
9Router tidak jalan di mesin build. Artinya jalur "agent pintar" belum pernah
diuji dengan model sungguhan — baru jalur "agent mekanis".

### 1.3 Trend radar tidak melihat TikTok
Tidak ada API tren TikTok publik. Yang dipakai: HN, HuggingFace, GitHub,
Google Trends ID, dan watchlist yang kamu isi manual. Jadi "kesadaran trend"
kita bagus untuk dunia AI global, **buta untuk apa yang sedang viral di TikTok
Indonesia**. Ini gap paling mahal untuk niche kita.

### 1.4 Visual belum bergaya "cerita"
Dua referensi yang kamu kirim menunjukkan pola yang berbeda dari yang kita punya:

| | Referensi 1 (@caritahuyukk17) | Referensi 2 (video "jam kerja") | Pipeline kita sekarang |
|---|---|---|---|
| Gaya | 3D clay/toy, karakter | 2D flat kartun, karakter + diagram | motion-graphics abstrak |
| Durasi | 78 detik | 64 detik | 36–40 detik |
| Struktur | cerita orang (Nabila, Pak Darto) | cerita + data (grafik, jam, termometer) | penjelasan konsep |
| Badge seri | logo kecil kiri atas | "jam kerja" kiri atas | "AI DALAM 60 DETIK" |
| Caption | kotak putih, teks pendek | kotak putih, teks pendek | ASS per 3 kata (lebih ramai) |

Yang kita punya sekarang **tidak menyerupai keduanya**. Ini keputusan yang
harus dibuat sebelum menambah fitur lain.

**Catatan penting soal 3D:** sudah diukur, render 3D clay di CPU:
720×1280 @16 spp = **59 detik/frame**. Video 40 detik @24 fps = 960 frame =
**15 jam**. Itu bukan pipeline $0. Kalau mau gaya referensi 1, harus pakai
trik "still + gerak kamera" (8 adegan ≈ 8 menit) — tapi geraknya kaku.
Gaya referensi 2 (2D flat) jauh lebih murah dan bisa dikejar dengan stack kita.

### 1.5 Upload & distribusi belum ada
`publish.mode` default `manual`. API TikTok memaksa konten dari klien
unaudited jadi `SELF_ONLY`, dan audit butuh 2–4 minggu dengan risiko ditolak.
Jadi untuk sekarang: **paket siap-upload**, bukan upload otomatis.

### 1.6 Dubbing satu suara, satu gaya
Hanya `edge-tts` dengan 2 pilihan suara (`id-ID-ArdiNeural`, `id-ID-GadisNeural`).
Belum ada variasi tempo/emosi per beat, belum ada jeda dramatis yang disengaja,
belum bisa meniru suara sendiri.

### 1.7 Studio butuh proses hidup
`python -m src.dashboard` harus jalan. Kalau laptop tidur, agent berhenti.
`scripts/autostart.sh` membantu (launchd/systemd user), tapi tetap mati saat
laptop benar-benar sleep.

### 1.8 Belum ada autentikasi dashboard
Siapa pun yang bisa menjangkau port 8080 bisa menekan **Setujui**. Untuk
localhost aman; begitu diekspos ke jaringan/tunnel, ini lubang serius.

### 1.9 Ketergantungan lingkungan tidak dijaga
Sudah kejadian dua kali di sesi ini: `pip install` hilang setelah environment
reset → ffmpeg dan edge-tts lenyap → render diam-diam jatuh ke mode hening
tanpa error. Sudah ditambal dengan `python -m src.cli doctor`, tapi belum ada
yang memaksa menjalankannya sebelum studio start.

### 1.10 Learning loop belum bersuara
`learning.report()` jalan, tapi datanya kosong karena belum ada metrik yang
pernah dimasukkan. Jadi agent "belajar dari nol" setiap kali.

---

## 2. Yang bisa diperbaiki (dengan perkiraan usaha)

| # | Perbaikan | Dampak | Usaha |
|---|---|---|---|
| 1 | Hidupkan 9Router → LLM asli untuk naskah | ★★★★★ | 1 jam (di sisi kamu) |
| 2 | Restrukturisasi naskah: konsep → **cerita** (tokoh, konflik, akhir) | ★★★★★ | 2–3 hari |
| 3 | Gaya visual 2D flat + karakter (arah referensi 2) | ★★★★★ | 4–6 hari |
| 4 | Caption gaya kotak putih (bukan per-kata) | ★★★ | 2 jam |
| 5 | Variasi suara: tempo & jeda per beat | ★★★ | 1 hari |
| 6 | Metrik masuk otomatis (entry manual di dashboard dulu) | ★★★★ | 1 hari |
| 7 | Autentikasi + token akses untuk dashboard | ★★★ | 4 jam |
| 8 | `doctor` dipanggil otomatis sebelum studio start | ★★ | 1 jam |
| 9 | Retry/backoff saat render gagal berulang | ★★ | 4 jam |
| 10 | Migrasi DB berversi (sekarang `CREATE TABLE IF NOT EXISTS` saja) | ★★ | 3 jam |

---

## 3. Urutan pengerjaan yang disarankan

Aturan penentuan prioritas yang dipakai di sini: **kerjakan yang mengubah
kualitas hasil per video lebih dulu**, baru yang menghemat waktu kita.

### P0 — sebelum menambah fitur apa pun (1–2 hari)
1. **Hidupkan LLM.** Tanpa ini semua perbaikan lain cuma memperindah naskah
   yang datar. Jalankan 9Router, `python -m src.cli providers`, pilih model
   hidup, tulis ke config.
2. **Ubah bentuk naskah dari "konsep" ke "cerita".** Skema beat berubah:
   `tokoh → masalah → percobaan → titik balik → pelajaran`. Ini yang membuat
   referensi 1 dan 2 bekerja.
3. **Caption kotak putih** (gaya referensi), bukan highlight per kata.

### P1 — kualitas visual (1–2 minggu)
4. **Renderer karakter 2D.** Flat vector + wajah ekspresif; satu karakter
   tetap per seri supaya orang mengenali. Semua bisa dengan Pillow/SVG, sudah
   terbukti murah (frame 2D kita ~30 ms vs 3D 59 detik).
5. **Pustaka diagram** (grafik batang, jam, termometer, tabel) seperti
   referensi 2 — ini yang membuat video "terasa berisi".
6. **Badge seri + intro 1 detik** yang konsisten.

### P2 — distribusi & umpan balik (setelah 5–7 video tayang)
7. **Input metrik** dari dashboard → learning loop mulai bersuara.
8. **Uji A/B hook**: dua variasi hook, pilih yang retensi 3 detiknya lebih baik.
9. **Ajukan audit TikTok** untuk upload langsung (sambil tetap manual).

### P3 — ketahanan
10. Autentikasi dashboard, backoff render, migrasi DB, CI yang benar-benar jalan.

---

## 4. Kerangka berpikir agent ini

Inti desainnya: **agent boleh memutuskan apa yang dikerjakan, tidak boleh
memutuskan menggantikan manusia.**

```
                 ┌──────────────────────────────────────────┐
                 │           MEMORI (SQLite)                │
                 │  tren · episode · task · revisi · metrik │
                 └──────────────────────────────────────────┘
                     ▲                        ▲
        baca kondisi │                        │ tulis jejak
                     │                        │
   ┌─────────────────┴────────────────────────┴──────────────────┐
   │                        PUTARAN KERJA                        │
   │                                                             │
   │  1. AMATI      apa yang berubah? (DB, umur laporan, antrean)│
   │  2. NILAI      apa yang paling mendesak? (aturan di bawah)  │
   │  3. KERJAKAN   satu unit kerja saja                         │
   │  4. CATAT      task + progres → dashboard jujur             │
   │  5. VERIFIKASI apakah hasilnya memenuhi syarat?             │
   └─────────────────────────────────────────────────────────────┘
```

### 4.1 Urutan keputusan (dari `orchestrator.step`)

```
ada episode di-ACC?          → kerjakan (ACC kamu = prioritas tertinggi)
antrean ACC penuh (≥2)?      → jangan menumpuk; belajar saja
jeda antar-episode belum?    → diam (idle jujur, bukan sibuk palsu)
selain itu                   → riset → ide → tulis → taruh di ACC
```

Empat aturan itu sengaja bodoh dan kaku. Agent yang "kreatif" soal urutan kerja
adalah agent yang sulit diprediksi dan sulit dimaafkan saat salah.

### 4.2 Aturan yang tidak boleh dilanggar (hard rules)

| Aturan | Kenapa | Diuji oleh |
|---|---|---|
| Render **wajib** ada `decision.json: approve` | manusia tetap pemegang keputusan | `test_otonomi_tidak_pernah_render_tanpa_acc` |
| Publish publik tidak pernah otomatis | ToS TikTok + risiko akun | default `auto_publish: false` |
| Naskah tanpa sumber → ditolak | anti-hoaks | `scriptwriter.require_sources` |
| Wajib sebut batasan | kejujuran editorial | `must_include_limitation` |
| Tiru struktur, bukan aset | hak cipta | `trends_tiktok.compliance` |
| Satu langkah = satu task tercatat | dashboard tidak boleh mengarang | `agents.snapshot()` |

### 4.3 Lapisan memori

| Lapisan | Isi | Dipakai untuk |
|---|---|---|
| **Episodik** | `events`, `agent_tasks`, `revisions` | apa yang terjadi, kapan, oleh agent mana |
| **Semantik** | `learning.report()` → pola pemenang | "hook pertanyaan lebih baik dari angka" |
| **Prosedural** | `config/persona.yaml`, `config.yaml` | aturan main yang bisa kamu ubah tanpa kode |

Tanpa lapisan ketiga, agent tidak bisa dikoreksi tanpa menyentuh kode. Itu
sebabnya semua ambang (jumlah pending, jeda episode, level musik) ada di config.

### 4.4 Prinsip verifikasi

Setiap klaim di README punya cara membuktikannya (lihat tabel "Bukti, bukan
janji"). Kalau sebuah fitur tidak punya test atau artefak yang bisa diperiksa,
fitur itu **dianggap belum ada** — apa pun yang tertulis di dokumentasi.

---

## 5. Jawaban atas pertanyaanmu

### 5.1 Kalau saya upload suara, bisa dipakai untuk dubbing?

**Bisa, dua tingkat:**

**Tingkat 1 — suara kamu apa adanya (bisa hari ini, tanpa ML).**
Kamu rekam bacaan skrip, kirim filenya, pipeline memakai rekaman itu sebagai
narasi dan `edge-tts` tidak dipanggil. Caption tetap jalan lewat whisper
(`faster-whisper`, gratis, CPU) untuk dapat timestamp per kata. Tidak ada
training, tidak ada risiko. **Ini yang saya sarankan untuk 10 video pertama** —
suara asli manusia selalu lebih dipercaya daripada TTS.

**Tingkat 2 — kloning suara (butuh model lokal, masih $0 tapi berat).**
Pilihan lisensi permisif: **F5-TTS** (MIT) dan **Chatterbox** (MIT). Keduanya
bisa jalan di CPU; 10–30 detik sampel sudah cukup untuk kloning kasar. Biaya
nyata: ~1–3× durasi audio untuk sintesis di CPU, plus download model 1–2 GB.
Yang **harus** dihindari: kloning suara orang lain tanpa izin tertulis, dan
model dengan lisensi non-komersial (XTTS-v2) kalau nanti monetisasi.

Kalau kamu kirim sampel suara, saya bisa: (a) uji berapa detik yang benar-benar
dibutuhkan untuk hasil layak, (b) ukur kecepatan sintesis di mesin ini, (c)
bandingkan F5-TTS vs Chatterbox pada teks Indonesia.

### 5.2 Kalau 9Router di laptop dinyalakan, bisa dicoba model-modelnya?

**Ada satu syarat teknis yang harus jelas dulu:** sandbox tempat saya bekerja
**bukan laptop kamu**. `localhost:20128` di sini menunjuk ke mesin kosong.
Jadi jawabannya: **belum, kecuali 9Router-nya bisa dijangkau dari internet.**

Tiga jalan, dari paling mudah:

| Cara | Yang kamu lakukan | Yang saya lakukan |
|---|---|---|
| **A. Kamu jalankan sendiri** | `python -m src.cli providers` → tempel JSON-nya ke sini | saya analisis: mana hidup, mana `quota`, mana `unauthorized`, dan susun `PREFERRED_STRONG/CHEAP` |
| **B. Tunnel publik** | `cloudflared tunnel --url http://localhost:20128` (gratis, tanpa akun) lalu kirim URL + API key | saya probe semua 71 model dari sini dan buat tabel hasil lengkap |
| **C. Rekam dashboard** | screenshot tab "Cek model" | saya baca hasil apa adanya |

Cara B paling cepat (5 menit) dan memberi hasil paling lengkap — tapi ingat:
URL tunnel itu **pintu terbuka ke router kamu**, jadi matikan setelah selesai.

Catatan ToS yang sudah saya temukan sebelumnya: jalur routing 9Router yang
memakai **OAuth sesi akun consumer** (Claude Code, Copilot, Cursor) melanggar
ToS untuk pemakaian 24/7/komersial. Pakai jalur **API key** saja.

### 5.3 Gap apa yang bisa dikerjakan AI lain?

Ringkas; detailnya di bagian 1–3:

1. **Naskah naratif** — ubah skema beat jadi cerita 5 babak. Murni kerja
   `scriptwriter.py` + prompt. Tidak menyentuh render.
2. **Renderer karakter 2D** — file baru `src/characters2d.py`, ikut antarmuka
   `RENDERERS` yang sudah ada. Bisa dikerjakan paralel tanpa konflik.
3. **Pustaka diagram** (grafik, jam, termometer) — satu fungsi per diagram di
   `visuals.py`.
4. **Kloning suara** — modul baru `src/voice.py`, antarmuka: `synth(text) -> wav`.
5. **Autentikasi dashboard** — `dashboard.py` + satu token di config.
6. **Backoff & pemulihan render** — `queue.py` + `orchestrator.py`.
7. **Migrasi DB berversi** — `db.py`, tabel `schema_version`.
8. **Analitik metrik** — `learning.py` sudah siap; butuh jalur input data.

Yang **tidak boleh** dikerjakan paralel: `orchestrator.py` dan `studio_html.py`
(dua file ini saling terikat erat; perubahan bersamaan gampang bentrok).

---

## 6. Definisi "selesai" untuk versi berikutnya

- [ ] 7 video berturut-turut tanpa intervensi selain ACC
- [ ] ≤24 jam dari sinyal tren → siap publish
- [ ] ≤5 menit kerja manusia per video
- [ ] Naskah dari LLM asli, bukan template
- [ ] Visual bergaya seri (karakter tetap + badge), bukan motion-graphics generik
- [ ] Minimal satu video punya data metrik yang masuk ke learning loop
