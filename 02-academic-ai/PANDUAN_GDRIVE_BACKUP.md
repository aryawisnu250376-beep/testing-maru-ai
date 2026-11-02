# Panduan Backup PDF ke Google Drive per Mata Kuliah

Setiap PDF yang berhasil di-upload (lewat web **atau** bot Telegram) otomatis
dibackup ke Google Drive dengan struktur folder per mata kuliah:

```
Academic_AI/
├── PP/
│   └── Pengantar_Pancasila.pdf
├── PA/
├── BING/
└── ... (dibuat otomatis saat dibutuhkan)
```

File lokal tetap dipakai untuk RAG; Drive hanya cadangan. Backup bersifat
*best-effort*: kalau gagal (internet putus, token kedaluwarsa), upload lokal
tetap sukses dan peringatan dicatat di log. Menghapus materi (`/hapusmateri`
atau web) juga menghapus salinan Drive-nya.

## 1. Buat kredensial OAuth (sekali saja)

1. Buka https://console.cloud.google.com/ dan login dengan akun Google yang
   akan menampung backup.
2. Buat project baru (misalnya `academic-ai-backup`).
3. Aktifkan **Google Drive API**: *APIs & Services → Library → Google Drive API
   → Enable*.
4. *APIs & Services → OAuth consent screen*:
   - User type: **External**, isi nama aplikasi + email.
   - Pada langkah *Test users*, tambahkan **email kamu sendiri** (wajib selama
     aplikasi berstatus Testing).
   - Scope tidak perlu ditambah manual — aplikasi memakai `drive.file`
     (hanya boleh mengelola file yang ia buat sendiri).
5. *APIs & Services → Credentials → Create Credentials → OAuth client ID*:
   - Application type: **Desktop app**.
   - Unduh JSON-nya (tombol download).
6. Simpan file JSON itu sebagai `data/drive_credentials.json` di folder project
   (atau atur path lain via `GDRIVE_CREDENTIALS_FILE` di `.env`).

## 2. Otorisasi (sekali saja)

Di CMD folder project (venv aktif):

```cmd
python run.py --drive-auth
```

Browser terbuka → login → izinkan akses. Kalau muncul peringatan *"Google
hasn't verified this app"*, klik *Advanced → Go to … (unsafe)* — wajar untuk
aplikasi Testing milik sendiri. Token tersimpan di `data/drive_token.json`
(jangan bagikan file ini).

## 3. Nyalakan backup

Di `.env`:

```env
GDRIVE_BACKUP_ENABLED=true
GDRIVE_CREDENTIALS_FILE=data/drive_credentials.json
GDRIVE_TOKEN_FILE=data/drive_token.json
GDRIVE_ROOT_FOLDER=Academic_AI
```

Restart bot/web. Upload satu PDF percobaan, lalu cek folder `Academic_AI` di
Google Drive.

## Perilaku penting

- Upload ulang file **dengan konten identik** (sha256 sama) dilewati — tidak
  menumpuk duplikat. Upload ulang konten berbeda dengan nama sama akan
  membuat file kedua (Drive mengizinkan nama ganda).
- Setiap file backup menyimpan metadata internal (ID dokumen + sha256) untuk
  keperluan hapus dan dedup. Metadata ini tidak terlihat sebagai kolom Drive.
- Token di-refresh otomatis. Kalau refresh gagal (misal akses dicabut dari
  akun Google), jalankan ulang `python run.py --drive-auth`.
- Scope `drive.file`: aplikasi **tidak bisa melihat/mengubah** file Drive lain
  milikmu — hanya file/folder yang ia buat.

## Pemecahan masalah

| Gejala | Penyebab umum | Solusi |
|---|---|---|
| `File kredensial Google tidak ditemukan` | JSON belum disimpan | Simpan sebagai `data/drive_credentials.json` |
| `Token Drive belum ada` | Belum otorisasi | `python run.py --drive-auth` |
| `access_denied` / Error 403 di browser | Email belum jadi test user | Tambahkan email di OAuth consent → Test users |
| Backup dilewati + `[WARN]` di log | Internet/token bermasalah | Cek koneksi; otorisasi ulang bila perlu |
| Folder ganda `Academic_AI` | Root diganti namanya/diubah | Samakan `GDRIVE_ROOT_FOLDER` atau hapus folder ganda manual |
