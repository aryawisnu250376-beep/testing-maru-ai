import re

with open('studio_bulletproof.html', 'r', encoding='utf-8') as f:
    html = f.read()

# Implementasi Lengkap Phase 3: Interior Furnishing & Room Decoration
new_phase3_module = """<script>
// ================= MARU HQ 3D VIRTUAL OFFICE MODULE (PHASE 3 - INTERIOR FURNISHING & DECORATION) =================
(() => {
  let isInitialized = false;
  let scene, camera, renderer, controls;
  let cameraMode = 'iso';
  let targetFocus = new THREE.Vector3(0, 0, 0);

  // 9 DEPARTEMEN RESMI + 5 FASILITAS BERSAMA (LENGKAP SPESIFIKASI INVENTARIS PERABOTAN)
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

    // ROW 4: FASILITAS TAMBAHAN (Z: 23)
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
    controls.maxPolarAngle = Math.PI / 2.15;
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

    const curbGeo = new THREE.BoxGeometry(67.5, 0.4, 63.5);
    const curbMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.8 });
    const curb = new THREE.Mesh(curbGeo, curbMat);
    curb.position.set(0, -0.2, 2);
    scene.add(curb);

    // Shared Reusable Materials Library
    const glassMat = new THREE.MeshPhysicalMaterial({ color: 0x38bdf8, transparent: true, opacity: 0.18, roughness: 0.1, transmission: 0.85, thickness: 0.3 });
    const solidWallMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.5 });
    const columnMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.3, metalness: 0.3 });
    const frameMat = new THREE.MeshStandardMaterial({ color: 0x475569, metalness: 0.6, roughness: 0.4 });
    const woodDeskMat = new THREE.MeshStandardMaterial({ color: 0x3b1d11, roughness: 0.4 });
    const modernDeskMat = new THREE.MeshStandardMaterial({ color: 0x1e293b, roughness: 0.3 });
    const chairMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.4 });
    const monitorBezelMat = new THREE.MeshStandardMaterial({ color: 0x020617, roughness: 0.2 });
    const screenCyanMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
    const screenRedMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });
    const screenGreenMat = new THREE.MeshBasicMaterial({ color: 0x22c55e });
    const plantPotMat = new THREE.MeshStandardMaterial({ color: 0x334155 });
    const plantLeafMat = new THREE.MeshStandardMaterial({ color: 0x10b981, roughness: 0.6 });

    // --- 2. REUSABLE PROCEDURAL BUILDER HELPERS ---
    function addDesk(parent, x, z, w = 2.4, d = 1.3, h = 0.9, mat = modernDeskMat) {
      const desk = new THREE.Mesh(new THREE.BoxGeometry(w, 0.1, d), mat);
      desk.position.set(x, h, z);
      parent.add(desk);

      // 4 Kaki Meja Logam
      const legMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, metalness: 0.6 });
      const legGeo = new THREE.CylinderGeometry(0.04, 0.04, h, 6);
      [[-w/2+0.15, -d/2+0.15], [w/2-0.15, -d/2+0.15], [-w/2+0.15, d/2-0.15], [w/2-0.15, d/2-0.15]].forEach(pt => {
        const leg = new THREE.Mesh(legGeo, legMat);
        leg.position.set(x + pt[0], h/2, z + pt[1]);
        parent.add(leg);
      });
      return desk;
    }

    function addChair(parent, x, z, color = 0x0f172a) {
      const cSeat = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.08, 0.7), new THREE.MeshStandardMaterial({ color }));
      cSeat.position.set(x, 0.5, z);
      parent.add(cSeat);
      const cBack = new THREE.Mesh(new THREE.BoxGeometry(0.7, 0.7, 0.08), new THREE.MeshStandardMaterial({ color }));
      cBack.position.set(x, 0.85, z + 0.31);
      parent.add(cBack);
      const cPole = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 0.5, 6), new THREE.MeshStandardMaterial({ color: 0x475569 }));
      cPole.position.set(x, 0.25, z);
      parent.add(cPole);
    }

    function addMonitor(parent, x, z, rotY = 0, screenColor = 0x38bdf8) {
      const monGrp = new THREE.Group();
      monGrp.position.set(x, 0.95, z);
      monGrp.rotation.y = rotY;
      const bz = new THREE.Mesh(new THREE.BoxGeometry(1.2, 0.7, 0.06), monitorBezelMat);
      bz.position.y = 0.45;
      monGrp.add(bz);
      const scr = new THREE.Mesh(new THREE.PlaneGeometry(1.12, 0.62), new THREE.MeshBasicMaterial({ color: screenColor }));
      scr.position.set(0, 0.45, 0.035);
      monGrp.add(scr);
      const stand = new THREE.Mesh(new THREE.BoxGeometry(0.1, 0.3, 0.05), monitorBezelMat);
      stand.position.y = 0.15;
      monGrp.add(stand);
      parent.add(monGrp);
    }

    function addPlant(parent, x, z) {
      const pot = new THREE.Mesh(new THREE.CylinderGeometry(0.35, 0.25, 0.7, 8), plantPotMat);
      pot.position.set(x, 0.35, z);
      parent.add(pot);
      const leaf = new THREE.Mesh(new THREE.DodecahedronGeometry(0.65), plantLeafMat);
      leaf.position.set(x, 0.95, z);
      parent.add(leaf);
    }

    // --- 3. ARCHITECTURAL ROOMS & DEPARTMENT-SPECIFIC INTERIOR ---
    departments.forEach(dept => {
      const grp = new THREE.Group();
      grp.position.set(dept.x, 0, dept.z);

      // A. Lantai Ruangan
      const fl = new THREE.Mesh(new THREE.BoxGeometry(dept.w, 0.12, dept.d), new THREE.MeshStandardMaterial({ color: dept.color, roughness: 0.5 }));
      fl.position.y = 0.06;
      fl.receiveShadow = true;
      grp.add(fl);

      // B. Dinding Partisi Kaca & Kolom Sudut Cutaway
      const hWall = 3.2;
      const wallBack = new THREE.Mesh(new THREE.BoxGeometry(dept.w, hWall, 0.16), glassMat);
      wallBack.position.set(0, hWall / 2, -dept.d / 2);
      grp.add(wallBack);

      const wallLeft = new THREE.Mesh(new THREE.BoxGeometry(0.16, hWall, dept.d), glassMat);
      wallLeft.position.set(-dept.w / 2, hWall / 2, 0);
      grp.add(wallLeft);

      // Kolom Struktural
      const colGeo = new THREE.BoxGeometry(0.4, hWall, 0.4);
      [[-dept.w/2, -dept.d/2], [dept.w/2, -dept.d/2], [-dept.w/2, dept.d/2]].forEach(pt => {
        const col = new THREE.Mesh(colGeo, columnMat);
        col.position.set(pt[0], hWall / 2, pt[1]);
        grp.add(col);
      });

      // Partial Ceiling Lintel
      const lintel = new THREE.Mesh(new THREE.BoxGeometry(dept.w * 0.35, 0.15, dept.d * 0.35), solidWallMat);
      lintel.position.set(-dept.w * 0.3, hWall + 0.08, -dept.d * 0.3);
      grp.add(lintel);

      // Neon Floor Border Base
      const edge = new THREE.LineSegments(
        new THREE.EdgesGeometry(new THREE.BoxGeometry(dept.w, 0.12, dept.d)),
        new THREE.LineBasicMaterial({ color: 0xffffff, opacity: 0.3, transparent: true })
      );
      edge.position.y = 0.07;
      grp.add(edge);

      // ================= C. INTERIOR INVENTARIS LENGKAP TIAP RUANGAN =================
      if (dept.id === "bima") {
        // 1. EXECUTIVE HQ (BIMA): Meja kayu jati besar, kursi eksekutif, lemari arsip, wall KPI display
        addDesk(grp, 0, -2, 4.2, 2.0, 0.95, woodDeskMat);
        addChair(grp, 0, -3.2, 0x1e1b4b);
        addMonitor(grp, -0.9, -2.1, 0.2, 0x818cf8);
        addMonitor(grp, 0.9, -2.1, -0.2, 0x38bdf8);
        // Lemari Arsip Eksekutif
        const cab = new THREE.Mesh(new THREE.BoxGeometry(3.5, 2.4, 0.8), new THREE.MeshStandardMaterial({ color: 0x311005 }));
        cab.position.set(-dept.w / 2 + 1.2, 1.2, -dept.d / 2 + 1.0);
        grp.add(cab);
        // Kursi Tamu & Tanaman
        addChair(grp, -1.2, -0.6, 0x334155);
        addChair(grp, 1.2, -0.6, 0x334155);
        addPlant(grp, dept.w / 2 - 1.2, -dept.d / 2 + 1.2);

      } else if (dept.id === "hermes") {
        // 2. CREATIVE & SCRIPTWRITING (HERMES): Meja naskah ganda, dual monitor, papan ide, sticky notes
        addDesk(grp, -2.5, -1.5, 3.2, 1.5, 0.9);
        addChair(grp, -2.5, -2.5);
        addMonitor(grp, -3.2, -1.7, 0.15, 0x38bdf8);
        addMonitor(grp, -1.8, -1.7, -0.15, 0x38bdf8);
        // Papan Mood Board / Ide Naskah
        const board = new THREE.Mesh(new THREE.BoxGeometry(3.6, 1.8, 0.08), new THREE.MeshStandardMaterial({ color: 0x334155 }));
        board.position.set(0, 1.8, -dept.d / 2 + 0.15);
        grp.add(board);
        addDesk(grp, 2.5, 1.5, 2.8, 1.3, 0.9);
        addChair(grp, 2.5, 0.6);
        addMonitor(grp, 2.5, 1.3, 0, 0x38bdf8);

      } else if (dept.id === "nara") {
        // 3. BRAINSTORMING & TRENDS (NARA): Meja diskusi bundar besar, 4 kursi keliling, layar tren viral
        const bTable = new THREE.Mesh(new THREE.CylinderGeometry(2.4, 2.4, 0.85, 16), new THREE.MeshStandardMaterial({ color: 0x451a03 }));
        bTable.position.set(0, 0.45, 0);
        grp.add(bTable);
        [[0, -3.2], [0, 3.2], [-3.2, 0], [3.2, 0]].forEach(pos => addChair(grp, pos[0], pos[1], 0xb45309));
        // Layar Monitoring Tren Viral Besar di Dinding
        const tv = new THREE.Mesh(new THREE.BoxGeometry(4.2, 2.0, 0.1), monitorBezelMat);
        tv.position.set(0, 2.0, -dept.d / 2 + 0.15);
        grp.add(tv);
        const tvScr = new THREE.Mesh(new THREE.PlaneGeometry(4.0, 1.8), new THREE.MeshBasicMaterial({ color: 0xfbbf24 }));
        tvScr.position.set(0, 2.0, -dept.d / 2 + 0.22);
        grp.add(tvScr);

      } else if (dept.id === "cendekia") {
        // 4. ACADEMIC RESEARCH LIBRARY (CENDEKIA): 3 Rak buku kayu tinggi penuh jurnal, meja riset baca
        for (let i = 0; i < 3; i++) {
          const shelf = new THREE.Mesh(new THREE.BoxGeometry(0.7, 3.0, 4.6), new THREE.MeshStandardMaterial({ color: 0x451a03 }));
          shelf.position.set(-dept.w / 2 + 1.2 + i * 2.4, 1.5, -dept.d / 2 + 2.8);
          grp.add(shelf);
        }
        addDesk(grp, 2.2, 1.2, 3.2, 1.4, 0.9, woodDeskMat);
        addChair(grp, 2.2, 0.2, 0x065f46);
        addMonitor(grp, 2.2, 1.0, 0, 0x34d399);
        addPlant(grp, dept.w / 2 - 1.2, dept.d / 2 - 1.2);

      } else if (dept.id === "maus") {
        // 5. PR & APPROVAL GATE (MAUS): Workstation audit, lampu indikator status ACC merah/hijau, layar antrean
        addDesk(grp, 0, -1.0, 3.4, 1.6, 0.9);
        addChair(grp, 0, -2.1, 0x831843);
        addMonitor(grp, -0.8, -1.2, 0.1, 0xef4444);
        addMonitor(grp, 0.8, -1.2, -0.1, 0x22c55e);
        // Indikator Status ACC Besar
        const accSign = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.6, 0.1), monitorBezelMat);
        accSign.position.set(0, 2.6, -dept.d / 2 + 0.15);
        grp.add(accSign);
        const accLight = new THREE.Mesh(new THREE.PlaneGeometry(2.2, 0.45), new THREE.MeshBasicMaterial({ color: 0xef4444 }));
        accLight.position.set(0, 2.6, -dept.d / 2 + 0.22);
        grp.add(accLight);

      } else if (dept.id === "kirana") {
        // 6. VIDEO PRODUCTION (KIRANA): Dual-monitor setup video editing, playback screen, lighting rig
        addDesk(grp, -1.5, -1.2, 3.6, 1.6, 0.9);
        addChair(grp, -1.5, -2.2, 0x581c87);
        addMonitor(grp, -2.3, -1.4, 0.12, 0xc084fc);
        addMonitor(grp, -0.7, -1.4, -0.12, 0x38bdf8);
        // Lampu Softbox Studio Video
        const sbPole = new THREE.Mesh(new THREE.CylinderGeometry(0.04, 0.04, 2.4, 6), frameMat);
        sbPole.position.set(3.2, 1.2, 1.5);
        grp.add(sbPole);
        const sbHead = new THREE.Mesh(new THREE.BoxGeometry(0.8, 1.0, 0.4), new THREE.MeshStandardMaterial({ color: 0xffffff }));
        sbHead.position.set(3.2, 2.4, 1.5);
        grp.add(sbHead);

      } else if (dept.id === "ardi") {
        // 7. VOICE PRODUCTION STUDIO (ARDI): Booth vokal isolasi, stand mic rekaman kondensor, lampu ON-AIR
        const micP = new THREE.Mesh(new THREE.CylinderGeometry(0.05, 0.05, 2.2, 6), frameMat);
        micP.position.set(0, 1.1, 1.2);
        grp.add(micP);
        const micH = new THREE.Mesh(new THREE.SphereGeometry(0.2, 8, 8), new THREE.MeshBasicMaterial({ color: 0x38bdf8 }));
        micH.position.set(0, 2.2, 1.2);
        grp.add(micH);
        // Meja Audio Mixer / Controller
        addDesk(grp, 0, -2.0, 3.2, 1.4, 0.9);
        addChair(grp, 0, -3.0, 0x111827);
        addMonitor(grp, 0, -2.2, 0, 0x38bdf8);
        // Lampu ON-AIR Merah
        const onAir = new THREE.Mesh(new THREE.BoxGeometry(2.4, 0.6, 0.15), new THREE.MeshBasicMaterial({ color: 0xef4444 }));
        onAir.position.set(0, 3.0, -dept.d / 2 + 0.15);
        grp.add(onAir);

      } else if (dept.id === "wira") {
        // 8. IT OBSERVABILITY (WIRA): 2 Rack server tinggi dengan LED indikator, meja technical dashboard
        for (let i = 0; i < 2; i++) {
          const rack = new THREE.Mesh(new THREE.BoxGeometry(1.6, 2.8, 1.1), new THREE.MeshStandardMaterial({ color: 0x020617 }));
          rack.position.set(-dept.w / 2 + 1.8 + i * 2.4, 1.4, -dept.d / 2 + 1.6);
          grp.add(rack);
          const led = new THREE.Mesh(new THREE.PlaneGeometry(1.4, 0.2), screenGreenMat);
          led.position.set(-dept.w / 2 + 1.8 + i * 2.4, 2.3, -dept.d / 2 + 2.18);
          grp.add(led);
        }
        addDesk(grp, 1.8, 0.8, 2.8, 1.4, 0.9);
        addChair(grp, 1.8, -0.2, 0x083344);
        addMonitor(grp, 1.8, 0.6, 0, 0x06b6d4);

      } else if (dept.id === "ootto") {
        // 9. TIKTOK PUBLISHER (OOTTO): Workstation publishing, layar analytics performa, kalender jadwal
        addDesk(grp, 0, -1.0, 3.2, 1.4, 0.9);
        addChair(grp, 0, -2.0, 0xc2410c);
        addMonitor(grp, -0.8, -1.2, 0.15, 0xfb923c);
        addMonitor(grp, 0.8, -1.2, -0.15, 0x38bdf8);
        // Papan Kalender Distribusi Konten
        const cal = new THREE.Mesh(new THREE.BoxGeometry(3.2, 1.6, 0.08), new THREE.MeshStandardMaterial({ color: 0x334155 }));
        cal.position.set(0, 2.0, -dept.d / 2 + 0.15);
        grp.add(cal);

      } else if (dept.id === "canteen") {
        // 10. CANTEEN & PANTRY: Meja makan panjang, kursi makan, konter bar kopi, mesin espresso
        addDesk(grp, 0, -1.0, 4.4, 1.8, 0.85, modernDeskMat);
        [[-1.4, -2.2], [0, -2.2], [1.4, -2.2], [-1.4, 0.2], [0, 0.2], [1.4, 0.2]].forEach(pt => addChair(grp, pt[0], pt[1], 0x334155));
        // Konter Kopi / Pantry
        const bar = new THREE.Mesh(new THREE.BoxGeometry(3.6, 1.1, 0.9), new THREE.MeshStandardMaterial({ color: 0x1e293b }));
        bar.position.set(0, 0.55, 3.5);
        grp.add(bar);
        const esp = new THREE.Mesh(new THREE.BoxGeometry(0.6, 0.6, 0.6), new THREE.MeshStandardMaterial({ color: 0xef4444 }));
        esp.position.set(-0.8, 1.4, 3.5);
        grp.add(esp);

      } else if (dept.id === "meeting") {
        // 11. MEETING ROOM: Meja rapat besar elips/panjang, 6 kursi konferensi, layar presentasi
        const conf = new THREE.Mesh(new THREE.BoxGeometry(5.2, 0.85, 2.2), woodDeskMat);
        conf.position.set(0, 0.45, 0);
        grp.add(conf);
        [[-1.6, -1.6], [0, -1.6], [1.6, -1.6], [-1.6, 1.6], [0, 1.6], [1.6, 1.6]].forEach(pt => addChair(grp, pt[0], pt[1], 0x0f172a));
        // Layar Presentasi Rapat
        const pr = new THREE.Mesh(new THREE.BoxGeometry(4.0, 1.8, 0.08), monitorBezelMat);
        pr.position.set(0, 2.2, -dept.d / 2 + 0.15);
        grp.add(pr);
        const prScr = new THREE.Mesh(new THREE.PlaneGeometry(3.8, 1.6), screenCyanMat);
        prScr.position.set(0, 2.2, -dept.d / 2 + 0.22);
        grp.add(prScr);

      } else if (dept.id === "lobby") {
        // 12. RECEPTION & LOBBY: Meja resepsionis melengkung, sofa tunggu tamu, standing info display
        const rec = new THREE.Mesh(new THREE.BoxGeometry(3.6, 1.2, 1.2), new THREE.MeshStandardMaterial({ color: 0x0f172a }));
        rec.position.set(0, 0.6, -1.5);
        grp.add(rec);
        // Sofa Tamu
        const sf = new THREE.Mesh(new THREE.BoxGeometry(3.2, 0.6, 1.2), new THREE.MeshStandardMaterial({ color: 0x334155 }));
        sf.position.set(0, 0.3, 2.8);
        grp.add(sf);
        addPlant(grp, -dept.w / 2 + 1.2, dept.d / 2 - 1.2);
        addPlant(grp, dept.w / 2 - 1.2, dept.d / 2 - 1.2);

      } else if (dept.id === "mushola") {
        // 13. MUSHOLA & PRAYER ROOM: Karpet sajadah saf hijau, rak sandal, tempat wudhu / batas suci
        for (let i = 0; i < 2; i++) {
          const saj = new THREE.Mesh(new THREE.PlaneGeometry(8.0, 1.6), new THREE.MeshStandardMaterial({ color: 0x065f46 }));
          saj.rotation.x = -Math.PI / 2;
          saj.position.set(0, 0.08, -1.2 + i * 2.2);
          grp.add(saj);
        }

      } else if (dept.id === "lounge") {
        // 14. LOUNGE & REST AREA: Kursi santai empuk, meja kopi kaca, rak majalah
        const lSofa = new THREE.Mesh(new THREE.BoxGeometry(3.4, 0.6, 1.4), new THREE.MeshStandardMaterial({ color: 0x374151 }));
        lSofa.position.set(0, 0.3, -0.8);
        grp.add(lSofa);
        const lTable = new THREE.Mesh(new THREE.BoxGeometry(2.0, 0.4, 1.0), glassMat);
        lTable.position.set(0, 0.2, 1.2);
        grp.add(lTable);
        addPlant(grp, dept.w / 2 - 1.2, -dept.d / 2 + 1.2);
      }

      scene.add(grp);
    });

    // --- 4. CORRIDORS & CROSS WALKWAYS ---
    const walkHMat = new THREE.MeshStandardMaterial({ color: 0x0f172a, roughness: 0.4 });
    const walkH = new THREE.Mesh(new THREE.BoxGeometry(64, 0.08, 3.0), walkHMat); walkH.position.set(0, 0.04, -9.5); scene.add(walkH);
    const walkH2 = new THREE.Mesh(new THREE.BoxGeometry(64, 0.08, 3.0), walkHMat); walkH2.position.set(0, 0.04, 5.5); scene.add(walkH2);
    const walkV = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.08, 60), walkHMat); walkV.position.set(0, 0.04, 2); scene.add(walkV);

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
    console.log("[MARU 3D] Interior Furnishing Phase 3 Initialized Successfully!");
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
      const pos = new THREE.Vector3(d.x, 3.6, d.z);
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

# Cari dan ganti blok script Phase 2 menjadi Phase 3
pattern = r'<script>\s*\/\/\s*={5,}\s*MARU HQ 3D VIRTUAL OFFICE MODULE.*?<\/script>'
m = re.search(pattern, html, re.DOTALL)
if m:
    html = html[:m.start()] + new_phase3_module + html[m.end():]
    with open('studio_bulletproof.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("Phase 3 Interior Furnishing integrated successfully into studio_bulletproof.html!")
else:
    print("WARNING: Script pattern not found, trying fallback...")
    idx = html.find('// ================= MARU HQ 3D VIRTUAL OFFICE MODULE')
    if idx != -1:
        start_script = html.rfind('<script>', 0, idx)
        end_script = html.find('</script>', idx) + 9
        html = html[:start_script] + new_phase3_module + html[end_script:]
        with open('studio_bulletproof.html', 'w', encoding='utf-8') as f:
            f.write(html)
        print("Fallback replacement succeeded!")
    else:
        print("Error: Could not locate 3D script block!")
