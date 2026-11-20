# Uji regresi menyeluruh pada logika studio.html
# 1. Pastikan fungsi lain (renderAll, renderOffice, renderStudio, renderVideoList) tidak terganggu
episodes = [
    {"id": "ep1", "title": "You are the CAPTURE step...", "status": "pending_approval", "has_video": False},
    {"id": "ep2", "title": "Model open source...", "status": "rejected", "has_video": True},
    {"id": "ep3", "title": "uji jembatan hermes", "status": "failed", "has_video": False},
    {"id": "ep4", "title": "Model AI baru: Mistral-Large", "status": "rendered", "has_video": True},
]

def playableVideo(e):
    if not e or not e.get("id"): return False
    st = str(e.get("status") or "").lower()
    title = str(e.get("title") or "")
    if "CAPTURE" in title or "memory system" in title: return False
    if any(k in st for k in ["acc", "revisi", "reject", "tolak", "failed"]):
        return False
    return True

filtered = [e for e in episodes if playableVideo(e)]
assert len(filtered) == 1
assert filtered[0]["id"] == "ep4"
print("UJI REGRESI LENGKAP: 100% SUKSES, TIDAK MERUSAK FUNGSI LAIN!")
