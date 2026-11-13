# POLICY ENGINE & AUTONOMY BOUNDARIES
**Dokumen Referensi: Phase 6.0 Integration Audit & Job System Architecture Blueprint**
*Kebijakan Batasan Otonomi, Pengawasan Manusia & Keamanan Siber*
*Klasifikasi Status Komponen: `PROPOSED`*
*Tanggal Rilis: 13 November 2026*

---

## 1. TINGKATAN OTONOMI AGENT (AUTONOMY TIERS)

Sistem MARU HQ menerapkan 4 tingkatan otonomi ketat (*Least Privilege*):

| Tingkat Otonomi | Deskripsi Fungsional | Tindakan yang Diizinkan | Persetujuan Manusia |
|---|---|---|---|
| **Tier 0 (Read-Only)** | Pengumpulan data & observasi pasif | Membaca watchlist, memeriksa status server, query database | Otomatis tanpa izin |
| **Tier 1 (Internal Draft)** | Penyusunan draf internal | Menulis naskah draf, merender klip pratinjau lokal, memverifikasi sitasi | Otomatis dengan batas biaya |
| **Tier 2 (External Staging)** | Penjadwalan & persiapan publikasi | Menyiapkan draf TikTok Sandbox, memuat draf ke kalender rilis | **Wajib ACC Pemilik di Gerbang Maus** |
| **Tier 3 (Public Action)** | Publikasi langsung ke publik / tindakan finansial | Mengunggah video publik, mengubah kredensial, menghapus data | **Wajib ACC Tertulis Pemilik** |

---

## 2. ATURAN SERVER-SIDE POLICY ENGINE (ENFORCEMENT RULES)

1. **Aturan Gerbang Mutlak MausBot (Approval Gate Invariant):**
   Tidak ada konten video yang dapat dikirim ke TikTok Direct Post API tanpa record keputusan `decision === "SETUJU"` yang sah dan ditandatangani oleh session pemilik di tabel `mausbot_cards`.
2. **Hard Budget Limit per Task:**
   Setiap pekerjaan dihentikan seketika (*aborted*) jika konsumsi token LLM atau estimasi biaya melampaui `budget.max_cost_idr`.
3. **Emergency Stop Button (Saklar Darurat):**
   Tersedia endpoint darurat `POST /api/hq/emergency-stop` yang seketika mengubah seluruh status worker menjadi `PAUSED` dan membatalkan seluruh task yang sedang berjalan (*kill-switch*).
4. **Secret Redaction:**
   Kredensial sensitif (`TIKTOK_CLIENT_SECRET`, session token, API key) wajib disaring (*redacted*) dari log eksekusi, log error, dan tampilan inspector UI.
5. **Prompt Injection Protection:**
   Input topik dari publik/media sosial wajib melewati sanitasi regex dan filter instruksi kontradiktif sebelum diteruskan ke Hermes.
