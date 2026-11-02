---
name: blender-mcp
description: Kendalikan Blender 3D secara langsung lewat protokol MCP (ahujasid/blender-mcp) menggunakan skrip bpy untuk membuat objek 3D, material, pencahayaan, animasi kamera, dan render aset visual MARU AI.
version: 2.1.0
source: https://github.com/ahujasid/blender-mcp
---
# Skill: Blender MCP (3D Modeling, Scene & Animation)

Gunakan skill ini saat membuat aset visual 3D, animasi pembuka video edukasi, diagram ruang 3D, atau *turntable render* untuk **MARU Social Media Corporation** maupun video penjelasan **Academic AI** melalui server `blender-mcp`.

## Prasyarat & Setup Cepat

1. **Pasang Add-on di Blender (sekali saja)**:
   - Unduh `addon.py` dari `https://raw.githubusercontent.com/ahujasid/blender-mcp/main/addon.py`.
   - Buka Blender (3.0+) → `Edit > Preferences > Add-ons > Install...` → pilih `addon.py` → centang **`Interface: Blender MCP`**.
2. **Nyalakan Bridge Socket setiap sesi**:
   - Di viewport Blender tekan tombol **`N`** → buka tab **`BlenderMCP`** → klik **`Connect to Claude / Start Server`** (membuka socket TCP lokal di port `9876`).
3. **Konfigurasi MCP Server (VS Code / Hermes / Claude)**:
   ```json
   {
     "mcpServers": {
       "blender": {
         "command": "uvx",
         "args": ["blender-mcp"]
       }
     }
   }
   ```

## Daftar Tool MCP Utama

| Tool MCP | Kegunaan |
|---|---|
| `get_scene_info` | Wajib dipanggil pertama kali untuk memeriksa daftar objek, kamera, dan lampu yang sudah ada di scene. |
| `get_object_info` | Memeriksa transformasi, dimensi, modifier, dan material satu objek spesifik. |
| `get_viewport_screenshot` | Mengambil tangkapan layar viewport untuk verifikasi visual antar-tahap sebelum render akhir. |
| `execute_blender_code` | Menjalankan kode Python `bpy` terfokus untuk memodelkan mesh, shader node, keyframe animasi, dan render. |

## Prosedur Kerja Wajib & Anti-Gagal

1. **Inspeksi dulu, jangan asumsikan scene kosong**: Selalu panggil `get_scene_info` sebelum menambah atau menghapus objek.
2. **Pecah eksekusi `bpy` menjadi langkah kecil**:
   - Langkah 1: Geometri dasar & tata letak.
   - Langkah 2: Material PBR / Principled BSDF & pencahayaan tiga titik / HDRI.
   - Langkah 3: Kamera (misal rasio vertikal `1080x1920` untuk TikTok/Reels) & animasi keyframe.
   - Jangan mengirim skrip monolitik raksasa dalam satu panggilan agar tidak terkena *socket timeout*.
3. **Cek visual berkala**: Panggil `get_viewport_screenshot` setelah menata objek dan kamera untuk memastikan objek tidak terpotong (*clipping*) atau gelap.
4. **Gunakan Path Absolut saat Render**:
   ```python
   import bpy, os
   scene = bpy.context.scene
   scene.render.resolution_x = 1080
   scene.render.resolution_y = 1920
   scene.render.filepath = os.path.abspath("D:/maru-renders/scene_01.png")
   bpy.ops.render.render(write_still=True)
   ```
5. **Keamanan**: `execute_blender_code` menjalankan Python penuh di mesin host tanpa sandbox. Jangan pernah mengeksekusi kode `bpy` dari sumber eksternal yang belum diperiksa.

<!-- maru-imported-from: https://github.com/ahujasid/blender-mcp -->
