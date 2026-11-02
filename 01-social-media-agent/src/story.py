"""Original, source-bounded story scaffolds. Nara is fictional, not a testimonial.

These are explicitly labelled template fallbacks, never presented as LLM output.
No invented benchmarks, time savings, prices, or claims of personal experience.
"""
from __future__ import annotations

STAGES = ["tokoh", "masalah", "percobaan", "titik_balik", "batasan", "pelajaran", "cta"]
KINDS = ["hook", "point", "point", "point", "limit", "point", "cta"]
HEADLINES = ["Kenalan dengan Nara", "Ada yang mengganjal", "Coba langkah kecil", "Ini yang ia pelajari", "Tetap ada batasnya", "Bawa pulang ini", "Pahami, lalu coba"]
VISUALS = [
    {"type": "character", "props": {"emotion": "curious"}},
    {"type": "clock", "props": {"label": "Waktu cari jawaban", "illustrative": True}},
    {"type": "diagram", "props": {"nodes": [{"title": "Tentukan tugas"}, {"title": "Beri konteks"}, {"title": "Periksa hasil"}]}},
    {"type": "compare", "props": {"left": {"title": "Tebak-tebakan", "items": ["Langsung percaya"]}, "right": {"title": "Lebih terarah", "items": ["Cek ke sumber"]}}},
    {"type": "thermometer", "props": {"label": "Perlu verifikasi", "level": 0.65, "illustrative": True}},
    {"type": "steps", "props": {"items": [{"title": "Mulai dari tugas kecil"}, {"title": "Tetap cek hasilnya"}]}},
    {"type": "character", "props": {"emotion": "happy"}},
]

