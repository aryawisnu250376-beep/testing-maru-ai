import re

with open('studio_bulletproof.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Kita perbarui modul Window.MaruOffice3D dengan implementasi arsitektur cutaway gedung Phase 2 yang kokoh
old_module_target = """<script>
// ================= MARU HQ 3D VIRTUAL OFFICE MODULE (PHASE 1) =================
(() => {"""

new_phase2_module = """<script>
// ================= MARU HQ 3D VIRTUAL OFFICE MODULE (PHASE 2 - BUILDING ARCHITECTURE) =================
(() => {
  let isInitialized = false;
  let scene, camera, renderer, controls;
  let cameraMode = 'iso';
  let targetFocus = new THREE.Vector3(0, 0, 0);

  // 9 DEPARTEMEN RESMI + 5 FASILITAS BERSAMA (KOORDINAT ARSITEKTURAL PRESISI)
  const departments = [
    // ROW 1: EKSEKUTIF & RISET UTAMA (Z: -17)
    { id: "bima", name: "Executive HQ", leader: "Bima", role: "Chief Executive Intelligence", color: 0x1e1b4b, pillColor: "#818cf8", x: -22, z: -17, w: 13, d: 12, floorType: "carpet_navy", task: "Memimpin Strategi Agensi MARU" },
    { id: "hermes", name: "Creative & Scriptwriting", leader: "Hermes", role: "Creative Director & Scriptwriter", color: 0x0369a1, pillColor: "#38bdf8", x: -7.5, z: -17, w: 13, d: 12, floorType: "carpet_blue", task: "Menyusun Naskah TikTok Hook 3 Detik" },
    { id: "nara", name: "Brainstorming & Trends", leader: "Nara", role: "Research Ideation Specialist", color: 0xb45309, pillColor: "#fbbf24", x: 7.5, z: -17, w: 13, d: 12, floorType: "carpet_amber", task: "Scraping Tren Isu Edukasi TikTok" },
    { id: "cendekia", name: "Academic Research Library", leader: "Cendekia", role: "Chief Academic Researcher", color: 0x065f46, pillColor: "#34d399", x: 22, z: -17, w: 13, d: 12, floorType: "wood_parquet", task: "Validasi Teori Pengantar Komunikasi" },

    // ROW 2: PRODUKSI, GERBANG ACC & IT (Z: -2)
    { id: "maus", name: "PR & Approval Gate", leader: "Maus", role: "Quality Gatekeeper", color: 0x831843, pillColor: "#ef4444", x: -22, z: -2, w: 13, d: 12, floorType: "carpet_wine", task: "Menunggu Keputusan ACC Pemilik HQ!" },
    { id: "kirana", name: "Video Production", leader: "Kirana", role: "Visual Production Director", color: 0x581c87, pillColor: "#c084fc", x: -7.5, z: -2, w: 13, d: 12, floorType: "carpet_purple", task: "Muxing Timeline Video 9:16 Vertikal" },
    { id: "ardi", name: "Voice Production Studio", leader: "Ardi", role: "Voice Production Specialist", color: 0x111827, pillColor: "#38bdf8", x: 7.5, z: -2, w: 13, d: 12, floorType: "acoustic_dark", task: "Standby di Meja Vokal Suara Muda" },
    { id: "wira", name: "IT Observability", leader: "Wira", role: "Chief Technical Operations", color: 0x083344, pillColor: "#06b6d4", x: 22, z: -2, w: 13, d: 12, floorType: "server_tile", task: "Monitoring Zero Downtime & Token Usage" },

    // ROW 3: DISTRIBUSI & FASILITAS BERSAMA (Z: 13)
    { id: "ootto", name: "TikTok Publisher", leader: "Ootto", role: "Social Media Distribution", color: 0xc2410c, pillColor: "#fb923c", x: -22, z: 13, w: 13, d: 12, floorType: "carpet_orange", task: "Menyiapkan Jalur Direct Post API" },
    { id: "canteen", name: "Canteen & Pantry", leader: "Shared", role: "Pantry & Dining Area", color: 0x1e293b, pillColor: "#94a3b8", x: -7.5, z: 13, w: 13, d: 12, floorType: "tile_ceramic", task: "Area Istirahat, Kopi & Makan" },
    { id: "meeting", name: "Meeting Room", leader: "Shared", role: "Conference Room", color: 0x0f172a, pillColor: "#a855f7", x: 7.5, z: 13, w: 13, d: 12, floorType: "carpet_navy", task: "Ruang Diskusi & Presentasi" },
    { id: "lobby", name: "Reception & Main Entrance", leader: "Shared", role: "Main Entrance", color: 0x1e293b, pillColor: "#f59e0b", x: 22, z: 13, w: 13, d: 12, floorType: "marble_bright", task: "Penyambutan Tamu & Display Info" },

    // FASILITAS TAMBAHAN: MUSHOLA & PRAYER ROOM (Z: 24)
    { id: "mushola", name: "Mushola & Prayer Room", leader: "Shared", role: "Quiet Prayer Area", color: 0x064e3b, pillColor: "#10b981", x: -7.5, z: 23, w: 13, d: 6, floorType: "prayer_green", task: "Tempat Ibadah & Refleksi Tenang" },
    { id: "lounge", name: "Lounge & Rest Area", leader: "Shared", role: "Relaxation Space", color: 0x1f2937, pillColor: "#f472b6", x: 7.5, z: 23, w: 13, d: 6, floorType: "lounge_wood", task: "Area Istirahat Tenang" }
  ];

  function init3D() {
    if (isInitialized) return;
    const view = document.getElementById("office-3d-viewport");
    if (!view) return;

    scene = new THREE.Scene();
    scene.background = new THREE.Color(0x060913);
    scene.fog = new THREE.FogExp2(0x060913, 0.012);

    const w = view.clientWidth || window.innerWidth;
    const h = view.clientHeight || (window.innerHeight - 60);

    camera = new THREE.PerspectiveCamera(38, w / h, 1, 1000);
    camera.position.set(48, 52, 60);

    renderer = new THREE.WebGLRenderer({ antialias: true, alpha: true });
    renderer.setSize(w, h);
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.shadowMap.enabled = true;
    renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    view.appendChild(renderer.domElement);

    controls = new THREE.OrbitControls(camera, renderer.domElement);
    controls.enableDamping = true;
    controls.dampingFactor = 0.08;
    controls.maxPolarAngle = Math.PI / 2.15; // Mencegah kamera tembus lantai
    controls.minDistance = 14;
    controls.maxDistance = 160;
    controls.target.set(0, 0, 0);

    // Pencahayaan Arsitektural Profesional
    const amb = new THREE.AmbientLight(0x334155, 1.5);
    scene.add(amb);
    const dir = new THREE.DirectionalLight(0xffffff, 1.8);
    dir.position.set(40, 75, 50);
    dir.castShadow = true;
    dir.shadow.mapSize.width = 2048;
    dir.shadow.mapSize.height = 2048;
    scene.add(dir);

    // Warm Ambient Interior Fill Light
    const fillLight = new THREE.DirectionalLight(0x93c5fd, 0.6);
    fillLight.position.set(-30, 40, -30);
    scene.add(fillLight);

    // --- 1. BUILDING FOUNDATION & SLAB ---
    const slabGeo = new THREE.BoxGeometry(66, 0.6, 62);
    const slabMat = new THREE.MeshStandardMaterial({ color: 0x090d16, roughness: 0.6, metalness: 0.2 });
    const mainSlab = new THREE.Mesh(slabGeo, slabMat);
    mainSlab.position.set(0, -0.3, 2);
    mainSlab.receiveShadow = true;
    scene.add(mainSlab);

    // Outer Perimeter Concrete Curb
    const curbGeo = new THREE.BoxGeometry(67.5, 0.4, 63.5);
    const curbMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.8 });
    const curb = new THREE.Mesh(curbGeo, curbMat);
    curb.position.set(0, -0.2, 2);
    scene.add(curb);

    // Materials Library Terstandarisasi
    const glassMat = new THREE.MeshPhysicalMaterial({
      color: 0x38bdf8,
      transparent: true,
      opacity: 0.18,
      roughness: 0.1,
      transmission: 0.85,
      thickness: 0.3
    });
    const solidWallMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.5 });
    const columnMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.3, metalness: 0.3 });
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.6, roughness: 0.4 });

    // --- 2. ARCHITECTURAL CUTAWAY BUILDING STRUCTURE ---
    // Helper Bangun Ruangan Cutaway
    departments.forEach(dept => {
      const grp = new THREE.Group();
      grp.position.set(dept.x, 0, dept.z);

      // A. Lantai Ruangan
      const flGeo = new THREE.BoxGeometry(dept.w, 0.12, dept.d);
      const flMat = new THREE.MeshStandardMaterial({ color: dept.color, roughness: 0.5 });
      const fl = new THREE.Mesh(flGeo, flMat);
      fl.position.y = 0.06;
      fl.receiveShadow = true;
      grp.add(fl);

      // B. Architectural Glass Partition (Dinding Belakang & Samping Kiri)
      const hWall = 3.2;
      const wallBackGeo = new THREE.BoxGeometry(dept.w, hWall, 0.16);
      const wallBack = new THREE.Mesh(wallBackGeo, glassMat);
      wallBack.position.set(0, hWall / 2, -dept.d / 2);
      grp.add(wallBack);

      const wallLeftGeo = new THREE.BoxGeometry(0.16, hWall, dept.d);
      const wallLeft = new THREE.Mesh(wallLeftGeo, glassMat);
      wallLeft.position.set(-dept.w / 2, hWall / 2, 0);
      grp.add(wallLeft);

      // C. Kusen Pintu & Frame Baja Minimalis
      const topBeamGeo = new THREE.BoxGeometry(dept.w, 0.12, 0.2);
      const topBeam = new THREE.Mesh(topBeamGeo, frameMat);
      topBeam.position.set(0, hWall, -dept.d / 2);
      grp.add(topBeam);

      const sideBeamGeo = new THREE.BoxGeometry(0.2, 0.12, dept.d);
      const sideBeam = new THREE.Mesh(sideBeamGeo, frameMat);
      sideBeam.position.set(-dept.w / 2, hWall, 0);
      grp.add(sideBeam);

      // D. Kolom Struktural di Tiap Sudut Ruangan
      const colGeo = new THREE.BoxGeometry(0.4, hWall, 0.4);
      const col1 = new THREE.Mesh(colGeo, columnMat); col1.position.set(-dept.w / 2, hWall / 2, -dept.d / 2); grp.add(col1);
      const col2 = new THREE.Mesh(colGeo, columnMat); col2.position.set(dept.w / 2, hWall / 2, -dept.d / 2); grp.add(col2);
      const col3 = new THREE.Mesh(colGeo, columnMat); col3.position.set(-dept.w / 2, hWall / 2, dept.d / 2); grp.add(col3);

      // E. Cutaway Open-Front / Entrance Cutaway (Pintu Terbuka 2.0m)
      const doorFrameGeo = new THREE.BoxGeometry(0.15, 2.4, 0.15);
      const doorPost = new THREE.Mesh(doorFrameGeo, frameMat);
      doorPost.position.set(dept.w / 2 - 2.2, 1.2, dept.d / 2);
      grp.add(doorPost);

      // F. Partial Ceiling Lintel (Kanopi Elegan Menandakan Atap Cutaway)
      const lintelGeo = new THREE.BoxGeometry(dept.w * 0.35, 0.15, dept.d * 0.35);
      const lintel = new THREE.Mesh(lintelGeo, solidWallMat);
      lintel.position.set(-dept.w * 0.3, hWall + 0.08, -dept.d * 0.3);
      grp.add(lintel);

      // G. Neon Floor Border Base
      const edge = new THREE.LineSegments(
        new THREE.EdgesGeometry(flGeo),
        new THREE.LineBasicMaterial({ color: 0xffffff, opacity: 0.3, transparent: true })
      );
      edge.position.y = 0.07;
      grp.add(edge);

      scene.add(grp);
    });

    // --- 3. CORRIDORS, WALKWAYS & MAIN ENTRANCE HALL ---
    // Koridor Penghubung Utama (Cross Walkway)
    const walkHMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.4 });
    const walkH = new THREE.Mesh(new THREE.BoxGeometry(64, 0.08, 3.0), walkHMat);
    walkH.position.set(0, 0.04, -9.5);
    scene.add(walkH);

    const walkH2 = new THREE.Mesh(new THREE.BoxGeometry(64, 0.08, 3.0), walkHMat);
    walkH2.position.set(0, 0.04, 5.5);
    scene.add(walkH2);

    const walkV = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.08, 60), walkHMat);
    walkV.position.set(0, 0.04, 2);
    scene.add(walkV);

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
    console.log("[MARU 3D] Building Architecture Phase 2 Initialized Successfully!");
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
      const pos = new THREE.Vector3(d.x, 3.5, d.z);
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
        camera.position.set(48, 52, 60);
        controls.enableRotate = false;
      } else if (controls) {
        controls.enableRotate = true;
      }
    },
    resetCamera: () => {
      if (controls && camera) {
        controls.target.set(0, 0, 0);
        camera.position.set(48, 52, 60);
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

# Cari blok script office lama dan gantikan dengan modul Phase 2
pattern = r'<script>\s*\/\/\s*={5,}\s*MARU HQ 3D VIRTUAL OFFICE MODULE.*?<\/script>'
m = re.search(pattern, html, re.DOTALL)
if m:
    html = html[:m.start()] + new_phase2_module + html[m.end():]
    with open('studio_bulletproof.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Phase 2 Building Architecture integrated into studio_bulletproof.html successfully!")
else:
    print("WARNING: Pattern not matched! Replacing by fallback...")
    # fallback
    idx = html.find('// ================= MARU HQ 3D VIRTUAL OFFICE MODULE')
    if idx != -1:
        start_script = html.rfind('<script>', 0, idx)
        end_script = html.find('</script>', idx) + 9
        html = html[:start_script] + new_phase2_module + html[end_script:]
        with open('studio_bulletproof.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Fallback replacement succeeded!")
    else:
        print("Error: Could not locate 3D script block!")
