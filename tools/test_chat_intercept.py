# Simulasi chat hermes_mausbot.py
low = "hubungkan tiktok"

# Kode lama yang bermasalah:
is_queue_action = "hapus" in low and ("antrean" in low or "acc" in low or "riwayat" in low)
print("Apakah dianggap hapus antrean?", is_queue_action)

# Cek kenapa bot membalas itu di screenshot:
# Di screenshot sebelumnya, user chat:
# "maus hapus semua riwayat acc dan yang sedang di antrian buat lagi saat gw bilang sekarang boleh produksi"
# Lalu bot membalas "Siap Pak Wisnu! Seluruh 6 draf di antrean ACC sudah saya arsipkan/reset..."
# Lalu user kirim: "hubungkan tiktok"
# Bot membalas persis teks yang sama: "Siap Pak Wisnu! Seluruh 0 draf di antrean ACC sudah saya arsipkan/reset..."
