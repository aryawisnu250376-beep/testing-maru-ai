# Uji jika user mau KOSONG TOTAL (0 item di dropdown jika belum ada draf baru):
# Status 'rendered' adalah video yang sudah selesai diproduksi sebelumnya.
# Jika user ingin dropdown benar-benar kosong bersih dari semua riwayat kemarin:
episodes = [
    {"id": "1", "title": "Model open source...", "status": "rendered"},
    {"id": "2", "title": "Model AI baru: Mistral...", "status": "rendered"},
]

# Jika hanya menampilkan draf yang SEDANG menunggu ACC (pending_approval):
# Karena workflow = 0 (tidak ada pending), maka dropdown harus = 0 (kosong bersih)!
def filter_only_pending(episodes):
    return [e for e in episodes if e.get("status") == "pending_approval"]

res = filter_only_pending(episodes)
assert len(res) == 0
print("UJI DROPDOWN KOSONG BERSIH SAAT WORKFLOW 0: VALID 100%!")
