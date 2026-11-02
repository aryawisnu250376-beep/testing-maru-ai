# Panduan n8n untuk Academic AI

n8n berperan sebagai **orkestrasi di sekeliling** Academic AI: jadwal kuis,
auto-upload materi, dan digest harian. Semua workflow memanggil API lokal
(`http://127.0.0.1:8765`) — tidak perlu mengubah kode Academic AI.

Prasyarat: `python web_run.py` harus berjalan (workflow menembak API-nya).

## 1. Instal n8n (PC Windows yang sama — disarankan)

Node.js sudah terinstal (syarat 9Router), jadi cara termudah:

```cmd
npm install -g n8n
n8n start
```

Buka http://localhost:5678, buat akun admin lokal, dan biarkan CMD n8n tetap
berjalan. (Alternatif: Docker `docker run -p 5678:5678 n8nio/n8n`, atau n8n
Cloud — lihat catatan LAN di bawah.)

Agar n8n nyala otomatis saat laptop menyala, buat scheduled task Windows yang
menjalankan `n8n start` ketika logon.

## 2. Import workflow

Di n8n: *⋯ menu → Import from File*, pilih satu per satu dari folder `n8n/`:

| File | Fungsi |
|---|---|
| `kuis_harian.json` | Tiap jam 07.00 minta `/api/quiz` lalu kirim ke Telegram |
| `auto_ingest_folder.json` | PDF baru di `C:\academic_ai\inbox` otomatis di-upload ke API |
| `digest_harian.json` | Tiap jam 21.00 kirim ringkasan `/api/stats` ke Telegram |
| `academic_webhook.json` | Webhook `POST /academic-ask` → `/api/chat` → respons JSON (contoh integrasi generik) |

## 3. Isi 3 hal wajib di tiap workflow

1. **Token API** — di node HTTP, ganti `GANTI_DENGAN_LOCAL_API_TOKEN` dengan
   isi `LOCAL_API_TOKEN` dari `.env` Academic AI (format: `Bearer <token>`).
   Tips rapi: simpan sebagai environment variable n8n lalu pakai
   `Bearer {{ $env.ACADEMIC_API_TOKEN }}`.
2. **Kredensial Telegram** — di node Telegram, *Create New Credential* dan isi
   *Access Token* bot dari `@BotFather`. **Boleh memakai token bot yang sama**
   dengan Academic AI: node ini hanya *mengirim* pesan, tidak bentrok dengan
   polling bot. Yang dilarang: memasang **Telegram Trigger** dengan token yang
   sama (rebutan update dengan `run.py`).
3. **Chat ID** — ganti `GANTI_DENGAN_CHAT_ID` dengan ID numerik Telegram kamu
   (chat bot `@userinfobot`, atau kirim pesan ke bot lalu buka
   `https://api.telegram.org/bot<TOKEN>/getUpdates`).

Lalu klik **Test workflow** (atau *Execute step* per node), dan jika beres,
aktifkan toggle **Active** agar jadwal berjalan otomatis.

## 4. Kustomisasi cepat

- **Ganti mata kuliah kuis**: edit `subject_code` di node *Minta Kuis*
  (`PP` → `PA`, dst). Duplikat workflow untuk beberapa matkul.
- **Ganti jam**: edit cron di node Schedule (`0 7 * * *` = jam 07.00).
- **Inbox per matkul**: buat subfolder `C:\academic_ai\inbox\PP`,
  `...\PA`, dst. Node *Tentukan Matkul* membaca nama folder induk sebagai
  kode matkul (tidak dikenal → default `PP`).
- **n8n di mesin lain**: ubah `WEB_ACCESS_MODE=lan` di `.env` Academic AI,
  ganti URL workflow ke `http://<IP-LAPTOP>:8765`, dan pastikan satu jaringan
  private. Jangan ekspos API ke internet.

## 5. Ide lanjutan (loop "mengasah kemampuan")

- Tambahkan node **Google Sheets** setelah digest untuk mencatat
  `recent_verifications` tiap hari → bahan evaluasi kualitas jawaban.
- Tambahkan node **IF** pada `status == UNVERIFIED` → teruskan ke grup
  diskusi/reviewer manusia alih-alih ke siswa.
- Webhook n8n sebagai frontend WhatsApp/Discord yang meneruskan pertanyaan ke
  `POST /api/chat`.

## Pemecahan masalah

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| HTTP 401 | Token salah | Samakan dengan `LOCAL_API_TOKEN` di `.env` |
| HTTP 422 (quiz/chat) | Config/model bermasalah | Baca `detail` respons — itu pesan aksi yang harus diperbaiki |
| `ECONNREFUSED 127.0.0.1:8765` | `web_run.py` mati | Nyalakan web/API dulu |
| HTTP timeout (kuis/upload) | Model lokal lambat | Wajar di CPU; timeout workflow sudah 5 menit |
| Telegram 400 `chat not found` | Chat ID salah / belum `/start` | Chat bot dulu, cek ID numerik |
| File Trigger tidak bereaksi | Path salah / n8n tanpa akses | Samakan path di node; jalankan n8n sebagai user biasa |
