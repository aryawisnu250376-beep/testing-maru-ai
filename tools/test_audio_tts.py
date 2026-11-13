# Periksa apakah edge-tts terpasang untuk voiceover bahasa Indonesia
try:
    import edge_tts
    print("edge_tts: TERPASANG")
except ImportError:
    print("edge_tts: BELUM TERPASANG")
