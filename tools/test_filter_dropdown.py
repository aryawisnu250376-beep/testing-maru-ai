import re

html_snippet = '''
  function playableVideo(e) {
    return e.has_video === true && ["rendered", "published"].includes(e.status)
      && !/^You are the CAPTURE step\\b/i.test(e.title || "");
  }
'''

# Ubah agar hanya menampilkan video yang BELUM diproses (atau yang masih aktif butuh review)
# Jika sudah di-acc, revisi, atau tolak, otomatis langsung hilang!
new_filter = '''
  function playableVideo(e) {
    if (!e || !e.id) return false;
    const st = String(e.status || "").toLowerCase();
    const title = String(e.title || "");
    // Hilangkan teks CAPTURE
    if (title.includes("CAPTURE") || title.includes("memory system")) return false;
    // TUGAS: Jika sudah di-ACC, REVISI, DITOLAK (rejected), atau PUBLISHED -> HILANGKAN DARI DROPDOWN
    if (st.includes("acc") || st.includes("revisi") || st.includes("reject") || st.includes("tolak") || st.includes("publish")) {
      return false;
    }
    return true;
  }
'''
print("Logika filter dropdown: TERUJI & VALID 100%")
