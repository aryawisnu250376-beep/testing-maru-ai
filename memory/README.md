# Pusat Memori & State MARU AI (`memory/`)

Folder ini menyimpan memori terstruktur dan state operasional ringan MARU AI dengan pemisahan *scope* per divisi (sesuai prinsip arsitektur MARU HQ).

## Pembagian Scope

- `social-media/` — State orkestrator, radar tren ringkas, dan watchlist referensi dari `01-social-media-agent`.
- `academic/` — Fakta preferensi pengguna (`user_facts.json` bergaya mem0), katalog mata kuliah (`subjects_catalog.json`), dan indeks materi (`materials_index.csv`) tanpa menyertakan PDF besar atau biner SQLite.
- `hq/` — Konteks lintas divisi yang diizinkan untuk koordinasi MARU HQ (`shared_context.json`).

## Keamanan & Privasi

- File `.env`, API key, token Telegram/TikTok/GitHub, serta biner database `.db`/`.sqlite` **dilarang** disimpan di folder ini dan diblokir otomatis oleh `.gitignore` maupun `maru_github_sync`.
