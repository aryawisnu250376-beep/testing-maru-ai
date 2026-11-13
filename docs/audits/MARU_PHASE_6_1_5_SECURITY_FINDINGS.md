# MARU HQ — PHASE 6.1.5 SECURITY FINDINGS & CLOSURE
**Branch:** `fix/phase-6-1-5-comprehensive-audit-remediation`  

### Temuan 1: Kerentanan Identity Claim String pada Memori
- **Deskripsi:** Caller sebelumnya dapat mengklaim identitas agen dengan menyertakan string `caller_id`.
- **Mitigasi:** `InternalAuthAuthority` mewajibkan token bertanda tangan server (`psec_...`). Permintaan tanpa token otomatis turun (fail closed) menjadi Anonymous yang hanya memiliki hak baca pada `ORGANIZATIONAL`.
- **Status:** **TERTUTUP & TERUJI (PASS)**.

### Temuan 2: Thread-Only Fallback pada Worker Timeout
- **Deskripsi:** Timeout worker dengan thread daemon berisiko meninggalkan orphan threads yang masih menulis ke DB setelah timeout.
- **Mitigasi:** Eksekusi otomatis dialihkan ke isolasi proses nyata sistem operasi (`multiprocessing.Process`) dengan sinyal terminasi paksa `SIGTERM` lalu `SIGKILL`.
- **Status:** **TERTUTUP & TERUJI (PASS)**.

### Temuan 3: Klaim Verifikasi Palsu pada Fallback Router
- **Deskripsi:** Fallback deterministik offline sebelumnya menghasilkan label status `VERIFIED` dan skor keyakinan `0.95`.
- **Mitigasi:** Status fallback diubah menjadi `UNVERIFIED_DRAFT`, skor diturunkan menjadi `0.60`, dan mewajibkan review manusia (`requires_human_review: True`).
- **Status:** **TERTUTUP & TERUJI (PASS)**.
