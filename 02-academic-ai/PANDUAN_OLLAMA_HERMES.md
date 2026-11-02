# Hermes via Ollama + 9Router

Aplikasi ini mendukung dua endpoint chat sekaligus: **Agent A/B dapat memakai 9Router**, sementara **AI Manager/verifier dapat memakai Hermes lokal di Ollama**. Pengaturan khusus Manager memakai `MANAGER_CHAT_BASE_URL` dan `MANAGER_CHAT_API_KEY`; jangan arahkan `CHAT_BASE_URL` global ke Ollama jika Agent A/B harus tetap memakai 9Router.

## 1. Siapkan Ollama dan Hermes

1. Unduh dan instal Ollama dari https://ollama.com/download (atau `winget install Ollama.Ollama`).
2. Di CMD jalankan:

   ```cmd
   ollama pull hermes3
   ollama list
   curl http://localhost:11434/v1/models
   ```

   Catat **NAME persis** dari `ollama list` / `/v1/models`. Jika katalog menampilkan `hermes3:latest`, gunakan persis nilai itu sebagai `MODEL_MANAGER`. Bila curl gagal, pastikan Ollama berjalan atau jalankan `ollama serve` di CMD terpisah.

Model lokal membutuhkan ruang RAM/VRAM. Hermes sekitar 8B biasanya lebih layak dicoba di komputer pribadi; model besar dapat sangat lambat atau tidak muat di memori.

## 2. Mode yang disarankan: Agent A/B via 9Router, Manager via Hermes

Dari folder project di Command Prompt:

```cmd
copy .env.hybrid-manager-hermes.example .env
notepad .env
```

Isi nilai rahasia dan sesuaikan model dengan katalog live-mu. Bagian routing utama:

```env
# Spesialis A/B tetap ke 9Router
CHAT_BASE_URL=
CHAT_API_KEY=

# Hanya AI Manager/verifier ke Ollama
MANAGER_CHAT_BASE_URL=http://localhost:11434/v1
MANAGER_CHAT_API_KEY=ollama
MODEL_MANAGER=hermes3:latest
```

Biarkan `CHAT_BASE_URL` kosong agar aplikasi memakai `NINE_ROUTER_BASE_URL` untuk semua Agent A/B. Isi `NINE_ROUTER_API_KEY` seperti biasa. `MANAGER_CHAT_*` mengalihkan hanya panggilan Manager/verifier dan rangkuman caption YouTube. Embedding dan STT juga tetap memakai 9Router bila `EMBEDDING_*` dan `STT_*` dibiarkan kosong.

`MODEL_FALLBACK_MANAGER`, jika dipakai, harus berupa model yang tersedia di **Ollama**. Fallback Manager tidak otomatis pindah ke 9Router; biarkan kosong bila belum menyiapkan model lokal kedua.

Template hybrid menyediakan pembagian model dari konfigurasi yang diminta: A memakai Haiku; B memakai GLM-5, DeepSeek, atau Qwen sesuai endpoint. MiniMax yang tidak muncul pada katalog live diganti dengan `kr/glm-5`. Gunakan ID persis yang tersedia pada katalog 9Router milikmu.

## 3. Mode lama: semua chat lokal

Jika memang ingin semua 14 spesialis dan Manager memakai Ollama, gunakan template terpisah:

```cmd
copy .env.ollama-hermes.example .env
```

Dalam mode ini `CHAT_BASE_URL=http://localhost:11434/v1`, jadi model-model spesialis juga harus terpasang di Ollama. Jangan gunakan mode ini untuk konfigurasi hybrid yang menempatkan Agent A/B di 9Router.

## 4. Periksa routing dan ID model

Nyalakan 9Router dan Ollama, lalu jalankan:

```cmd
python run.py --check
python run.py --check --live
```

Pemeriksaan live membaca katalog; tidak mengirim prompt/completion ke model. Pada mode hybrid hasilnya seharusnya menampilkan dua chat catalog terpisah:

- **Katalog chat spesialis**: `http://localhost:20128/v1` (9Router)
- **Katalog chat Manager**: `http://localhost:11434/v1` (Ollama)

Semua ID `MODEL_*_A` dan `MODEL_*_B` harus berstatus `OK` di katalog spesialis; `MODEL_MANAGER` harus berstatus `OK` di katalog Manager. Jika ada `TIDAK ADA`, salin ID persis dari katalog endpoint yang sesuai. `MODEL_EMBEDDING` harus ada di katalog embedding 9Router; `MODEL_STT` hanya diisi bila memakai voice note dan ID-nya harus ada di katalog STT.

## 5. Jalankan aplikasi

```cmd
python run.py
```

Untuk website buka CMD lain dan jalankan:

```cmd
python web_run.py
```

Pastikan CMD Ollama dan 9Router tetap berjalan selama aplikasi dipakai.

## Catatan

- Hermes adalah model chat, **bukan model embedding atau STT**. Jangan isi `MODEL_EMBEDDING` atau `MODEL_STT` dengan `hermes3` kecuali server Ollama dan model yang dipasang memang menyediakan endpoint yang sesuai.
- `NINE_ROUTER_TIMEOUT` dipakai sebagai timeout umum; model lokal bisa butuh waktu lebih lama saat pertama kali dimuat.
- Pada CPU saja, Manager lokal dapat terasa lambat. Kurangi `MAX_OUTPUT_TOKENS` atau `MAX_REVISION_ROUNDS` bila perlu.
- `MANAGER_CHAT_API_KEY=ollama` adalah nilai placeholder untuk API OpenAI-compatible Ollama; bukan rahasia 9Router.

## Pemecahan masalah

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| Manager `TIDAK ADA` | ID tidak sama dengan katalog Ollama atau endpoint khusus Manager belum aktif | Cek `ollama list`, `MANAGER_CHAT_BASE_URL`, dan `MODEL_MANAGER` |
| Agent A/B `TIDAK ADA` | ID tidak tersedia/berizin pada 9Router atau `CHAT_BASE_URL` diarahkan ke Ollama | Kosongkan `CHAT_BASE_URL` agar fallback ke 9Router; cek `/v1/models` di port 20128 |
| `Connection refused localhost:11434` | Ollama belum berjalan | Jalankan Ollama/`ollama serve`; cek `/v1/models` |
| `MODEL_EMBEDDING` error | Mengisi model chat, atau ID embedding tidak tersedia | Pilih ID persis dari katalog embedding 9Router |
| Voice note 503/502 | STT tidak terkonfigurasi atau diarahkan ke Ollama | Kosongkan `STT_BASE_URL` agar memakai 9Router dan isi ID katalog STT |
