# Change: video-explainer (OpenMontage-style, lokal, Rp 0)

## Kenapa
User yang tidak paham bacaan butuh penjelasan video singkat dari materi.

## Apa (arsitektur pipeline ala OpenMontage, tanpa kode AGPL)
Tahap: `preflight → research → script → narration → slides → render → review`.
- research: rangkuman existing (grounded PDF) dijadikan sumber naskah.
- script: pecah heuristik jadi ≤VIDEO_MAX_SCENES adegan (tanpa LLM ekstra).
- narration: Piper offline (suara id) → fallback edge-tts; gagal keduanya = error jujur.
- slides: PNG 1280x720 via PIL (font DejaVu bawaan).
- render: ffmpeg concat + audio + subtitle mov_text → MP4 di data/videos/.
- review: decision log (TTS terpilih, dsb.) tersimpan di metadata JSON.

## Antarmuka
- Job `video` di /api/jobs (progres tahap); GET /api/videos, download MP4.
- Bot /video <topik>; tombol web + player.
- Butuh: ffmpeg + (piper-tts | edge-tts).

## Bukan bagian ini
Footage stok, avatar, musik, API video berbayar.