# Each tuple supplies problem, experiment, discovery, limitation, lesson.
# Statements about a category are referenced; the character's actions are fiction.
ARCS = {
    "agents": (
        "Nara punya daftar tugas. Ia bingung, apakah AI agent cuma nama lain untuk chatbot?",
        "Ia membandingkan alurnya: chatbot menjawab pertanyaan, sedangkan agent dapat memakai alat untuk menjalankan langkah kerja.",
        "Ternyata bedanya ada pada tindakan. Agent bisa menjalankan rangkaian langkah, tetapi izin dan pemeriksaan manusia tetap penting.",
        "Satu langkah salah bisa ikut terbawa ke langkah berikutnya. Jangan beri akses besar hanya karena demonya terlihat rapi.",
        "Mulai dari tugas kecil dan izin terbatas. Minta agent berhenti untuk persetujuan sebelum tindakan penting.",
        "Kalau AI boleh bertindak, siapa yang memegang tombol berhenti? Menurut Nara, jawabannya tetap kamu.",
    ),
    "on_device": (
        "Sinyal Nara hilang saat perjalanan. Ia bertanya, bisakah AI tetap bekerja langsung dari perangkatnya?",
        "Ia mencari contoh model lokal. Sebagian AI memang dirancang untuk berjalan di perangkat, bukan selalu mengirim jawaban ke server.",
        "Ibarat membawa buku saku, sebagian kemampuan bisa ikut tanpa koneksi. Tetapi perangkat dan ukuran model tetap menentukan.",
        "Tidak semua ponsel sanggup. Model lokal bisa lebih lambat, memakai memori, dan kemampuannya tidak selalu setara model server.",
        "Cocokkan model dengan perangkat dan tugas. Uji dulu pada data yang tidak rahasia, bukan langsung pada dokumen penting.",
        "Kalau ingin mencoba AI lokal, perangkat apa yang kamu punya? Mulai dari kebutuhan, bukan dari nama model.",
    ),
    "small_models": (
        "Nara melihat model AI kecil. Ia penasaran, apakah ukuran kecil selalu berarti jawaban kurang berguna?",
        "Ia membaca contoh penggunaannya. Model kecil bisa dipilih untuk tugas terbatas ketika kebutuhan perangkat ikut dipertimbangkan.",
        "Seperti alat di kotak perkakas, yang berguna bukan selalu yang terbesar. Tugas yang jelas membantu memilih alat yang tepat.",
        "Model kecil tetap punya batas. Tugas panjang atau rumit bisa gagal, dan ukuran bukan satu-satunya penentu kualitas.",
        "Bandingkan pada tugas kamu sendiri. Pisahkan contoh demonstrasi dari hasil pengujian yang benar-benar bisa diperiksa.",
        "Tugas apa yang sebenarnya ingin kamu selesaikan? Tulis dulu kebutuhannya sebelum memilih model AI.",
    ),
    "coding": (
        "Nara sedang belajar membuat aplikasi. Ketika AI menawarkan bantuan kode, ia bingung harus mulai dari mana.",
        "Ia mencoba permintaan kecil: jelaskan satu fungsi dan buat contoh sederhana, bukan meminta seluruh aplikasi sekaligus.",
        "Kode yang terlihat masuk akal belum tentu benar. Ia perlu menjalankan contoh dan memeriksa hasilnya sebelum dipakai.",
        "AI bisa membuat kesalahan keamanan atau dependensi yang tidak cocok. Jangan jalankan kode yang belum kamu pahami.",
        "Minta perubahan kecil, baca bedanya, lalu uji. Rahasia seperti kata sandi dan kunci API tidak perlu masuk ke prompt.",
        "Kalau kamu belajar kode, bagian mana yang paling membingungkan? Jadikan itu satu percobaan kecil.",
    ),
    "rag_memory": (
        "Nara punya banyak catatan. Ia bertanya, bagaimana AI bisa menjawab tanpa membaca seluruh dokumennya setiap kali?",
        "Ia mengenal retrieval: cari bagian dokumen yang relevan, lalu gunakan bagian itu sebagai konteks jawaban.",
        "Seperti daftar isi dan catatan penanda, pencarian membantu menemukan halaman yang perlu dibaca. Itu bukan ingatan manusia.",
        "Potongan yang salah bisa menghasilkan jawaban yang salah. Izin akses dokumen dan pemeriksaan kutipan tetap diperlukan.",
        "Coba beberapa pertanyaan yang jawabannya kamu tahu. Periksa apakah sumber yang diambil benar-benar mendukung jawaban.",
        "Punya tumpukan catatan? Sebelum bertanya ke AI, pastikan dulu sumber dan batas aksesnya jelas.",
    ),
    "multimodal": (
        "Nara menemukan AI yang menerima gambar dan suara. Ia ingin tahu, apakah itu berarti AI memahami seperti manusia?",
        "Ia mencoba memberi satu gambar dan pertanyaan sederhana. Sistem mengolah pola dari input untuk menghasilkan respons.",
        "Jawaban yang terdengar yakin bukan bukti bahwa gambar dibaca dengan benar. Ia memeriksa detail penting secara langsung.",
        "Teks kecil, konteks gambar, atau suara bising bisa membingungkan. Jangan pakai hasilnya sebagai diagnosis atau keputusan penting.",
        "Mulai dengan bahan yang tidak sensitif. Bandingkan jawaban dengan detail yang bisa kamu lihat atau dengar sendiri.",
        "Kalau mencoba AI gambar atau suara, apa yang ingin kamu cek? Jangan lupa verifikasi hasilnya.",
    ),
    "safety": (
        "Nara hendak menempelkan dokumen ke chatbot. Lalu ia berhenti: apakah dokumen itu boleh dibagikan?",
        "Ia memeriksa isinya lebih dulu, memisahkan informasi umum dari data pribadi dan rahasia yang tidak perlu dibagikan.",
        "Mudah bukan berarti aman. Ia memilih contoh tanpa identitas dan membaca aturan layanan sebelum mengunggah bahan.",
        "Pengaturan tiap layanan berbeda. Menghapus satu nama belum tentu membuat seluruh dokumen menjadi anonim atau aman.",
        "Bagikan seperlunya saja. Untuk data sensitif, minta izin pemilik data dan pilih jalur yang memang disetujui.",
        "Sebelum menekan kirim, tanyakan: adakah informasi yang tidak perlu keluar? Itu langkah kecil yang penting.",
    ),
    "cost": (
        "Nara melihat label AI gratis. Ia bertanya, apakah gratis berarti bisa dipakai tanpa batas untuk semua tugas?",
        "Ia memeriksa batas pemakaian dan kebutuhan tugasnya, bukan hanya angka harga yang paling menarik.",
        "Ibarat paket internet, biaya dan batasnya bisa berbeda. Ukuran tugas serta jumlah percobaan ikut memengaruhi pemakaian.",
        "Harga dapat berubah dan paket gratis punya batas. Jangan menganggap biaya contoh sama dengan biaya pemakaian nyata.",
        "Catat pemakaian pada tugas kamu sendiri. Tetapkan batas biaya dan jangan memasukkan kunci API ke tempat publik.",
        "Pilih alat dari kebutuhan dan batasnya. Menurut kamu, apa yang lebih penting: murah atau bisa diandalkan?",
    ),
    "open_source": (
        "Nara melihat istilah model terbuka. Ia penasaran, apakah terbuka berarti bebas dipakai untuk apa saja?",
        "Ia membaca halaman model dan memeriksa lisensi serta kebutuhan perangkat sebelum mencoba contoh yang tersedia.",
        "Akses ke model tidak menghapus aturan pemakaian. Ia tetap perlu memeriksa apakah tujuannya diizinkan oleh lisensi.",
        "Tidak semua yang disebut terbuka memiliki syarat yang sama. Biaya menjalankan dan tanggung jawab penggunaan tetap ada.",
        "Baca lisensi, bukan hanya judulnya. Untuk proyek komersial, pastikan izin penggunaan sesuai sebelum meluncurkan.",
        "Pernah bingung memilih model terbuka? Mulai dari izin pakai dan kebutuhan, bukan sekadar popularitas.",
    ),
    "reasoning": (
        "Nara mendapat jawaban AI yang terdengar rinci. Ia bertanya, apakah penjelasan panjang berarti jawabannya pasti benar?",
        "Ia mengambil satu klaim dari jawaban itu, lalu mencari rujukan yang bisa diperiksa secara terpisah.",
        "Panjang teks bukan ukuran akurasi. Jawaban tetap perlu diuji, terutama saat dipakai untuk keputusan penting.",
        "AI dapat keliru meski terdengar yakin. Penjelasan yang dibuat model bukan bukti independen atas kebenarannya.",
        "Pisahkan fakta dari dugaan. Periksa sumber asli dan cari contoh yang bisa menunjukkan bahwa jawabannya salah.",
        "Saat melihat jawaban meyakinkan, apa yang kamu cek lebih dulu? Coba mulai dari satu klaim.",
    ),
}
GENERAL = (
    "Nara melihat sebuah kabar AI. Sebelum ikut membagikannya, ia ingin tahu apa yang sebenarnya dikatakan sumber.",
    "Ia membuka sumber aslinya dan mencatat bagian yang benar-benar tertulis, bukan menebak dari judul yang ramai.",
    "Judul adalah pintu masuk, bukan kesimpulan. Ia memisahkan isi sumber dari pendapat orang yang membahasnya.",
    "Tautan sumber belum otomatis membuktikan semua klaim. Isi sumber bisa terbatas, berbeda konteks, atau belum berupa pengujian.",
    "Baca sumber asli sebelum membagikan klaim. Kalau bukti belum cukup, katakan belum cukup, bukan menambah kepastian.",
    "Ada kabar AI yang membuatmu penasaran? Buka sumbernya dulu, lalu tentukan bagian mana yang benar-benar didukung.",
)


def build_arc(theme: str) -> list[str]:
    return list(ARCS.get(theme or "general", GENERAL))


def hook_options(theme: str) -> list[dict]:
    subject = {
        "agents": "AI agent", "on_device": "AI tanpa internet", "small_models": "model kecil",
        "coding": "AI penulis kode", "rag_memory": "AI pembaca dokumen", "multimodal": "AI pembaca gambar",
        "safety": "data kamu", "cost": "AI gratis", "open_source": "model terbuka", "reasoning": "jawaban AI",
    }.get(theme or "general", "kabar AI")
    first = {
        "agents": "Nara bingung: agent itu chatbot yang lain?",
        "on_device": "Sinyal hilang. Apakah AI Nara ikut berhenti?",
        "safety": "Nara hampir mengirim dokumen yang bukan miliknya.",
        "coding": "Kode dari AI terlihat benar. Sudah aman?",
    }.get(theme or "general", f"Nara menemukan {subject}. Apa yang perlu dicek?")
    return [{"id": "A", "text": first}, {"id": "B", "text": f"Sebelum memakai {subject}, Nara cek satu hal."}]
