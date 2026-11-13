# AGENT REGISTRY — 9 OFFICIAL LEADERS & DECORATIVE NPCS
**Dokumen Referensi: Phase 6.0 Integration Audit & Job System Architecture Blueprint**
*Inventarisasi Agen, Otoritas, Batas Biaya & Status Ketersediaan*
*Klasifikasi Status Komponen: `VERIFIED` | `PARTIAL` | `PROPOSED`*
*Tanggal Rilis: 13 November 2026*

---

## 1. REGISTRI RESMI 9 OFFICIAL AI LEADERS (TIER 1)

| ID | Nama Agen | Departemen Resmi | Peran & Tanggung Jawab | Provider / Model Aktual | Tool Permissions | Batas Biaya (IDR/Task) | Status Kemampuan Aktual |
|---|---|---|---|---|---|---|---|
| `EMP-L01` | **Bima** | Executive HQ | Chief Executive Intelligence, perancangan visi & supervisi pipeline | Claude 3.5 Sonnet / GPT-4o | `delegate_task`, `view_reports`, `emergency_stop` | Rp 25.000 | `PARTIAL` (Orkestrasi manual di UI) |
| `EMP-L02` | **Hermes** | Creative & Scriptwriting | Creative Director & Scriptwriter, naskah hook 3 detik | Claude 3.5 Sonnet / Mistral | `compose_draft`, `read_watchlist`, `format_script` | Rp 15.000 | `VERIFIED` (`hermes_create_draft` aktif) |
| `EMP-L03` | **Nara** | Brainstorming & Trends | Research Ideation Specialist, analisis tren & psikologi audiens | GPT-4o-mini / Local Scraper | `read_trends`, `search_topics`, `calculate_retention` | Rp 10.000 | `PARTIAL` (Watchlist aktif, scraper otomatis belum) |
| `EMP-L04` | **Cendekia** | Academic Research Library | Chief Academic Researcher, verifikasi teori & kurikulum | Claude 3.5 Sonnet / Knowledge Base | `query_curriculum`, `verify_citation`, `audit_ethics` | Rp 12.000 | `VERIFIED` (Basis pengetahuan 7 dept tersedia) |
| `EMP-L05` | **Maus** | PR & Approval Gate | Quality Gatekeeper & Compliance, filter isu & penegakan ACC | Deterministic Policy Engine | `inspect_guidelines`, `block_unauthorized`, `submit_acc` | Rp 5.000 | `VERIFIED` (`mausbot_card_decision` aktif) |
| `EMP-L06` | **Kirana** | Video Production | Executive Video Producer, rendering video 9:16 vertikal | FFmpeg / MoviePy / Local GPU | `render_timeline`, `composite_subtitles`, `encode_mp4` | Rp 20.000 | `PARTIAL` (Skrip render mandiri ada, worker belum) |
| `EMP-L07` | **Ardi** | Voice Production Studio | Lead Voice Actor & Sound Engineer, dubbing karakter muda | Edge TTS / Local Audio DSP | `synthesize_speech`, `apply_equalizer`, `mix_audio` | Rp 10.000 | `PARTIAL` (Aset audio terbukti, streaming worker belum) |
| `EMP-L08` | **Wira** | IT Observability | Principal Systems Engineer, telemetri server & database SQLite | Local Python Telemetry / HealthCheck | `query_metrics`, `restart_service`, `db_vacuum` | Rp 5.000 | `VERIFIED` (Heartbeat polling & telemetri aktif) |
| `EMP-L09` | **Ootto** | TikTok Publisher | Autonomous Pipeline Operator, eksekusi Direct Post API | TikTok Content Posting API (Sandbox) | `upload_video_chunk`, `query_publish_status`, `notify_user` | Rp 8.000 | `PARTIAL` (Alur sandbox terbukti, auto-scheduler belum) |

---

## 2. REGISTRI 18 DECORATIVE NPCS (TIER 2)
Seluruh 18 karakter pendukung (`EMP-S01` s/d `EMP-S18`) **TETAP DIKLASIFIKASIKAN SEBAGAI `DECORATIVE_NPC`**.
* **Aturan Mutlak:**
  - Tidak memiliki akses token eksekusi LLM.
  - Tidak memiliki tool permissions mandiri.
  - Batas biaya: **Rp 0 (Nol Rupiah)**.
  - Tidak diperbolehkan menerima penugasan otonom tanpa izin eksplisit pemilik MARU HQ di fase mendatang.
