---
name: open-notebook
description: Integrasi Open Notebook (lfnovo/open-notebook & open-notebook-mcp) sebagai ruang riset multi-sumber mandiri bergaya NotebookLM untuk merangkum PDF kuliah, catatan studi, pencarian vektor, dan pembuatan podcast diskusi multi-pembicara di MARU Academic AI.
source: https://github.com/lfnovo/open-notebook
---
# Skill: Open Notebook (Self-Hosted Research & Study Intelligence)

Gunakan skill ini saat mengorganisasi buku catatan riset per mata kuliah, menggabungkan banyak sumber (PDF kuliah, transkrip YouTube, jurnal ilmiah, halaman web), membuat catatan terverifikasi, atau merancang naskah audio/podcast diskusi belajar (1–4 pembicara) yang terintegrasi dengan **MARU Academic AI**.

## Arsitektur & Keunggulan untuk MARU AI

- **Kedaulatan Data Penuh**: Seluruh materi kuliah dan catatan pribadi tersimpan lokal (tidak terkunci ke cloud pihak ketiga).
- **Multi-Provider & Lokal Gratis**: Mendukung penuh **Ollama**, **9Router / OmniRoute** (`http://localhost:20128/v1`), OpenAI-compatible, Gemini, dan Groq.
- **Integrasi MCP (`open-notebook-mcp`)**: Agent dapat membaca daftar notebook, mencari sumber, menambah catatan ringkasan, dan memulai sesi tanya-jawab kontekstual langsung lewat MCP.

## Konfigurasi MCP (`.vscode/mcp.json` / Hermes Config)

```json
{
  "mcpServers": {
    "open-notebook": {
      "command": "uvx",
      "args": ["open-notebook-mcp"],
      "env": {
        "OPEN_NOTEBOOK_URL": "http://localhost:5055",
        "OPEN_NOTEBOOK_PASSWORD": "${OPEN_NOTEBOOK_PASSWORD}"
      }
    }
  }
}
```
*(Catatan keamanan MARU: Simpan `OPEN_NOTEBOOK_PASSWORD` dan `OPEN_NOTEBOOK_ENCRYPTION_KEY` hanya di file `.env` lokal, jangan pernah di-commit ke GitHub.)*

## Alur Kerja Standar di Ekosistem MARU

1. **Pemetaan Notebook per Mata Kuliah**:
   Buat/pilih notebook sesuai 7 kode mata kuliah MARU (`PP`, `PA`, `BING`, `PR`, `ILKOM`, `KAP`, `DJ`) agar konteks antar-mapel tidak bercampur.
2. **Ingesti & Transformasi Materi**:
   Masukkan PDF modul/jurnal → jalankan ekstraksi poin inti, daftar istilah kunci, dan peta argumen.
3. **Disiplin Sitasi Akademik**:
   Saat menyalin hasil temuan dari Open Notebook ke jawaban pengguna, selalu pertahankan atribusi nama dokumen dan nomor halaman; pisahkan tegas antara isi materi internal dengan pengayaan eksternal.
4. **Produksi Podcast / Audio Belajar**:
   Susun dialog 2–3 pembicara (mis. *Dosen Pengampu*, *Mahasiswa Kritis*, *Praktisi*) dengan durasi padat 3–7 menit berdasarkan poin yang sudah terverifikasi sumbernya.

<!-- maru-imported-from: https://github.com/lfnovo/open-notebook -->
