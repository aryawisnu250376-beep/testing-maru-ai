---
name: omni-route
description: Konfigurasi dan tata kelola OmniRoute (diegosouzapw/OmniRoute, evolusi 9Router di port 20128) sebagai Model Router cerdas multi-provider dengan fallback berjenjang, kontrol kuota/biaya, auto-refresh OAuth, dan kompatibilitas OpenAI/Claude untuk MARU HQ, Social Media Agent, dan Academic AI.
source: https://github.com/diegosouzapw/OmniRoute
---
# Skill: OmniRoute — Smart Multi-Provider AI Gateway & Model Router

Gunakan skill ini saat merancang, mendiagnosis, atau mengoptimalkan routing model LLM/Embedding/STT pada **MARU HQ**, **01-social-media-agent**, dan **02-academic-ai**.

## Mengapa OmniRoute Cocok Langsung dengan MARU AI

OmniRoute adalah pengembangan lanjutan dari **9Router** dan berjalan secara *drop-in* pada endpoint standar yang sudah dipakai di seluruh codebase MARU:
- Endpoint lokal: `http://localhost:20128/v1`
- Kompatibel langsung dengan variabel `.env` MARU yang sudah ada:
  - `ROUTER_BASE_URL=http://localhost:20128/v1` (di `01-social-media-agent`)
  - `NINE_ROUTER_BASE_URL=http://localhost:20128/v1` (di `02-academic-ai`)

## Strategi Routing 4-Tier (Hemat Biaya & Anti-Putus)

Susun rantai fallback di OmniRoute sesuai tanggung jawab komponen MARU:

1. **Tier 1 — High-Reasoning (Manager, Verifier, QC, & Scriptwriter Utama)**:
   Model penalaran kuat untuk verifikasi sitasi akademik (`MODEL_MANAGER`) dan penulisan hook/naskah utama (`LLM_MODEL_STRONG`).
2. **Tier 2 — Fast API Providers (Groq / Gemini Flash / DeepSeek)**:
   Latensi rendah untuk spesialis mata kuliah (`MODEL_<MAPEL>_A/B`) dan revisi cepat.
3. **Tier 3 — Low-Cost Bulk (`LLM_MODEL_CHEAP`)**:
   Klasifikasi tren harian, *clustering* topik radar, dan ekstraksi metadata.
4. **Tier 4 — Local / Free Fallback (Ollama lokal `http://localhost:11434/v1` / Free Tier)**:
   Menjamin operasional dasar tetap berjalan saat kuota internet/API habis, selama sesuai kebijakan privasi data.

## Aturan Kebijakan & Keamanan MARU HQ (Wajib Dipatuhi)

1. **Jangan Ekspos Dashboard ke Publik**: Port `20128` wajib terikat ke `127.0.0.1` (`localhost`), jangan pernah dibuka ke internet publik tanpa autentikasi berlapis.
2. **Verifikasi ID Model Aktual**: Sebelum mengisi `MODEL_EMBEDDING`, `MODEL_STT`, atau `MODEL_MANAGER` di `.env`, selalu cek daftar nyata lewat `GET http://localhost:20128/v1/models` — jangan menebak nama model.
3. **Perlindungan Privasi Fallback**: Jangan mengarahkan dokumen akademik sensitif atau memori pribadi ke provider eksternal gratis yang tidak diizinkan oleh *Policy Engine* MARU.
4. **Penanganan Kegagalan Jujur**: Jika seluruh tier gagal atau *timeout*, kembalikan status error terstruktur — dilarang mengarang jawaban palsu seolah model berhasil dipanggil.

<!-- maru-imported-from: https://github.com/diegosouzapw/OmniRoute -->
