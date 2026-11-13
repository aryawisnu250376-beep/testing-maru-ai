# INTEGRATION CONTRACT — MARU HQ INTERNAL INTERFACES
**Dokumen Referensi: Phase 6.0 Integration Audit & Job System Architecture Blueprint**
*Spesifikasi Protokol Komunikasi & Payload API Terpadu*
*Klasifikasi Status Komponen: `PROPOSED`*
*Tanggal Rilis: 13 November 2026*

---

## 1. ENDPOINT KONTRAK HQ CORE (INTERNAL REST/JSON)

### A. Endpoint Pembuatan Tugas (`POST /api/hq/tasks`)
* **Akses:** Diotentikasi via Bearer Token (Pemilik HQ / Bima).
* **Request Payload:**
```json
{
  "division": "SOCIAL_MEDIA",
  "goal": "Penyusunan naskah video TikTok tentang Teori Spiral of Silence",
  "input": {
    "topic": "Takut beda pendapat di kolom komentar",
    "curriculum_dept": "DEP_05",
    "style_preset": "@gegaraid"
  },
  "acceptance_criteria": [
    "Hook 3 detik pertama memicu rasa penasaran",
    "Menyertakan analogi sederhana teori Spiral of Silence",
    "Call to action mengajak diskusi sehat"
  ],
  "priority": 2,
  "budget_idr": 10000
}
```
* **Response Payload (HTTP 201 Created):**
```json
{
  "ok": true,
  "task_id": "JOB-20261113-002",
  "correlation_id": "CORR-8812-B9A1",
  "status": "QUEUED",
  "assigned_agent": "EMP-L02",
  "created_at": "2026-11-13T02:20:00+07:00"
}
```

---

### B. Endpoint Status Tugas & Polling (`GET /api/hq/tasks/{task_id}`)
* **Response Payload (HTTP 200 OK):**
```json
{
  "task_id": "JOB-20261113-002",
  "correlation_id": "CORR-8812-B9A1",
  "status": "AWAITING_APPROVAL",
  "assigned_agent": "EMP-L05",
  "attempts": 1,
  "lease_owner": "worker_01",
  "result": {
    "draft_id": "Q4-019",
    "hook": "Pernah gak sih mau komen tapi gak jadi gara-gara takut diserang netizen lain?",
    "script_body": "Dalam ilmu komunikasi, ini disebut teori Spiral of Silence...",
    "verification_status": "PASSED_ACADEMIC_CHECK"
  },
  "requires_approval": true,
  "approval_gate": "Maus (PR & Approval Gate)",
  "error": null
}
```

---

### C. Endpoint Keputusan Persetujuan Pemilik (`POST /api/hq/tasks/{task_id}/decision`)
* **Request Payload:**
```json
{
  "decision": "APPROVED",
  "reason": "Naskah tajam dan sesuai dengan materi kurikulum DEP_05",
  "decided_by": "PEMILIK_HQ"
}
```
* **Response Payload (HTTP 200 OK):**
```json
{
  "ok": true,
  "task_id": "JOB-20261113-002",
  "status": "COMPLETED",
  "next_stage": "READY_FOR_STUDIO_PRODUCTION"
}
```

---

## 2. KONTRAK ADAPTER ANTAR-DIVISI (PYTHON PROTOCOL)

```python
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

class BaseDivisionAdapter(ABC):
    @abstractmethod
    def validate_input(self, task_input: Dict[str, Any]) -> bool:
        """Memvalidasi kesesuaian input sebelum dimasukkan ke antrean pekerjaan."""
        pass

    @abstractmethod
    def execute_stage(self, task_id: str, stage_name: str, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Mengeksekusi tahapan kerja spesifik di dalam divisi terkait."""
        pass

    @abstractmethod
    def handle_rejection(self, task_id: str, reason: str) -> bool:
        """Menangani revisi atau pembatalan draf dari gerbang persetujuan."""
        pass
```
