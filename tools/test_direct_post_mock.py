# Uji coba mekanisme TikTok upload video ke Direct Post / Sandbox
# Verifikasi struktur token, payload publish, dan kesiapan video mp4
import json
from pathlib import Path

video_path = Path("/home/user/maru_ai_bug_recovery_v2.mp4")
assert video_path.exists(), "Video mp4 harus ada"
size = video_path.stat().st_size
print(f"Video MP4 terverifikasi: {size} bytes ({size / (1024*1024):.2f} MB)")

# Verifikasi payload init TikTok v2
payload = {
    "post_info": {
        "title": "Bagaimana AI Menemukan & Memulihkan Bug #AI #Automation #Coding #MARU",
        "privacy_level": "SELF_ONLY",
        "disable_duet": False,
        "disable_comment": False,
        "disable_stitch": False,
        "video_cover_timestamp_ms": 1000
    },
    "source_info": {
        "source": "FILE_UPLOAD",
        "video_size": size,
        "chunk_size": size,
        "total_chunk_count": 1
    }
}
print("Payload TikTok Direct Post Init valid JSON:", json.dumps(payload, indent=2))
