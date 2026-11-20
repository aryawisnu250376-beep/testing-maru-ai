import sys

def patch_phase4():
    with open('studio_bulletproof.html', 'r', encoding='utf-8') as f:
        html = f.read()

    # 1. Update Inspector Panel HTML to support tabs/sections for Employee vs Department
    old_panel = '''      <div style="background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;font-size:11px;border:1px solid rgba(255,255,255,0.08);margin-bottom:8px;">
        <div style="color:var(--muted);margin-bottom:2px;">Status Operasional:</div>
        <div id="insp-status" style="font-weight:700;color:var(--emerald);">100% ONLINE / RUNNING</div>
      </div>
      <div style="background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;font-size:11px;border:1px solid rgba(255,255,255,0.08);margin-bottom:12px;">
        <div style="color:var(--muted);margin-bottom:2px;">Tugas Saat Ini:</div>
        <div id="insp-task" style="color:var(--text);font-weight:500;">Memimpin Visi Media & Konten MARU HQ</div>
      </div>
      <button onclick="window.MaruOffice3D.focusSelected()" style="width:100%;background:rgba(56,189,248,0.15);border:1px solid var(--cyan);color:var(--cyan);font-weight:800;font-size:11px;padding:8px;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;">
        <span>🔍</span><span>Fokus Kamera ke Ruangan</span>
      </button>'''

    new_panel = '''      <div id="insp-meta-row" style="display:flex;gap:6px;margin-bottom:8px;">
        <div style="flex:1;background:rgba(0,0,0,0.3);border-radius:8px;padding:6px 8px;font-size:10px;border:1px solid rgba(255,255,255,0.08);">
          <div style="color:var(--muted);font-size:9px;">TIPE ENTITAS</div>
          <div id="insp-type" style="font-weight:700;color:#fff;">DEPARTEMEN</div>
        </div>
        <div style="flex:1;background:rgba(0,0,0,0.3);border-radius:8px;padding:6px 8px;font-size:10px;border:1px solid rgba(255,255,255,0.08);">
          <div style="color:var(--muted);font-size:9px;">WORKSTATION</div>
          <div id="insp-workstation" style="font-weight:700;color:var(--cyan);">Executive Desk #1</div>
        </div>
      </div>
      <div style="background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;font-size:11px;border:1px solid rgba(255,255,255,0.08);margin-bottom:8px;">
        <div style="color:var(--muted);margin-bottom:2px;">Status Operasional:</div>
        <div id="insp-status" style="font-weight:700;color:var(--emerald);">100% ONLINE / STANDBY</div>
      </div>
      <div style="background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;font-size:11px;border:1px solid rgba(255,255,255,0.08);margin-bottom:12px;">
        <div style="color:var(--muted);margin-bottom:2px;">Tugas & Aktivitas:</div>
        <div id="insp-task" style="color:var(--text);font-weight:500;">Memimpin Visi Media & Konten MARU HQ</div>
      </div>
      <button onclick="window.MaruOffice3D.focusSelected()" style="width:100%;background:rgba(56,189,248,0.15);border:1px solid var(--cyan);color:var(--cyan);font-weight:800;font-size:11px;padding:8px;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;">
        <span>🔍</span><span id="insp-focus-btn-text">Fokus Kamera ke Target</span>
      </button>'''

    if old_panel in html:
        html = html.replace(old_panel, new_panel)
        print("[SUCCESS] Inspector Panel UI updated to support both Employees and Departments!")
    else:
        print("[WARNING] Could not find exact old_panel, checking if already patched...")

    # 2. Add Character Population Logic, Click Raycaster, Employee Roster, Selection System
    # We find where Phase 3 ends (walkV position) right before renderPillTags();
    target_pos = 'const walkV = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.08, 60), walkHMat); walkV.position.set(0, 0.04, 2); scene.add(walkV);'

    character_system_code = '''const walkV = new THREE.Mesh(new THREE.BoxGeometry(3.0, 0.08, 60), walkHMat); walkV.position.set(0, 0.04, 2); scene.add(walkV);

    // =========================================================================
    // PHASE 4: AI EMPLOYEE POPULATION SYSTEM (SINGLE SOURCE OF TRUTH ROSTER)
    // 9 Official AI Leaders + 18 Supporting/Decorative AI Specialists = 27 Total
    // =========================================================================

    const employeeRoster = [
      // 1. EXECUTIVE HQ (BIMA & SPECIALISTS)
      { id: "EMP-L01", name: "Bima", deptId: "bima", deptName: "Executive HQ", isLead: true, role: "Chief Executive Intelligence", title: "Chief Executive Officer", workstation: "Executive Walnut Desk #1", pose: "typing", suit: 0x1e1b4b, hair: 0x0f172a, skin: 0xfed7aa, x: -22.0, z: -18.2, rotY: 0, status: "ONLINE / SUPERVISING", task: "Memimpin Strategi Agensi MARU & Evaluasi Kurikulum" },
      { id: "EMP-S01", name: "AI Strategy Analyst A", deptId: "bima", deptName: "Executive HQ", isLead: false, role: "Strategic Operations Associate", title: "Executive Operations Specialist", workstation: "Executive Meeting Desk", pose: "reading", suit: 0x334155, hair: 0x1e293b, skin: 0xfde047, x: -24.5, z: -15.5, rotY: 1.57, status: "STANDBY / MONITORING", task: "Kompilasi Matriks Kinerja 7 Departemen Edukasi" },
      { id: "EMP-S02", name: "AI Strategy Analyst B", deptId: "bima", deptName: "Executive HQ", isLead: false, role: "Executive Assistant AI", title: "Executive Operations Specialist", workstation: "Executive Archive Desk", pose: "standing", suit: 0x475569, hair: 0x334155, skin: 0xfed7aa, x: -19.5, z: -15.5, rotY: -1.57, status: "STANDBY / READY", task: "Arsip Protokol Regulasi Penyiaran Media Digital" },

      // 2. CREATIVE & SCRIPTWRITING (HERMES & SPECIALISTS)
      { id: "EMP-L02", name: "Hermes", deptId: "hermes", deptName: "Creative & Scriptwriting", isLead: true, role: "Creative Director & Scriptwriter", title: "Head of Scriptwriting", workstation: "Scriptwriting Dual Desk A", pose: "typing", suit: 0x0369a1, hair: 0x0284c7, skin: 0xfcd34d, x: -9.0, z: -18.2, rotY: 0, status: "ONLINE / DRAFTING", task: "Menyusun Naskah TikTok Hook 3 Detik Berbobot Edukasi" },
      { id: "EMP-S03", name: "AI Narrative Specialist A", deptId: "hermes", deptName: "Creative & Scriptwriting", isLead: false, role: "Hook & Copywriter Assistant", title: "Creative Storyboard Specialist", workstation: "Scriptwriting Dual Desk B", pose: "typing", suit: 0x075985, hair: 0x64748b, skin: 0xfed7aa, x: -6.0, z: -18.2, rotY: 0, status: "STANDBY / BRAINSTORM", task: "Eksplorasi Variasi Kalimat Pembuka 9:16 Vertikal" },
      { id: "EMP-S04", name: "AI Storyboard Drafter", deptId: "hermes", deptName: "Creative & Scriptwriting", isLead: false, role: "Visual Metaphor Specialist", title: "Creative Visual Assistant", workstation: "Mood Board Desk", pose: "discussing", suit: 0x0284c7, hair: 0x0f172a, skin: 0xfde047, x: -7.5, z: -14.8, rotY: 3.14, status: "STANDBY / REVIEW", task: "Visualisasi Alur Adegan & Papan Mood Board" },

      // 3. BRAINSTORMING & TRENDS (NARA & SPECIALISTS)
      { id: "EMP-L03", name: "Nara", deptId: "nara", deptName: "Brainstorming & Trends", isLead: true, role: "Research Ideation Specialist", title: "Lead Trends Explorer", workstation: "Brainstorm Round Table (North)", pose: "discussing", suit: 0xb45309, hair: 0xf43f5e, skin: 0xfed7aa, x: 7.5, z: -18.4, rotY: 0, status: "ONLINE / ANALYZING", task: "Scraping Tren Isu Edukasi TikTok & Psikologi Audiens" },
      { id: "EMP-S05", name: "AI Viral Trend Scout A", deptId: "nara", deptName: "Brainstorming & Trends", isLead: false, role: "Social Listening Analyst", title: "Social Trends Associate", workstation: "Brainstorm Round Table (South)", pose: "reading", suit: 0xd97706, hair: 0x78350f, skin: 0xfcd34d, x: 7.5, z: -15.6, rotY: 3.14, status: "STANDBY / MONITORING", task: "Peta Sentimen Isu Viral Gen-Z & Komentar Publik" },
      { id: "EMP-S06", name: "AI Algorithm Auditor", deptId: "nara", deptName: "Brainstorming & Trends", isLead: false, role: "TikTok Algorithm Associate", title: "Engagement Metrics Specialist", workstation: "Brainstorm Round Table (West)", pose: "typing", suit: 0x92400e, hair: 0x451a03, skin: 0xfed7aa, x: 6.1, z: -17.0, rotY: 1.57, status: "STANDBY / CALCULATING", task: "Analisis Pola Retensi & Watch-Time Durasi 20 Detik" },

      // 4. ACADEMIC RESEARCH LIBRARY (CENDEKIA & SPECIALISTS)
      { id: "EMP-L04", name: "Cendekia", deptId: "cendekia", deptName: "Academic Research Library", isLead: true, role: "Chief Academic Researcher", title: "Head of Communications Pedagogy", workstation: "Academic Research Desk", pose: "reading", suit: 0x065f46, hair: 0x10b981, skin: 0xfed7aa, x: 22.0, z: -18.2, rotY: 0, status: "ONLINE / PEER-REVIEW", task: "Validasi Teori Pengantar Komunikasi & Etika Digital" },
      { id: "EMP-S07", name: "AI Peer-Reviewer A", deptId: "cendekia", deptName: "Academic Research Library", isLead: false, role: "Citation & Fact Checker", title: "Scientific Reference Assistant", workstation: "Library Reference Desk (East)", pose: "reading", suit: 0x047857, hair: 0x064e3b, skin: 0xfcd34d, x: 24.2, z: -15.5, rotY: -1.57, status: "STANDBY / FACT-CHECK", task: "Verifikasi Rujukan Teori Agenda Setting & Spiral of Silence" },
      { id: "EMP-S08", name: "AI Curriculum Archivist", deptId: "cendekia", deptName: "Academic Research Library", isLead: false, role: "Pedagogical Data Archivist", title: "Curriculum Archive Specialist", workstation: "Library Archive Desk (West)", pose: "standing", suit: 0x059669, hair: 0x1e293b, skin: 0xfde047, x: 19.8, z: -15.5, rotY: 1.57, status: "STANDBY / ARCHIVING", task: "Pengarsipan 7 Silabus Departemen Edukasi MARU" },

      // 5. PR & APPROVAL GATE (MAUS & SPECIALISTS)
      { id: "EMP-L05", name: "Maus", deptId: "maus", deptName: "PR & Approval Gate", isLead: true, role: "Quality Gatekeeper & Compliance", title: "Chief Quality & PR Gatekeeper", workstation: "Maus ACC Decision Station", pose: "typing", suit: 0x831843, hair: 0x0f172a, skin: 0xfcd34d, x: -22.0, z: -3.2, rotY: 0, status: "ONLINE / GATEKEEPING", task: "Audit Kepatuhan Kebijakan Komunitas & Siaga ACC!" },
      { id: "EMP-S09", name: "AI Compliance Auditor A", deptId: "maus", deptName: "PR & Approval Gate", isLead: false, role: "Community Guidelines Inspector", title: "Regulatory Compliance Specialist", workstation: "Pre-Audit Desk (West)", pose: "typing", suit: 0x9f1239, hair: 0x881337, skin: 0xfed7aa, x: -24.2, z: -0.5, rotY: 1.57, status: "STANDBY / VERIFYING", task: "Filter Hak Cipta, Klaim Sensitif & Standar Etika" },
      { id: "EMP-S10", name: "AI Policy Verifier B", deptId: "maus", deptName: "PR & Approval Gate", isLead: false, role: "PR Risk Assessment Associate", title: "Risk Mitigation Specialist", workstation: "Risk Analysis Desk (East)", pose: "reading", suit: 0xbe123c, hair: 0x4c0519, skin: 0xfde047, x: -19.8, z: -0.5, rotY: -1.57, status: "STANDBY / SCREENING", task: "Skrining Potensi Misinformasi & Tone of Voice" },

      // 6. VIDEO PRODUCTION (KIRANA & SPECIALISTS)
      { id: "EMP-L06", name: "Kirana", deptId: "kirana", deptName: "Video Production", isLead: true, role: "Executive Video Producer", title: "Lead Visual & Motion Director", workstation: "Video Editing Master Workstation", pose: "operating", suit: 0x581c87, hair: 0xa855f7, skin: 0xfed7aa, x: -7.5, z: -3.2, rotY: 0, status: "ONLINE / COMPOSITING", task: "Editing Video 9:16, Subtitle Dinamis & Color Grading" },
      { id: "EMP-S11", name: "AI Motion Graphicist A", deptId: "kirana", deptName: "Video Production", isLead: false, role: "Kinetic Typography Specialist", title: "Motion Effects Associate", workstation: "VFX Render Station (West)", pose: "operating", suit: 0x6b21a8, hair: 0x3b0764, skin: 0xfcd34d, x: -9.5, z: -0.5, rotY: 1.57, status: "STANDBY / RENDERING", task: "Penyusunan Animasi Tipografi Hook & Lower-Third" },
      { id: "EMP-S12", name: "AI Visual Asset Curator", deptId: "kirana", deptName: "Video Production", isLead: false, role: "Pixel Art & Texture Curator", title: "Visual Assets Specialist", workstation: "Asset Prep Desk (East)", pose: "standing", suit: 0x7e22ce, hair: 0x1e1b4b, skin: 0xfde047, x: -5.5, z: -0.5, rotY: -1.57, status: "STANDBY / INGEST", task: "Kurasi Aset Visual Pixel Art & Avatar MARU" },

      // 7. VOICE PRODUCTION STUDIO (ARDI & SPECIALISTS)
      { id: "EMP-L07", name: "Ardi", deptId: "ardi", deptName: "Voice Production Studio", isLead: true, role: "Lead Voice Actor & Sound Engineer", title: "Master Voice & Sound Producer", workstation: "Vocal Booth Condenser Mic Stand", pose: "recording", suit: 0x1e3a8a, hair: 0x3b82f6, skin: 0xfde047, x: 22.0, z: -3.5, rotY: 0, status: "ONLINE / BROADCASTING", task: "Dubbing Suara Karakter Muda Ekspresif & Audio DSP" },
      { id: "EMP-S13", name: "AI Sound Master Engineer", deptId: "ardi", deptName: "Voice Production Studio", isLead: false, role: "Audio Equalization Specialist", title: "Sound Mastering Specialist", workstation: "Audio Console Mixing Desk", pose: "operating", suit: 0x1d4ed8, hair: 0x172554, skin: 0xfed7aa, x: 22.0, z: -1.2, rotY: 3.14, status: "STANDBY / DSP-READY", task: "Dynamic Compressor, Loudness Equalizer & De-Esser" },
      { id: "EMP-S14", name: "AI Intonation Tuner", deptId: "ardi", deptName: "Voice Production Studio", isLead: false, role: "Prosody & Rhythm Analyst", title: "Speech Prosody Specialist", workstation: "Vocal Monitor Station", pose: "standing", suit: 0x2563eb, hair: 0x1e293b, skin: 0xfcd34d, x: 24.2, z: -0.5, rotY: -1.57, status: "STANDBY / AUDIT", task: "Pemeriksaan Resonansi & Humanisasi Pitch Suara" },

      // 8. IT OBSERVABILITY (WIRA & SPECIALISTS)
      { id: "EMP-L08", name: "Wira", deptId: "wira", deptName: "IT Observability", isLead: true, role: "Principal Systems Engineer", title: "Head of Infrastructure & Reliability", workstation: "Telemetry Master Dashboard", pose: "operating", suit: 0x134e4a, hair: 0x0ea5e9, skin: 0xfed7aa, x: -22.0, z: 12.8, rotY: 0, status: "ONLINE / TELEMETRY", task: "Monitoring Latensi Server & Zero Downtime Dashboard" },
      { id: "EMP-S15", name: "AI Server SRE A", deptId: "wira", deptName: "IT Observability", isLead: false, role: "System Reliability Associate", title: "DevOps & SRE Specialist", workstation: "Server Rack Alpha Console", pose: "standing", suit: 0x115e59, hair: 0x042f2e, skin: 0xfde047, x: -24.2, z: 15.0, rotY: 1.57, status: "STANDBY / OBSERVING", task: "Telemetri CPU, Memori & Integritas Basis Data" },
      { id: "EMP-S16", name: "AI Network Sentinel", deptId: "wira", deptName: "IT Observability", isLead: false, role: "Network & Sandbox Security AI", title: "Network Security Specialist", workstation: "Server Rack Beta Console", pose: "operating", suit: 0x0f766e, hair: 0x134e4a, skin: 0xfcd34d, x: -19.8, z: 15.0, rotY: -1.57, status: "STANDBY / FIREWALL", task: "Audit Sambungan Enkripsi SSL & Token Storage" },

      // 9. TIKTOK PUBLISHER (OOTTO & SPECIALISTS)
      { id: "EMP-L09", name: "Ootto", deptId: "ootto", deptName: "TikTok Publisher", isLead: true, role: "Autonomous Pipeline Operator", title: "Direct Post API Operator", workstation: "Publishing Release Workstation", pose: "operating", suit: 0x7c2d12, hair: 0x06b6d4, skin: 0xfcd34d, x: 22.0, z: 12.8, rotY: 0, status: "ONLINE / PIPELINE", task: "Otomasi Unggah Direct Post API & Kalender Rilis" },
      { id: "EMP-S17", name: "AI Distribution Strategist", deptId: "ootto", deptName: "TikTok Publisher", isLead: false, role: "Prime-Time Scheduler Assistant", title: "Publishing Operations Specialist", workstation: "Content Calendar Desk", pose: "typing", suit: 0x9a3412, hair: 0x431407, skin: 0xfed7aa, x: 24.2, z: 15.0, rotY: -1.57, status: "STANDBY / SCHEDULED", task: "Sinkronisasi Jadwal Tayang Jam Prime-Time TikTok" },
      { id: "EMP-S18", name: "AI Engagement Telemetry", deptId: "ootto", deptName: "TikTok Publisher", isLead: false, role: "Post-Release Analytics Specialist", title: "Social Metrics Specialist", workstation: "Telemetry Desk", pose: "reading", suit: 0xc2410c, hair: 0x1e293b, skin: 0xfde047, x: 19.8, z: 15.0, rotY: 1.57, status: "STANDBY / TRACKING", task: "Pencatatan Metrik Shares, Likes & Komentar Penonton" }
    ];

    // Reusable Character Geometries (Shared Memory Pool for 60 FPS)
    const charHeadGeo = new THREE.BoxGeometry(0.50, 0.50, 0.48);
    const charHairGeo = new THREE.BoxGeometry(0.56, 0.22, 0.54);
    const charTorsoGeo = new THREE.BoxGeometry(0.68, 0.85, 0.40);
    const charArmGeo = new THREE.BoxGeometry(0.18, 0.65, 0.18);
    const charLegGeo = new THREE.BoxGeometry(0.22, 0.70, 0.22);
    const charSittingLegGeo = new THREE.BoxGeometry(0.22, 0.22, 0.65);
    const charTieGeo = new THREE.BoxGeometry(0.12, 0.38, 0.04);
    const charGlassesGeo = new THREE.BoxGeometry(0.44, 0.12, 0.08);

    const tieMat = new THREE.MeshBasicMaterial({ color: 0x38bdf8 });
    const glassesMat = new THREE.MeshBasicMaterial({ color: 0x0f172a });

    const charactersGroup = new THREE.Group();
    charactersGroup.name = "CharactersGroup";
    scene.add(charactersGroup);

    const interactiveCharacters = [];

    // Procedural Character Builder Function
    function buildCharacter(cfg) {
      const charGrp = new THREE.Group();
      charGrp.position.set(cfg.x, 0, cfg.z);
      charGrp.rotation.y = cfg.rotY || 0;
      charGrp.userData = { isEmployee: true, employeeData: cfg };

      const suitMat = new THREE.MeshStandardMaterial({ color: cfg.suit, roughness: 0.7 });
      const skinMat = new THREE.MeshStandardMaterial({ color: cfg.skin, roughness: 0.5 });
      const hairMat = new THREE.MeshStandardMaterial({ color: cfg.hair, roughness: 0.8 });

      // Torso
      const isSeated = cfg.pose !== "standing";
      const torsoY = isSeated ? 0.95 : 1.15;
      const torso = new THREE.Mesh(charTorsoGeo, suitMat);
      torso.position.y = torsoY;
      torso.castShadow = true;
      charGrp.add(torso);

      // Head
      const head = new THREE.Mesh(charHeadGeo, skinMat);
      head.position.y = torsoY + 0.68;
      head.castShadow = true;
      charGrp.add(head);

      // Hair
      const hair = new THREE.Mesh(charHairGeo, hairMat);
      hair.position.y = torsoY + 0.95;
      charGrp.add(hair);

      // Leader Signature Accents (Tie & VIP Sunglasses for Leaders)
      if (cfg.isLead) {
        const tie = new THREE.Mesh(charTieGeo, tieMat);
        tie.position.set(0, torsoY + 0.12, 0.22);
        charGrp.add(tie);

        const glasses = new THREE.Mesh(charGlassesGeo, glassesMat);
        glasses.position.set(0, torsoY + 0.70, 0.26);
        charGrp.add(glasses);
      }

      // Legs based on Pose (Sitting vs Standing)
      if (isSeated) {
        const legL = new THREE.Mesh(charSittingLegGeo, suitMat);
        legL.position.set(-0.20, 0.52, 0.26);
        charGrp.add(legL);

        const legR = new THREE.Mesh(charSittingLegGeo, suitMat);
        legR.position.set(0.20, 0.52, 0.26);
        charGrp.add(legR);

        // Lower vertical calf to floor
        const calfGeo = new THREE.BoxGeometry(0.18, 0.45, 0.18);
        const calfL = new THREE.Mesh(calfGeo, suitMat);
        calfL.position.set(-0.20, 0.24, 0.54);
        charGrp.add(calfL);

        const calfR = new THREE.Mesh(calfGeo, suitMat);
        calfR.position.set(0.20, 0.24, 0.54);
        charGrp.add(calfR);
      } else {
        const legL = new THREE.Mesh(charLegGeo, suitMat);
        legL.position.set(-0.20, 0.38, 0);
        charGrp.add(legL);

        const legR = new THREE.Mesh(charLegGeo, suitMat);
        legR.position.set(0.20, 0.38, 0);
        charGrp.add(legR);
      }

      // Arms based on Pose
      if (cfg.pose === "typing" || cfg.pose === "operating") {
        // Arms reached forward to desk/keyboard
        const armL = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.16, 0.55), suitMat);
        armL.position.set(-0.28, torsoY + 0.15, 0.26);
        charGrp.add(armL);

        const armR = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.16, 0.55), suitMat);
        armR.position.set(0.28, torsoY + 0.15, 0.26);
        charGrp.add(armR);

        // Hands
        const handGeo = new THREE.BoxGeometry(0.12, 0.10, 0.14);
        const handL = new THREE.Mesh(handGeo, skinMat);
        handL.position.set(-0.28, torsoY + 0.15, 0.54);
        charGrp.add(handL);

        const handR = new THREE.Mesh(handGeo, skinMat);
        handR.position.set(0.28, torsoY + 0.15, 0.54);
        charGrp.add(handR);
      } else if (cfg.pose === "reading" || cfg.pose === "recording") {
        // One arm slightly raised, one resting
        const armL = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.45, 0.16), suitMat);
        armL.position.set(-0.30, torsoY, 0.12);
        charGrp.add(armL);

        const armR = new THREE.Mesh(new THREE.BoxGeometry(0.16, 0.16, 0.45), suitMat);
        armR.position.set(0.28, torsoY + 0.12, 0.22);
        charGrp.add(armR);
      } else {
        // Default standing or resting arms
        const armL = new THREE.Mesh(charArmGeo, suitMat);
        armL.position.set(-0.36, torsoY - 0.05, 0);
        charGrp.add(armL);

        const armR = new THREE.Mesh(charArmGeo, suitMat);
        armR.position.set(0.36, torsoY - 0.05, 0);
        charGrp.add(armR);
      }

      // Selection Halo / Hitbox Mesh (Invisible bounding box for easy Raycasting)
      const hitBoxGeo = new THREE.BoxGeometry(1.2, 2.2, 1.2);
      const hitBoxMat = new THREE.MeshBasicMaterial({ visible: false });
      const hitBox = new THREE.Mesh(hitBoxGeo, hitBoxMat);
      hitBox.position.y = 1.1;
      hitBox.userData = { parentCharacter: charGrp, employeeData: cfg };
      charGrp.add(hitBox);
      interactiveCharacters.push(hitBox);

      charactersGroup.add(charGrp);
      return charGrp;
    }

    // Populate all 27 employees into their designated workstations
    employeeRoster.forEach(emp => {
      buildCharacter(emp);
    });

    // -------------------------------------------------------------------------
    // CLICK SELECTION SYSTEM (EMPLOYEE INSPECTOR WITH RAYCASTER)
    // -------------------------------------------------------------------------
    const raycaster = new THREE.Raycaster();
    const mouse = new THREE.Vector2();

    function onSceneClick(e) {
      const view = document.getElementById("office-3d-viewport");
      if (!view) return;
      const rect = view.getBoundingClientRect();
      if (e.clientX < rect.left || e.clientX > rect.right || e.clientY < rect.top || e.clientY > rect.bottom) return;

      mouse.x = ((e.clientX - rect.left) / rect.width) * 2 - 1;
      mouse.y = -((e.clientY - rect.top) / rect.height) * 2 + 1;

      raycaster.setFromCamera(mouse, camera);
      const intersects = raycaster.intersectObjects(interactiveCharacters, false);

      if (intersects.length > 0) {
        const hit = intersects[0];
        const empData = hit.object.userData.employeeData;
        if (empData) {
          openEmployeeInspector(empData);
        }
      }
    }

    renderer.domElement.addEventListener("click", onSceneClick);

    // Inspector Handler for Employee
    function openEmployeeInspector(emp) {
      document.getElementById("insp-badge").innerText = emp.isLead ? "OFFICIAL AI LEADER" : "SUPPORTING SPECIALIST";
      document.getElementById("insp-badge").style.background = emp.isLead ? "var(--cyan)" : "#a855f7";
      document.getElementById("insp-title").innerText = emp.name;
      document.getElementById("insp-role").innerText = `${emp.role} (${emp.deptName})`;
      
      const elType = document.getElementById("insp-type");
      if (elType) elType.innerText = emp.isLead ? "LEADER (TIER 1)" : "SPECIALIST (TIER 2)";
      
      const elWs = document.getElementById("insp-workstation");
      if (elWs) elWs.innerText = emp.workstation;

      const elStat = document.getElementById("insp-status");
      if (elStat) elStat.innerText = emp.status;

      const elTask = document.getElementById("insp-task");
      if (elTask) elTask.innerText = emp.task;

      const btnText = document.getElementById("insp-focus-btn-text");
      if (btnText) btnText.innerText = `Fokus Kamera ke ${emp.name}`;

      targetFocus.set(emp.x, 1.2, emp.z);
      document.getElementById("office-inspector-panel").style.display = "block";
    }

    // Expose openEmployeeInspector globally
    window.MaruOffice3D_openEmployee = openEmployeeInspector;
'''

    if target_pos in html:
        html = html.replace(target_pos, character_system_code)
        print("[SUCCESS] Phase 4 Employee Population System code injected!")
    else:
        print("[ERROR] target_pos not found in studio_bulletproof.html!")
        return False

    with open('studio_bulletproof.html', 'w', encoding='utf-8') as f:
        f.write(html)
    print("[SUCCESS] studio_bulletproof.html successfully patched with Phase 4!")
    return True

if __name__ == '__main__':
    if not patch_phase4():
        sys.exit(1)
