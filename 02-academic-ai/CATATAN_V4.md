# CATATAN V4 — Academic AI (hybrid Manager-Ollama)

Rilis: 9 Oktober 2026. Paket kode: `academic_ai_v3_hybrid_manager_ollama_v4.zip`
(pengganti `academic_ai_v3.zip` / `academic_ai_v3_hybrid_manager_ollama.zip`;
`academic_ai_data_v3.zip` (29 PDF + database) tetap dipakai seperti biasa).

## Yang berubah

1. **Tiga specialist per mata kuliah (A/B/C)** — sebelumnya dua. Setiap pertanyaan kini
   dinilai dari 3 draft independen; AI Manager tetap satu, dan jawaban tetap disetujui
   minimal 2 agent berhasil (aturan lama dipertahankan). Konfigurasi baru:
   `MODEL_PP_C` ... `MODEL_DJ_C` (7 baris baru) + `MODEL_FALLBACK_AGENT_C`.
2. **Skill pack bawaan dari GitHub** (`prompts/skills/`) — diadaptasi dari pola
   [anthropics/skills](https://github.com/anthropics/skills) (SKILL.md, spesifikasi
   [agentskills.io](https://agentskills.io)): `answer.md`, `summary.md`, `quiz.md`,
   `citation_discipline.md`. Otomatis dipakai semua agent + hint hasil belajar tetap jalan.
3. **Chunk lebih banyak + anti-mengarang** — potongan teks 1200→1000 karakter
   (overlap 200), `RAG_TOP_K` 5→8, `RAG_QUERY_VARIANTS` 3→4. Prompt agent/verifier
   kini memuat aturan tegas: klaim tanpa dukungan cuplikan ditolak; jawaban kosong
   lebih baik daripada mengarang. *Catatan: chunk baru berlaku untuk PDF yang
   diunggah setelah update ini. Untuk PDF lama, hapus & unggah ulang bila ingin
   chunking baru.*
4. **Template `.env` baru: `.env.hybrid-manager-hermes.example`** — pola hybrid yang
   dipakai saat ini (specialist ke 9Router, Manager ke Ollama). Sebelumnya dirujuk
   manual tapi filenya tidak ada.
5. **`tools/probe_models.py`** — uji SEMUA model satu per satu (chat, embedding,
   Manager + uji payload besar & output panjang) dan menulis `hasil_uji_model.md`.
6. **Pembersihan file** — `app/web/office_worker_hijab.png` (1,3 MB, tidak terpakai) dihapus.

## Wajib dijalankan setelah update (di laptop)

```cmd
cd /d C:\Users\wisnu\Downloads\academic_ai\academic_ai_v3
venv\Scripts\activate

:: 1. Samakan nama model Ollama dengan .env (sumber error 404 "model not found")
ollama list
notepad .env            :: pastikan MODEL_MANAGER persis seperti di ollama list

:: 2. Uji semua model + isi otomatis MODEL_* yang valid
python tools/probe_models.py --patch-env

:: 3. Verifikasi konfigurasi
python run.py --check --live

:: 4. Restart web
python web_run.py
```

`hasil_uji_model.md` berisi daftar lengkap model yang **OK / GAGAL** beserta latensi
dan jenis error-nya — kirimkan file itu bila masih ada yang gagal.

## Perbaikan terkait error "AI Manager gagal melakukan verifikasi"

Penyebab yang ditemukan: panggilan `POST http://localhost:11434/v1/chat/completions`
mengembalikan **HTTP 404** — `MODEL_MANAGER` di `.env` tidak cocok dengan nama model
di Ollama. Perbaikan: samakan nama persisnya (`hermes3:latest` vs `hermes3` beda!),
atau jalankan `python tools/probe_models.py --patch-env` yang otomatis memilih nama
yang benar. Bila setelah itu muncul timeout, `NINE_ROUTER_TIMEOUT=300` sudah menjadi
default template hybrid (batas aplikasi 300 detik).

## Pengujian yang sudah dijalankan sebelum rilis

- `pytest tests/` — **101 lulus** (termasuk uji independensi 3 agent, loop revisi,
  verifikasi sumber, kuis, skill, web API).
- Uji *live* terhadap 9Router/Ollama di mesin Anda harus lewat `tools/probe_models.py`
  (tidak bisa dijalankan dari lingkungan pengembangan karena endpoint-nya localhost
  milik Anda).
