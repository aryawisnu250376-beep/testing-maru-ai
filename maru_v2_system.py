"""
MARU v2.0 - Core Engine & Curriculum Implementation
Autonomous AI Communication Education Agency
"""

# PART 2 - 7 PERMANENT EDUCATIONAL DEPARTMENTS (CURRICULUM)
CURRICULUM = {
    "DEP_01": {
        "id": "DEP_01",
        "name": "Pendidikan Pancasila (PP)",
        "lead": "Bima",
        "focus": [
            "Pancasila sebagai fondasi kehidupan berbangsa",
            "Kewarganegaraan & etika digital",
            "Demokrasi & tanggung jawab sosial Gen Z",
            "Identitas nasional & toleransi di media sosial"
        ],
        "example_hook": "Pernah gak sih debat di kolom komentar sampai bawa-bawa suku atau agama? Padahal sila ke-3 jelas banget ngajarin ini..."
    },
    "DEP_02": {
        "id": "DEP_02",
        "name": "Pendidikan Adab (PA)",
        "lead": "Cendekia",
        "focus": [
            "Etika & tata krama komunikasi digital",
            "Respectful disagreement (debat sehat tanpa menghakimi)",
            "Moral responsibility dalam membagikan informasi",
            "Adab menegur di ruang publik vs direct message"
        ],
        "example_hook": "Niatnya ngingetin, tapi kok malah dibilang menggurui? Ini adab menegur orang tanpa bikin mereka sakit hati!"
    },
    "DEP_03": {
        "id": "DEP_03",
        "name": "Bahasa Inggris I",
        "lead": "Sasa",
        "focus": [
            "Practical conversational English",
            "Public speaking expressions & confidence",
            "Communication vocabulary dalam dunia media",
            "Everyday Gen Z slang vs professional context"
        ],
        "example_hook": "Stop bilang 'I think' terus pas presentasi! Pakai 3 frasa ini biar public speaking bahasa Inggris lu langsung naik kelas!"
    },
    "DEP_04": {
        "id": "DEP_04",
        "name": "Dasar-Dasar Public Relations",
        "lead": "Maus",
        "focus": [
            "Corporate image & reputation management",
            "Crisis communication di era viral",
            "Media relations & public opinion",
            "Strategi klarifikasi brand saat diterpa isu negatif"
        ],
        "example_hook": "Kenapa satu brand besar bisa hancur cuma gara-gara salah bikin klarifikasi di TikTok? Ini rahasia Crisis PR!"
    },
    "DEP_05": {
        "id": "DEP_05",
        "name": "Pengantar Ilmu Komunikasi",
        "lead": "Hermes",
        "focus": [
            "Model & elemen komunikasi (Shannon-Weaver, Lasswell)",
            "Hambatan komunikasi verbal & nonverbal",
            "Noise mekanik vs semantik dalam percakapan",
            "Efek komunikasi massa & media digital"
        ],
        "example_hook": "Kenapa orang yang paling banyak ngomong belum tentu paling jago komunikasi? Ini penjelasan ilmiahnya menurut Ilmu Komunikasi!"
    },
    "DEP_06": {
        "id": "DEP_06",
        "name": "Komunikasi Antarpribadi",
        "lead": "Nara",
        "focus": [
            "Active listening & empati dalam hubungan",
            "Self-disclosure (teori Johari Window & Social Penetration)",
            "Manajemen konflik pertemanan & percintaan",
            "Kenapa overthinking sering merusak hubungan"
        ],
        "example_hook": "Kenapa makin sering chat malah makin gampang salah paham dan berantem? Sains komunikasi punya jawabannya!"
    },
    "DEP_07": {
        "id": "DEP_07",
        "name": "Dasar-Dasar Jurnalistik",
        "lead": "Raka",
        "focus": [
            "Nilai berita (News Values) & 5W+1H",
            "Fact-checking & verifikasi sumber informasi",
            "Membedakan misinformasi, disinformasi, dan fakta",
            "Etika jurnalistik di era media sosial instan"
        ],
        "example_hook": "Lu pernah percaya berita viral yang ternyata hoaks total? Ini cara jurnalis profesional membedakan fakta vs fitnah dalam 3 detik!"
    }
}

# PART 7 - 7-DAY CONTENT ROTATION SCHEDULE
SEVEN_DAY_ROTATION = [
    {"day": 1, "dept": "DEP_01", "name": "Pendidikan Pancasila"},
    {"day": 2, "dept": "DEP_02", "name": "Pendidikan Adab"},
    {"day": 3, "dept": "DEP_03", "name": "Bahasa Inggris I"},
    {"day": 4, "dept": "DEP_04", "name": "Dasar-Dasar Public Relations"},
    {"day": 5, "dept": "DEP_05", "name": "Pengantar Ilmu Komunikasi"},
    {"day": 6, "dept": "DEP_06", "name": "Komunikasi Antarpribadi"},
    {"day": 7, "dept": "DEP_07", "name": "Dasar-Dasar Jurnalistik"},
]

print("MARU v2.0 Curriculum Specification loaded successfully!")
