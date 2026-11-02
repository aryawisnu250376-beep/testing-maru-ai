---
name: maru-hq-governance
description: Aturan tata kelola inti MARU HQ (Hybrid Autonomous AI Corporation): level otonomi L1/L2/L3, gerbang persetujuan manusia, kontrak task lintas divisi, batas budget/retry, serta larangan keras kebocoran kredensial.
---
# Skill: MARU HQ Governance & Autonomy Policy

Berlaku lintas seluruh divisi **MARU AI** (**HQ Control Plane**, **Social Media Corporation**, dan **Academic AI**).

## 1. Tiga Level Otonomi Wajib

| Level | Cakupan Aktivitas | Aturan Eksekusi |
|---|---|---|
| **L1 — Autonomous** | Riset tren, klasifikasi, draft naskah, ringkasan kuliah, kuis, evaluasi QC internal. | Boleh berjalan otomatis selama di dalam batas *scope* dan *budget*. |
| **L2 — Controlled** | Mengubah file kerja proyek, render video lokal, memperbarui kalender draft, sinkronisasi skill/memori terstruktur. | Boleh otomatis dengan *backup*, pencatatan audit log, idempotensi, dan strategi *rollback*. |
| **L3 — Restricted** | Publikasi langsung ke TikTok/IG/YouTube (`mode=direct`), kirim pesan eksternal massal, transaksi/biaya berbayar, hapus data permanen. | **WAJIB persetujuan manusia eksplisit (`ACC`)** sebelum dieksekusi. Dilarang dilewati oleh agent mana pun. |

## 2. Isolasi Antar-Divisi & Memori

- HQ berkomunikasi dengan Social Media dan Academic AI **hanya melalui kontrak adapter/API tervalidasi** (dengan `task_id`, `correlation_id`, dan `idempotency_key`).
- Jangan mencampur dokumen/memori akademik pribadi pengguna ke basis pengetahuan publik Social Media tanpa izin eksplisit.

## 3. Keamanan Kredensial Mutlak

- Dilarang menaruh nilai `.env`, API key, token Telegram/TikTok/GitHub, atau password di kode sumber, log, screenshot, maupun commit GitHub.
