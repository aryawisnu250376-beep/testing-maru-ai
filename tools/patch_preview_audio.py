with open('/home/user/maru_hq_preview.html', 'r') as f:
    c = f.read()

# Pastikan badge menunjukkan model suara muda & karakter asli
c = c.replace("Audio: Ardi Neural (Dynamic Dub)", "Audio: Young Conversational (Voice-02 Pro)")
c = c.replace("Durasi: 22s", "Durasi: 20s (Dynamic Tilt & Pop-up)")
with open('/home/user/maru_hq_preview.html', 'w') as f:
    f.write(c)
print("Preview HTML updated!")
