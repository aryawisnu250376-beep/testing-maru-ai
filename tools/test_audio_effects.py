import subprocess
import imageio_ffmpeg
FFMPEG = imageio_ffmpeg.get_ffmpeg_exe()

# Kita buat rantai filter audio broadcast profesional (Equalizer, Bass Boost, Dynamic Compressor, Reverb Halus, dan Limiter)
# Filter: highpass=f=80, lowpass=f=12000, equalizer=f=250:width_type=h:width=100:g=3, acompressor=threshold=-18dB:ratio=4:attack=5:release=50, volume=1.8
cmd = [
    FFMPEG, "-y",
    "-i", "/home/user/maru_voice.mp3",
    "-af", "highpass=f=85,lowpass=f=11500,equalizer=f=200:width_type=o:width=1.5:g=4,equalizer=f=3200:width_type=o:width=1.2:g=3,acompressor=threshold=-16dB:ratio=3.5:attack=10:release=80:makeup=3dB",
    "/home/user/maru_voice_broadcast.mp3"
]
subprocess.run(cmd, check=True)
print("Filter audio efek broadcast BERHASIL dibuat!")
