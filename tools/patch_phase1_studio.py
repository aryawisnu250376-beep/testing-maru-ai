import re

with open('/home/user/studio_bulletproof.html', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Tambahkan tombol navigasi Virtual Office 3D ke dalam sidebar
nav_target = """    <button class="nav-btn" data-page="studio">
      <svg viewBox="0 0 24 24"><rect x="6" y="2" width="12" height="20" rx="2.5"/><polygon points="10 9 15 12 10 15 10 9"/></svg>
      <span>Studio Video</span>
      <span class="nav-badge">3 Gaya</span>
    </button>"""

nav_replacement = """    <button class="nav-btn" data-page="studio">
      <svg viewBox="0 0 24 24"><rect x="6" y="2" width="12" height="20" rx="2.5"/><polygon points="10 9 15 12 10 15 10 9"/></svg>
      <span>Studio Video</span>
      <span class="nav-badge">3 Gaya</span>
    </button>
    <button class="nav-btn" data-page="office" id="nav-btn-office">
      <svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>
      <span>Kantor 3D</span>
      <span class="nav-badge" style="background:rgba(56,189,248,0.2);color:var(--cyan);border-color:var(--cyan)">ISO 3D</span>
    </button>"""

if nav_target in content:
    content = content.replace(nav_target, nav_replacement, 1)
    print("Nav button Kantor 3D inserted successfully!")
else:
    print("WARNING: nav_target not found!")

# 2. Tambahkan section id="page-office" ke dalam container page-view
section_target = """  <!-- PAGE: STUDIO VIDEO INTERAKTIF -->
  <section id="page-studio" class="page-view hidden">"""

section_office_html = """  <!-- PAGE: VIRTUAL OFFICE 3D (ISOMETRIC DIORAMA PHASE 1) -->
  <section id="page-office" class="page-view hidden" style="padding:0;position:relative;height:calc(100vh - 60px);overflow:hidden;">
    <!-- Top Command Toolbar -->
    <div style="position:absolute;top:12px;left:14px;right:14px;z-index:40;display:flex;justify-content:space-between;align-items:center;background:rgba(15,23,42,0.88);backdrop-filter:blur(16px);border:1px solid rgba(56,189,248,0.3);border-radius:14px;padding:8px 16px;box-shadow:0 8px 24px rgba(0,0,0,0.5);">
      <div style="display:flex;align-items:center;gap:10px;">
        <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--cyan);box-shadow:0 0 10px var(--cyan);"></span>
        <b style="font-size:12px;letter-spacing:0.5px;">MARU HQ · LIVING ISOMETRIC 3D DIORAMA</b>
      </div>
      <div style="display:flex;align-items:center;gap:8px;">
        <div style="display:flex;gap:4px;background:rgba(0,0,0,0.4);padding:3px;border-radius:10px;border:1px solid rgba(255,255,255,0.1);">
          <button id="cam-iso-btn" onclick="window.MaruOffice3D.setCameraMode('iso')" style="background:var(--cyan);color:#040812;border:none;padding:4px 10px;border-radius:7px;font-size:10px;font-weight:700;cursor:pointer;">📐 ISO CAMERA</button>
          <button id="cam-free-btn" onclick="window.MaruOffice3D.setCameraMode('free')" style="background:transparent;color:var(--muted);border:none;padding:4px 10px;border-radius:7px;font-size:10px;font-weight:700;cursor:pointer;">🌐 FREE ORBIT</button>
        </div>
        <button onclick="window.MaruOffice3D.resetCamera()" style="background:rgba(255,255,255,0.06);border:1px solid rgba(255,255,255,0.12);color:var(--ink);padding:5px 10px;border-radius:8px;font-size:10px;font-weight:700;cursor:pointer;">↺ Reset</button>
      </div>
    </div>

    <!-- 3D Canvas Viewport Container -->
    <div id="office-3d-viewport" style="width:100%;height:100%;position:absolute;top:0;left:0;z-index:1;"></div>

    <!-- Floating Room Labels & Speech Bubbles Container -->
    <div id="office-overlay-container" style="position:absolute;top:0;left:0;width:100%;height:100%;pointer-events:none;z-index:30;"></div>

    <!-- Interactive Inspector Panel (Right Drawer) -->
    <div id="office-inspector-panel" style="position:absolute;right:16px;top:68px;width:300px;z-index:50;background:rgba(15,23,42,0.92);backdrop-filter:blur(20px);border:1px solid var(--cyan);border-radius:16px;padding:16px;box-shadow:0 16px 40px rgba(0,0,0,0.8);display:none;">
      <span onclick="window.MaruOffice3D.closeInspector()" style="position:absolute;top:12px;right:14px;cursor:pointer;font-size:16px;color:var(--muted);">✕</span>
      <span id="insp-badge" style="font-size:9px;font-weight:800;padding:2px 8px;border-radius:6px;text-transform:uppercase;display:inline-block;margin-bottom:6px;background:var(--cyan);color:#040812;">DEPARTEMEN</span>
      <h3 id="insp-title" style="font-size:14px;font-weight:800;margin-bottom:2px;color:#fff;">Nama Departemen</h3>
      <div id="insp-role" style="font-size:11px;color:var(--cyan);font-weight:600;margin-bottom:12px;">Leader: Bima</div>
      <div style="background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;font-size:11px;border:1px solid rgba(255,255,255,0.08);margin-bottom:8px;">
        <div style="color:var(--muted);margin-bottom:2px;">Status Operasional:</div>
        <div id="insp-status" style="font-weight:700;color:var(--emerald);">WORKING — Terhubung Backend</div>
      </div>
      <div style="background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;font-size:11px;border:1px solid rgba(255,255,255,0.08);margin-bottom:12px;">
        <div style="color:var(--muted);margin-bottom:2px;">Tugas Aktif:</div>
        <div id="insp-task" style="color:#cbd5e1;line-height:1.4;">Standby monitoring antrean tugas</div>
      </div>
      <button onclick="window.MaruOffice3D.focusSelected()" style="width:100%;padding:8px;border-radius:10px;font-size:11px;font-weight:700;cursor:pointer;border:none;background:var(--cyan);color:#040812;">🎯 Fokuskan Kamera</button>
    </div>

    <!-- Mobile Touch D-Pad (Bottom Right) -->
    <div style="position:absolute;right:14px;bottom:75px;z-index:45;display:grid;grid-template-columns:repeat(3,34px);grid-template-rows:repeat(2,34px);gap:4px;">
      <div onclick="window.MaruOffice3D.panCam(0,3)" style="background:rgba(15,23,42,0.85);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,0.4);border-radius:8px;color:var(--cyan);display:flex;align-items:center;justify-content:center;cursor:pointer;font-weight:bold;font-size:12px;">▲</div>
      <div onclick="window.MaruOffice3D.zoomCam(0.85)" style="background:rgba(15,23,42,0.85);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,0.4);border-radius:8px;color:var(--cyan);display:flex;align-items:center;justify-content:center;cursor:pointer;font-weight:bold;font-size:11px;">🔍+</div>
      <div onclick="window.MaruOffice3D.rotateCam(-0.25)" style="background:rgba(15,23,42,0.85);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,0.4);border-radius:8px;color:var(--cyan);display:flex;align-items:center;justify-content:center;cursor:pointer;font-weight:bold;font-size:12px;">↶</div>
      <div onclick="window.MaruOffice3D.panCam(0,-3)" style="background:rgba(15,23,42,0.85);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,0.4);border-radius:8px;color:var(--cyan);display:flex;align-items:center;justify-content:center;cursor:pointer;font-weight:bold;font-size:12px;">▼</div>
      <div onclick="window.MaruOffice3D.zoomCam(1.15)" style="background:rgba(15,23,42,0.85);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,0.4);border-radius:8px;color:var(--cyan);display:flex;align-items:center;justify-content:center;cursor:pointer;font-weight:bold;font-size:11px;">🔍-</div>
      <div onclick="window.MaruOffice3D.rotateCam(0.25)" style="background:rgba(15,23,42,0.85);backdrop-filter:blur(8px);border:1px solid rgba(56,189,248,0.4);border-radius:8px;color:var(--cyan);display:flex;align-items:center;justify-content:center;cursor:pointer;font-weight:bold;font-size:12px;">↷</div>
    </div>

    <!-- Bottom Status Bar Hooked to Real State -->
    <div style="position:absolute;bottom:10px;left:14px;right:14px;z-index:40;background:rgba(15,23,42,0.92);backdrop-filter:blur(16px);border:1px solid rgba(56,189,248,0.3);border-radius:14px;padding:8px 14px;display:flex;justify-content:space-between;align-items:center;">
      <div style="display:flex;flex-direction:column;gap:2px;">
        <div style="font-size:11px;font-weight:800;display:flex;align-items:center;gap:6px;">
          <span style="color:var(--cyan);">KANTOR 3D REAL-TIME SYNCHRONIZED</span>
          <span id="office-status-pill" style="font-size:9px;padding:1px 6px;border-radius:6px;background:rgba(52,211,153,0.15);color:var(--emerald);border:1px solid var(--emerald);">CONNECTED</span>
        </div>
        <div id="office-subtext" style="font-size:10px;color:var(--muted);">9 Agen Pemimpin Siaga · Data bersumber langsung dari /api/state</div>
      </div>
      <button id="office-acc-btn" onclick="window.location.hash='#workflow';switchPage('workflow')" style="padding:6px 12px;border-radius:8px;font-size:10px;font-weight:700;cursor:pointer;border:none;background:var(--cyan);color:#040812;">📋 Buka Panel ACC</button>
    </div>
  </section>

""" + section_target

if section_target in content:
    content = content.replace(section_target, section_office_html, 1)
    print("Section page-office inserted successfully!")
else:
    print("WARNING: section_target not found!")

# 3. Masukkan Three.js CDN dan Modul MaruOffice3D terisolasi
three_script_block = """
<!-- Three.js + OrbitControls (Phase 1 3D Integration) -->
<script src="https://cdnjs.cloudflare.com/ajax/libs/three.js/r128/three.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/three@0.128.0/examples/js/controls/OrbitControls.js"></script>

<script>
// ================= MARU HQ 3D VIRTUAL OFFICE MODULE (PHASE 1) =================
(() => {
  let isInitialized = false;
  let scene, camera, renderer, controls;
  let cameraMode = 'iso';
  let targetFocus = new THREE.Vector3(0, 0, 0);
  const departments = [
    { id: "bima", name: "Executive HQ", leader: "Bima", role: "Chief Executive Intelligence", color: 0x1e1b4b, pillColor: "#818cf8", x: -22, z: -17, w: 14, d: 13, task: "Memimpin Strategi Agensi MARU" },
    { id: "hermes", name: "Kreatif & Naskah", leader: "Hermes", role: "Creative Director & Scriptwriter", color: 0x0369a1, pillColor: "#38bdf8", x: -7, z: -17, w: 14, d: 13, task: "Menyusun Naskah TikTok Hook 3 Detik" },
    { id: "nara", name: "Brainstorming & Tren", leader: "Nara", role: "Research Ideation Specialist", color: 0xb45309, pillColor: "#fbbf24", x: 8, z: -17, w: 14, d: 13, task: "Scraping Tren Isu Edukasi TikTok" },
    { id: "cendekia", name: "Research Library", leader: "Cendekia", role: "Chief Academic Researcher", color: 0x065f46, pillColor: "#34d399", x: 23, z: -17, w: 14, d: 13, task: "Validasi Teori Pengantar Komunikasi" },
    { id: "maus", name: "PR & Gerbang ACC", leader: "Maus", role: "Quality Gatekeeper", color: 0x831843, pillColor: "#ef4444", x: -22, z: -1, w: 14, d: 13, task: "Menunggu Keputusan ACC Pemilik HQ!" },
    { id: "kirana", name: "Video Production", leader: "Kirana", role: "Visual Production Director", color: 0x581c87, pillColor: "#c084fc", x: -7, z: -1, w: 14, d: 13, task: "Siap Muxing Timeline 9:16 Vertikal" },
    { id: "ardi", name: "Studio Dubbing", leader: "Ardi", role: "Voice Production Specialist", color: 0x111827, pillColor: "#38bdf8", x: 8, z: -1, w: 14, d: 13, task: "Standby di Meja Vokal Suara Muda" },
    { id: "wira", name: "IT Observability", leader: "Wira", role: "Chief Technical Operations", color: 0x083344, pillColor: "#06b6d4", x: 23, z: -1, w: 14, d: 13, task: "Monitoring Zero Downtime & Token Usage" },
    { id: "ootto", name: "TikTok Publisher", leader: "Ootto", role: "Social Media Distribution", color: 0xc2410c, pillColor: "#fb923c", x: -22, z: 15, w: 14, d: 13, task: "Menyiapkan Jalur Direct Post API" },
    { id: "canteen", name: "Kantin & Pantry", leader: "Shared", role: "Pantry & Dining Area", color: 0x1e293b, pillColor: "#94a3b8", x: -7, z: 15, w: 14, d: 13, task: "Area Istirahat & Coffee Break" },
    { id: "meeting", name: "Ruang Rapat Utama", leader: "Shared", role: "Conference Room", color: 0x0f172a, pillColor: "#a855f7", x: 8, z: 15, w: 14, d: 13, task: "Ruang Diskusi Tim & Presentasi" },
    { id: "lobby", name: "Lobby & Resepsionis", leader: "Shared", role: "Main Entrance", color: 0x1e293b, pillColor: "#f59e0b", x: 23, z: 15, w: 14, d: 13, task: "Penyambutan Tamu & Display Info" }
  ];

  function init3D() {
    if (isInitialized) return;
    const view = document.getElementById("office-3d-viewport");
    if (!view) return;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060913);
    scene.fog = new THREE.FogExp2(0x060913, 0.014);

    const w = view.clientWidth || window.innerWidth;
    const h = view.clientHeight || (window.innerHeight - 60);

    camera = new THREE.PerspectiveCamera(40, w / h, 1, 1000);
    camera.position.set(45, 50, 56);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    view.appendChild(renderer.domElement);

    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxPolarAngle = Math.PI / 2.15;
    controls.minDistance = 12;
    controls.maxDistance = 150;
    controls.target.set(0, 0, 0);

    const amb = new THREE.AmbientLight(0x334155, 1.6);
    scene.add(amb);
    const dir = new THREE.DirectionalLight(0xffffff, 1.8);
    dir.position.set(35, 70, 45);
    dir.castShadow = true;
    scene.add(dir);

    // Lantai Dasar Gedung
    const ground = new THREE.Mesh(new THREE.BoxGeometry(84, 0.4, 72), new THREE.MeshStandardMaterial({ color: 0x090d16, roughness: 0.5 }));
    ground.position.y = -0.4;
    ground.receiveShadow = true;
    scene.add(ground);

    // Denah Ruangan Phase 1 (Foundation Structure)
    departments.forEach(dept => {
      const grp = new THREE.Group();
      grp.position.set(dept.x, 0, dept.z);

      const fl = new THREE.Mesh(new THREE.BoxGeometry(dept.w, 0.2, dept.d), new THREE.MeshStandardMaterial({ color: dept.color, roughness: 0.5 }));
      fl.position.y = 0.1;
      fl.receiveShadow = true;
      grp.add(fl);

      const partMat = new THREE.MeshPhysicalMaterial({ color: 0xffffff, transparent: true, opacity: 0.15, transmission: 0.9 });
      const pB = new THREE.Mesh(new THREE.BoxGeometry(dept.w, 2.6, 0.1), partMat); pB.position.set(0, 1.3, -dept.d/2); grp.add(pB);
      const pL = new THREE.Mesh(new THREE.BoxGeometry(0.1, 2.6, dept.d), partMat); pL.position.set(-dept.w/2, 1.3, 0); grp.add(pL);

      const edge = new THREE.LineSegments(new THREE.EdgesGeometry(new THREE.BoxGeometry(dept.w, 0.2, dept.d)), new THREE.LineBasicMaterial({ color: 0xffffff, opacity: 0.35, transparent: true }));
      edge.position.y = 0.11;
      grp.add(edge);

      scene.add(grp);
    });

    renderPillTags();

    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      updatePillTags();
      renderer.render(scene, camera);
    }
    animate();

    window.addEventListener("resize", () => {
      if (!view) return;
      const nw = view.clientWidth || window.innerWidth;
      const nh = view.clientHeight || (window.innerHeight - 60);
      camera.aspect = nw / nh;
      camera.updateProjectionMatrix();
      renderer.setSize(nw, nh);
    });

    isInitialized = true;
    console.log("[MARU 3D] Office Module Phase 1 Initialized!");
  }

  function renderPillTags() {
    const cont = document.getElementById("office-overlay-container");
    if (!cont) return;
    cont.innerHTML = "";
    departments.forEach(d => {
      const tag = document.createElement("div");
      tag.className = "room-tag";
      tag.style.cssText = "position:absolute;transform:translate(-50%,-50%);background:rgba(15,23,42,0.92);backdrop-filter:blur(10px);border:1px solid rgba(255,255,255,0.18);border-radius:999px;padding:4px 10px;font-size:9px;font-weight:800;text-transform:uppercase;letter-spacing:0.5px;color:#fff;display:flex;align-items:center;gap:5px;cursor:pointer;pointer-events:auto;box-shadow:0 4px 15px rgba(0,0,0,0.6);";
      tag.innerHTML = `<span style="display:inline-block;width:7px;height:7px;border-radius:50%;background:${d.pillColor};"></span><span>${d.name}</span>`;
      tag.onclick = () => openInspector(d);
      cont.appendChild(tag);
      d.tagEl = tag;
    });
  }

  function updatePillTags() {
    if (!camera) return;
    const view = document.getElementById("office-3d-viewport");
    if (!view) return;
    const w = view.clientWidth || window.innerWidth;
    const h = view.clientHeight || (window.innerHeight - 60);

    departments.forEach(d => {
      if (!d.tagEl) return;
      const pos = new THREE.Vector3(d.x, 3.2, d.z);
      pos.project(camera);
      if (pos.z > 1) {
        d.tagEl.style.opacity = "0";
        return;
      }
      d.tagEl.style.opacity = "1";
      d.tagEl.style.left = `${(pos.x * 0.5 + 0.5) * w}px`;
      d.tagEl.style.top = `${(-(pos.y * 0.5) + 0.5) * h}px`;
    });
  }

  function openInspector(d) {
    document.getElementById("insp-badge").innerText = d.leader === "Shared" ? "FASILITAS BERSAMA" : "DEPARTEMEN RESMI";
    document.getElementById("insp-badge").style.background = d.pillColor;
    document.getElementById("insp-title").innerText = d.name;
    document.getElementById("insp-role").innerText = d.leader === "Shared" ? d.role : `Leader: ${d.leader} (${d.role})`;
    document.getElementById("insp-task").innerText = d.task;
    document.getElementById("office-inspector-panel").style.display = "block";
    targetFocus.set(d.x, 1, d.z);
  }

  window.MaruOffice3D = {
    init: init3D,
    setCameraMode: (mode) => {
      cameraMode = mode;
      document.getElementById("cam-iso-btn").style.background = mode === "iso" ? "var(--cyan)" : "transparent";
      document.getElementById("cam-iso-btn").style.color = mode === "iso" ? "#040812" : "var(--muted)";
      document.getElementById("cam-free-btn").style.background = mode === "free" ? "var(--cyan)" : "transparent";
      document.getElementById("cam-free-btn").style.color = mode === "free" ? "#040812" : "var(--muted)";
      if (mode === "iso" && controls && camera) {
        controls.target.set(0, 0, 0);
        camera.position.set(45, 50, 56);
        controls.enableRotate = false;
      } else if (controls) {
        controls.enableRotate = true;
      }
    },
    resetCamera: () => {
      if (controls && camera) {
        controls.target.set(0, 0, 0);
        camera.position.set(45, 50, 56);
      }
    },
    closeInspector: () => {
      document.getElementById("office-inspector-panel").style.display = "none";
    },
    focusSelected: () => {
      if (controls && camera) {
        controls.target.copy(targetFocus);
        camera.position.set(targetFocus.x + 12, targetFocus.y + 12, targetFocus.z + 14);
      }
      document.getElementById("office-inspector-panel").style.display = "none";
    },
    panCam: (dx, dy) => {
      if (controls && camera) {
        controls.target.y += dy * 0.4;
        camera.position.y += dy * 0.4;
      }
    },
    zoomCam: (factor) => {
      if (controls && camera) {
        camera.position.x = controls.target.x + (camera.position.x - controls.target.x) * factor;
        camera.position.y = controls.target.y + (camera.position.y - controls.target.y) * factor;
        camera.position.z = controls.target.z + (camera.position.z - controls.target.z) * factor;
      }
    },
    rotateCam: (rad) => {
      if (controls && camera) {
        const x = camera.position.x - controls.target.x;
        const z = camera.position.z - controls.target.z;
        camera.position.x = controls.target.x + x * Math.cos(rad) - z * Math.sin(rad);
        camera.position.z = controls.target.z + x * Math.sin(rad) + z * Math.cos(rad);
      }
    }
  };
})();
</script>
"""

# Sisipkan sebelum penutup </body>
content = content.replace("</body>", three_script_block + "\n</body>", 1)

# Hubungkan switchPage agar memanggil init3D saat membuka data-page="office"
switch_page_target = """function switchPage(page) {
    S.page = page;
    $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.page === page));
    $$(".page-view").forEach(sec => sec.classList.toggle("hidden", sec.id !== "page-" + page));
    document.body.classList.remove("nav-open");
    if (S.data) renderVideoList(S.data.episodes || []);
  }"""

switch_page_replacement = """function switchPage(page) {
    S.page = page;
    $$(".nav-btn").forEach(b => b.classList.toggle("active", b.dataset.page === page));
    $$(".page-view").forEach(sec => sec.classList.toggle("hidden", sec.id !== "page-" + page));
    document.body.classList.remove("nav-open");
    if (page === "office" && window.MaruOffice3D) {
      setTimeout(() => window.MaruOffice3D.init(), 50);
    }
    if (S.data) renderVideoList(S.data.episodes || []);
  }"""

if switch_page_target in content:
    content = content.replace(switch_page_target, switch_page_replacement, 1)
    print("switchPage hook connected successfully!")
else:
    print("WARNING: switch_page_target not found!")

with open('/home/user/studio_bulletproof.html', 'w', encoding='utf-8') as f:
    f.write(content)

print("Updated studio_bulletproof.html for Phase 1!")
