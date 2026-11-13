# TARGET ARCHITECTURE — MARU HQ JOB SYSTEM BLUEPRINT
**Dokumen Referensi: Phase 6.0 Integration Audit & Job System Architecture Blueprint**
*Target Arsitektur: Control Plane Terpadu untuk Real Job Execution*
*Klasifikasi Status Komponen: `PROPOSED`*
*Tanggal Rilis: 13 November 2026*

---

## 1. TARGET ALUR EKSEKUSI TUGAS NYATA (TARGET PIPELINE)

```
[ USER / PEMILIK ]
       │
       ▼
[ BIMA / AI MANAGER ] (Evaluasi Visi & Pendelegasian)
       │
       ▼
[ HQ CORE / TASK PLANNER ] (Dekomposisi Tugas & Alokasi Anggaran)
       │
       ▼
[ PERSISTENT JOB QUEUE ] (SQLite WAL Mode: lease_owner, lock, priority)
       │
       ▼
[ ORCHESTRATOR & MODEL ROUTER ] (Budget Guard & Tool Allowlist)
       │
       ├───► [ ADAPTER DIVISI SOCIAL MEDIA ] (Hermes, Nara, Maus, Kirana, Ardi, Ootto)
       └───► [ ADAPTER DIVISI ACADEMIC AI ]  (Cendekia, Verifier, Knowledge Base)
       │
       ▼
[ RESULT AUDIT & VERIFICATION ]
       │
       ▼
[ BIMA (Report / ACC Request) ]
       │
       ▼
[ USER / PEMILIK ]
```

---

## 2. SPESIFIKASI SKEMA JOB LENGKAP (TASK SPECIFICATION)

Setiap pekerjaan yang masuk ke dalam `PERSISTENT JOB QUEUE` wajib memenuhi skema kanonikal berikut:

```json
{
  "task_id": "JOB-20261113-001",
  "correlation_id": "CORR-7A2F-99B1",
  "parent_task_id": null,
  "division": "SOCIAL_MEDIA",
  "requested_by": "PEMILIK_HQ",
  "goal": "Membuat konten edukasi TikTok tentang Sila ke-3 & Etika Komentar Medsos",
  "input": {
    "curriculum_dept": "DEP_01",
    "topic": "Debat kusir SARA di medsos",
    "target_duration_sec": 21,
    "creator_style": "@gegaraid"
  },
  "acceptance_criteria": [
    "Hook 3 detik pertama menyentuh emosi Gen Z",
    "Menyertakan rujukan sila ke-3 Pancasila dan adab digital",
    "Lolos review etika MausBot tanpa pelanggaran hak cipta",
    "Durasi video vertikal 9:16 tepat 18-22 detik",
    "Audio dubbing muda ekspresif dengan intonasi jelas"
  ],
  "priority": 1,
  "status": "QUEUED",
  "assigned_agent": "EMP-L02",
  "dependencies": [],
  "budget": {
    "max_cost_idr": 15000,
    "max_tokens": 8000,
    "max_duration_sec": 300
  },
  "attempts": 0,
  "max_attempts": 3,
  "lease_owner": null,
  "lease_expires_at": null,
  "created_at": "2026-11-13T02:15:00+07:00",
  "updated_at": "2026-11-13T02:15:00+07:00",
  "result": null,
  "error": null
}
```

---

## 3. STATE MACHINE SIKLUS HIDUP PEKERJAAN (JOB LIFECYCLE)

```
[ PENDING / QUEUED ]
        │
        ├─► (Acquire Lease) ──► [ LEASED / RUNNING ]
        │                              │
        │                              ├─► (Success) ──► [ AWAITING_APPROVAL ]
        │                              │                        │
        │                              │                        ├─► (Owner ACC) ──► [ COMPLETED ]
        │                              │                        └─► (Owner Rev) ──► [ REVISION ] ──┐
        │                              │                                                           │
        │                              └─► (Error / Timeout) ──► [ FAILED / RETRYING ]             │
        │                                                               │                          │
        │                                                               ├─► (Attempts < Max) ──────┘
        │                                                               └─► (Attempts >= Max) ─────► [ DEAD_LETTER ]
        └─► (User Cancel) ──► [ CANCELLED ]
```

---

## 4. KEAMANAN & PRINSIP TATA KELOLA (GOVERNANCE)
1. **Server-Side Policy Engine:** Tidak ada keputusan approval atau publikasi yang dipercayakan kepada logika browser/frontend.
2. **Lease & Heartbeat Lock:** Worker yang mengambil pekerjaan wajib memperbarui lease setiap 30 detik. Jika worker mati, job otomatis dikembalikan ke antrean (*stale job recovery*).
3. **Idempotency Key:** Setiap job memiliki hash unik dari `input` untuk mencegah duplikasi eksekusi jika terjadi double-click atau network retry.
