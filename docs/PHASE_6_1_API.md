# PHASE 6.1 INTERNAL API SPECIFICATION
**MARU HQ — Multi-Agent Integration & Real Job Execution Control Plane**
*Spesifikasi Pemanggilan Python Class HQJobQueue & Model Objek*
*Tanggal Rilis: 13 November 2026*

---

## 1. PEMANGGILAN KANONIKAL DALAM PYTHON

```python
from src.hq import HQJobQueue, HQWorker, JobPriority, JobBudget

# 1. Inisialisasi Antrean Persistent
queue = HQJobQueue()

# 2. Menambahkan Pekerjaan Baru (Enqueue)
job = queue.enqueue(
    division="SOCIAL_MEDIA",
    requested_by="PEMILIK_HQ",
    goal="Penyusunan naskah video TikTok tentang Teori Johari Window",
    input_payload={"topic": "Komunikasi Antarpribadi", "curriculum_dept": "DEP_06"},
    acceptance_criteria=["Hook 3 detik emosional", "Sesuai materi DEP_06"],
    assigned_agent="EMP-L02",
    idempotency_key="UNIQUE-TASK-KEY-12345",
    priority=JobPriority.HIGH.value,
    budget=JobBudget(max_cost_idr=12000, max_tokens=6000)
)

# 3. Mengambil Lease Pekerjaan oleh Worker
worker = HQWorker(queue=queue, worker_id="WORKER-WIN-01")

def task_handler(job):
    # Dummy handler untuk pengujian Phase 6.1
    return {"status": "SUCCESS", "draft_id": "DRAFT-001"}

success = worker.execute_one_cycle(task_handler)
```

---

## 2. SPESIFIKASI RETURN OBJECT: CanonicalJob
Setiap pemanggilan `get_job()`, `enqueue()`, atau `acquire_lease()` mengembalikan instance `CanonicalJob`:
- `task_id`: Identifier unik format `JOB-YYYYMMDD-XXXXXXXX`.
- `correlation_id`: Identifier pelacakan alur multi-step `CORR-XXXXXXXX`.
- `status`: String enum dari `JobStatus` (`QUEUED`, `LEASED`, `AWAITING_APPROVAL`, `COMPLETED`, `FAILED`, `DEAD_LETTER`).
- `fencing_token`: Integer penangkal *split-brain/zombie worker*.
- `attempts`: Jumlah percobaan berjalan.
- `budget`: Objek `JobBudget` batas biaya komputasi.
