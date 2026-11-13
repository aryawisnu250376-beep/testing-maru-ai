# PHASE 6.1 ROLLBACK PLAN & INVARIANT VERIFICATION
**MARU HQ — Multi-Agent Integration & Real Job Execution Control Plane**
*Prosedur Pengembalian Sistem & Verifikasi Ketidakrusakan*
*Tanggal Rilis: 13 November 2026*

---

## 1. HASH FILE SEBELUM & SESUDAH
Untuk membuktikan bahwa Phase 6.1 tidak mengubah file legacy apapun:

| Nama File | SHA256 Sebelum Phase 6.1 | SHA256 Sesudah Phase 6.1 | Status Integritas |
|---|---|---|---|
| `studio_bulletproof.html` | `080fa41d9564cc94d6dcf64fb51f48d958d52944549f4d7afd44b89a27335c0d` | `080fa41d9564cc94d6dcf64fb51f48d958d52944549f4d7afd44b89a27335c0d` | **100% IDENTIK & TIDAK BERUBAH** |

---

## 2. PROSEDUR ROLLBACK INSTAN (10 DETIK)
Jika pemilik HQ memutuskan untuk membatalkan seluruh perubahan Phase 6.1, jalankan perintah berikut:

### Di Lingkungan Linux / Sandbox:
```bash
rm -rf src/hq data/hq_core.db test_phase6_1_acceptance.py docs/PHASE_6_1_*.md
```

### Di Lingkungan Windows CMD:
```cmd
rmdir /S /Q src\hq
del data\hq_core.db
del test_phase6_1_acceptance.py
del docs\PHASE_6_1_*.md
```

### Dampak Rollback:
- Sistem MARU HQ seketika kembali persis ke kondisi akhir Phase 5B.
- Dashboard web `studio_bulletproof.html`, kanvas 3D Three.js, autentikasi sesi, dan data media sosial eksisting tetap berfungsi normal tanpa cacat.
