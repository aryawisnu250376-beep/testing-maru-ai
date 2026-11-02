# Change: ai-stack (15 alat, bertahap)

## Data & memori (04-07)
- Scrapling: webfetch (Scrapling→httpx) untuk /web (DDG, tanpa key).
- Docling: parsing PDF utama, fallback pypdf→OCR.
- PageIndex-inspired: tree index seksi + RAG_MODE vector/tree/hybrid (tanpa SDK).
- mem0-inspired: user_facts SQLite + recall keyword (tanpa server vektor).

## Hemat token (03+08, internal)
- compress.py: dedup/truncate chunk, rolling history penting-dulu, estimasi hemat.
- Prompt internal baru ditulis ringkas ala-caveman.

## Monitoring+prompt (10+11)
- TrendRadar: eksternal; n8n/trend_briefing.json + panduan.
- Fabric-inspired: prompts/ + loader + /jelaskan (ELI5).

## Sandbox (09)
- Daytona: docs workflow saja (app tidak eksekusi kode user).

## Otak (01, skills)
- skills.py: skill bentuk-jawaban per task+subject dari jawaban VERIFIED.
