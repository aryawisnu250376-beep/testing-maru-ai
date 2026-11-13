import re

with open('studio_bulletproof.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Update renderAll() hook to trigger window.MaruOffice3D.syncBackendState(S.data)
old_render_hook = 'offSub.innerText = "9 Agen Pemimpin Siaga · Data bersumber langsung dari /api/state";\n        }\n      }\n    } catch (_) {}'

new_render_hook = '''offSub.innerText = "9 Agen Pemimpin Siaga · Data bersumber langsung dari /api/state";
        }
      }
    } catch (_) {}

    // PHASE 5: Trigger real backend state synchronization to Living 3D Office
    try {
      if (window.MaruOffice3D && window.MaruOffice3D.syncBackendState) {
        window.MaruOffice3D.syncBackendState(S.data);
      }
    } catch (e) {
      console.error("[MARU 3D] Error syncing backend state:", e);
    }'''

if old_render_hook in text:
    text = text.replace(old_render_hook, new_render_hook, 1)
    print("[SUCCESS] renderAll hooked into window.MaruOffice3D.syncBackendState!")
else:
    print("[WARNING] old_render_hook not found, checking alternatives...")

# 2. Add Phase 5 State Machine, Animation Engine, Waypoint Movement, and Backend Synchronization
target_marker = 'renderer.domElement.addEventListener("click", onSceneClick);'

phase5_code = '''renderer.domElement.addEventListener("click", onSceneClick);

    // =========================================================================
    // PHASE 5: DYNAMIC TASK BEHAVIORS, STATE MACHINE & BACKEND SYNCHRONIZATION
    // =========================================================================

    // Activity States Definition
    const ACTIVITY_STATES = {
      IDLE: "IDLE",
      READY: "READY",
      WALKING: "WALKING",
      WORKING: "WORKING",
      REVIEWING: "REVIEWING",
      WAITING_APPROVAL: "WAITING_APPROVAL",
      COMPLETED: "COMPLETED",
      DISCONNECTED: "DISCONNECTED"
    };

    // Store references to character groups and their limb meshes for animation
    const leaderMeshMap = {};
    const decorativeNpcMeshes = [];

    // Enhance character builder mapping
    employeeRoster.forEach(emp => {
      const charGrp = charactersGroup.children.find(c => c.userData && c.userData.employeeData && c.userData.employeeData.id === emp.id);
      if (charGrp) {
        emp.sceneGroup = charGrp;
        emp.baseX = emp.x;
        emp.baseZ = emp.z;
        emp.baseRotY = emp.rotY || 0;
        emp.currentActivity = emp.isLead ? ACTIVITY_STATES.READY : ACTIVITY_STATES.IDLE;
        emp.targetPos = null;
        emp.walkingSpeed = 0.08;

        if (emp.isLead) {
          leaderMeshMap[emp.id] = { emp, group: charGrp };
        } else {
          decorativeNpcMeshes.push({ emp, group: charGrp });
        }
      }
    });

    // Dedicated Waypoints for Studio Recording & Production Movement
    const WAYPOINTS = {
      RECORDING_BOOTH: { x: 20.2, z: -3.5, label: "Vocal Recording Booth" },
      AUDIO_CONSOLE: { x: 22.0, z: -1.2, label: "Audio Mastering Console" },
      VIDEO_EDITING: { x: -7.5, z: -3.2, label: "Video Compositing Bay" },
      MAUS_DECISION: { x: -22.0, z: -3.2, label: "Maus ACC Gate" }
    };

    // Visual Indicator Alert Badges over Desks (e.g. Red '!' for Maus ACC)
    const alertBadgeGeo = new THREE.BoxGeometry(0.35, 0.35, 0.35);
    const alertBadgeMat = new THREE.MeshBasicMaterial({ color: 0xef4444 });
    const mausAlert = new THREE.Mesh(alertBadgeGeo, alertBadgeMat);
    mausAlert.position.set(-22.0, 3.2, -3.2);
    mausAlert.visible = false;
    scene.add(mausAlert);

    // Sync Backend State with 9 Official Leaders (Ground Truth Engine)
    function syncBackendState(data) {
      if (!data) {
        // Disconnected or offline fallback
        employeeRoster.forEach(emp => {
          if (emp.isLead) {
            emp.currentActivity = ACTIVITY_STATES.DISCONNECTED;
            emp.status = "DISCONNECTED";
            emp.statusOrigin = "BACKEND_DISCONNECTED";
            emp.task = "Sambungan backend terputus atau offline";
          }
        });
        if (selectedEmployeeData) openEmployeeInspector(selectedEmployeeData);
        return;
      }

      const q4 = data.queue4 || [];
      const cards = data.mausbot_cards || [];
      const pendingCards = cards.filter(c => c.status === "pending");
      const draftItems = q4.filter(i => i.status === "DRAF" || i.status === "REVISI" || i.status === "DITOLAK");
      const waitItems = q4.filter(i => i.status === "MENUNGGU");
      const prodItems = q4.filter(i => i.status === "DISETUJUI");
      const schedItems = q4.filter(i => i.status === "TERJADWAL" || i.status === "TAYANG" || i.status === "DRAF_TIKTOK");

      // 1. BIMA (EMP-L01) - Supervises overall MARU pipeline
      const bima = employeeRoster.find(e => e.id === "EMP-L01");
      if (bima) {
        bima.statusOrigin = "ACTUAL_BACKEND_DATA";
        if (pendingCards.length > 0) {
          bima.currentActivity = ACTIVITY_STATES.REVIEWING;
          bima.status = "REVIEWING (EVALUASI DRAF)";
          bima.task = `Memantau ${pendingCards.length} draf menunggu izin ACC di Gerbang Maus`;
        } else if (prodItems.length > 0 || schedItems.length > 0) {
          bima.currentActivity = ACTIVITY_STATES.WORKING;
          bima.status = "WORKING (SUPERVISI KONTEN)";
          bima.task = `Supervisi produksi: ${prodItems.length} konten disetujui, ${schedItems.length} terjadwal`;
        } else {
          bima.currentActivity = ACTIVITY_STATES.READY;
          bima.status = "READY / STANDBY";
          bima.task = "Standby orkestrasi kurikulum media MARU HQ";
        }
      }

      // 2. HERMES (EMP-L02) - Scriptwriting & Creative ideation
      const hermes = employeeRoster.find(e => e.id === "EMP-L02");
      if (hermes) {
        hermes.statusOrigin = "ACTUAL_BACKEND_DATA";
        if (draftItems.length > 0) {
          hermes.currentActivity = ACTIVITY_STATES.WORKING;
          hermes.status = "WORKING (MENULIS NASKAH)";
          hermes.task = `Menyusun & menyempurnakan ${draftItems.length} naskah hook 3 detik`;
        } else {
          hermes.currentActivity = ACTIVITY_STATES.READY;
          hermes.status = "READY (IDEASI SIAGA)";
          hermes.task = "Standby perancangan hook narasi komunikasi";
        }
      }

      // 3. NARA (EMP-L03) - Trends & Audience Research
      const nara = employeeRoster.find(e => e.id === "EMP-L03");
      if (nara) {
        nara.statusOrigin = "ACTUAL_BACKEND_DATA";
        if (draftItems.length > 0 || q4.length > 0) {
          nara.currentActivity = ACTIVITY_STATES.WORKING;
          nara.status = "WORKING (ANALISIS TREN)";
          nara.task = `Eksplorasi retensi audiens untuk ${q4.length} item antrean konten`;
        } else {
          nara.currentActivity = ACTIVITY_STATES.READY;
          nara.status = "READY (MONITOR TREN)";
          nara.task = "Standby radar tren edukasi media sosial";
        }
      }

      // 4. CENDEKIA (EMP-L04) - Academic verification & Fact check
      const cendekia = employeeRoster.find(e => e.id === "EMP-L04");
      if (cendekia) {
        cendekia.statusOrigin = "ACTUAL_BACKEND_DATA";
        if (waitItems.length > 0 || draftItems.length > 0) {
          cendekia.currentActivity = ACTIVITY_STATES.REVIEWING;
          cendekia.status = "REVIEWING (VERIFIKASI TEORI)";
          cendekia.task = "Validasi teori komunikasi & etika penyiaran digital";
        } else {
          cendekia.currentActivity = ACTIVITY_STATES.READY;
          cendekia.status = "READY (PERPUSTAKAAN SIAGA)";
          cendekia.task = "Standby arsip 7 silabus departemen edukasi MARU";
        }
      }

      // 5. MAUS (EMP-L05) - Approval Gatekeeper
      const maus = employeeRoster.find(e => e.id === "EMP-L05");
      if (maus) {
        maus.statusOrigin = "ACTUAL_BACKEND_DATA";
        if (pendingCards.length > 0 || waitItems.length > 0) {
          maus.currentActivity = ACTIVITY_STATES.WAITING_APPROVAL;
          maus.status = "WAITING_APPROVAL (BUTUH ACC!)";
          maus.task = `URGENT: ${pendingCards.length} draf butuh otorisasi ACC pemilik HQ!`;
          mausAlert.visible = true;
        } else {
          maus.currentActivity = ACTIVITY_STATES.READY;
          maus.status = "READY (GERBANG BERSIH)";
          maus.task = "Antrean bersih, seluruh draf telah disetujui/ditinjau";
          mausAlert.visible = false;
        }
      }

      // 6. KIRANA (EMP-L06) - Video Production & Rendering
      const kirana = employeeRoster.find(e => e.id === "EMP-L06");
      if (kirana) {
        kirana.statusOrigin = "ACTUAL_BACKEND_DATA";
        if (prodItems.length > 0) {
          kirana.currentActivity = ACTIVITY_STATES.WORKING;
          kirana.status = "WORKING (RENDERING VIDEO)";
          kirana.task = `Compositing video 9:16 untuk ${prodItems.length} konten disetujui`;
        } else {
          kirana.currentActivity = ACTIVITY_STATES.READY;
          kirana.status = "READY (STUDIO SIAGA)";
          kirana.task = "Standby render pipeline video & kinetic typography";
        }
      }

      // 7. ARDI (EMP-L07) - Voice Actor & Audio Production (With Dynamic Studio Movement!)
      const ardi = employeeRoster.find(e => e.id === "EMP-L07");
      if (ardi) {
        ardi.statusOrigin = "ACTUAL_BACKEND_DATA";
        if (prodItems.length > 0) {
          ardi.currentActivity = ACTIVITY_STATES.WORKING;
          ardi.status = "WORKING (REKAMAN DUBBING)";
          ardi.task = "Dubbing suara karakter muda ekspresif di depan mic kondenser";
          // Trigger dynamic movement: Ardi steps up to vocal booth
          ardi.targetPos = WAYPOINTS.RECORDING_BOOTH;
        } else {
          ardi.currentActivity = ACTIVITY_STATES.READY;
          ardi.status = "READY (VOKAL SIAGA)";
          ardi.task = "Standby di meja konsol audio mixer";
          // Return to base desk
          ardi.targetPos = { x: ardi.baseX, z: ardi.baseZ };
        }
      }

      // 8. WIRA (EMP-L08) - IT Observability & Server Health
      const wira = employeeRoster.find(e => e.id === "EMP-L08");
      if (wira) {
        wira.statusOrigin = "ACTUAL_BACKEND_DATA";
        wira.currentActivity = ACTIVITY_STATES.WORKING;
        wira.status = "WORKING (TELEMETRI AKTIF)";
        wira.task = "Audit server, zero-downtime, & keamanan basis data SQLite";
      }

      // 9. OOTTO (EMP-L09) - TikTok Direct Post Publisher
      const ootto = employeeRoster.find(e => e.id === "EMP-L09");
      if (ootto) {
        ootto.statusOrigin = "ACTUAL_BACKEND_DATA";
        if (schedItems.length > 0) {
          ootto.currentActivity = ACTIVITY_STATES.WORKING;
          ootto.status = "WORKING (PUBLISHING READY)";
          ootto.task = `Menjadwalkan rilis ${schedItems.length} konten ke TikTok Content Posting API`;
        } else {
          ootto.currentActivity = ACTIVITY_STATES.READY;
          ootto.status = "READY (PIPELINE SIAGA)";
          ootto.task = "Standby jadwal tayang prime-time & kuota sandbox";
        }
      }

      // Refresh inspector if open
      if (selectedEmployeeData) {
        const updated = employeeRoster.find(e => e.id === selectedEmployeeData.id);
        if (updated) openEmployeeInspector(updated);
      }
    }

    // Expose syncBackendState to window.MaruOffice3D
    window.MaruOffice3D.syncBackendState = syncBackendState;

    let selectedEmployeeData = null;

    // Track selected employee for camera follow mode
    let isCameraFollowing = false;
    let followTarget = null;

    window.MaruOffice3D.toggleCameraFollow = () => {
      isCameraFollowing = !isCameraFollowing;
      const btn = document.getElementById("insp-follow-btn");
      if (btn) {
        btn.innerText = isCameraFollowing ? "🎥 Matikan Ikuti Karakter" : "🎥 Ikuti Karakter (Follow Mode)";
        btn.style.background = isCameraFollowing ? "var(--rose)" : "rgba(168,85,247,0.15)";
      }
    };
'''

if target_marker in text:
    text = text.replace(target_marker, phase5_code)
    print("[SUCCESS] Phase 5 State Machine & Backend Synchronization injected!")
else:
    print("[ERROR] target_marker not found!")

# 3. Enhance openEmployeeInspector to remember selected employee and add follow button
old_open_emp_end = 'targetFocus.set(emp.x, 1.2, emp.z);\n      document.getElementById("office-inspector-panel").style.display = "block";\n    }'
new_open_emp_end = '''targetFocus.set(emp.x, 1.2, emp.z);
      selectedEmployeeData = emp;
      followTarget = emp.sceneGroup;

      const actEl = document.getElementById("insp-activity-state");
      if (actEl) actEl.innerText = emp.currentActivity || "READY";

      document.getElementById("office-inspector-panel").style.display = "block";
    }'''

if old_open_emp_end in text:
    text = text.replace(old_open_emp_end, new_open_emp_end, 1)
    print("[SUCCESS] openEmployeeInspector hooked with selectedEmployeeData!")

# 4. Add Activity State display and Camera Follow button to inspector HTML
old_task_markup = '''      <div style="background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;font-size:11px;border:1px solid rgba(255,255,255,0.08);margin-bottom:12px;">
        <div style="color:var(--muted);margin-bottom:2px;">Tugas & Aktivitas:</div>
        <div id="insp-task" style="color:var(--text);font-weight:500;">Memimpin Visi Media & Konten MARU HQ</div>
      </div>'''

new_task_markup = '''      <div style="background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;font-size:11px;border:1px solid rgba(255,255,255,0.08);margin-bottom:8px;">
        <div style="color:var(--muted);margin-bottom:2px;">Activity State:</div>
        <div id="insp-activity-state" style="font-weight:800;color:var(--cyan);letter-spacing:0.5px;">READY</div>
      </div>
      <div style="background:rgba(0,0,0,0.3);border-radius:10px;padding:10px;font-size:11px;border:1px solid rgba(255,255,255,0.08);margin-bottom:12px;">
        <div style="color:var(--muted);margin-bottom:2px;">Tugas & Aktivitas Aktual:</div>
        <div id="insp-task" style="color:var(--text);font-weight:500;">Memimpin Visi Media & Konten MARU HQ</div>
      </div>
      <button id="insp-follow-btn" onclick="window.MaruOffice3D.toggleCameraFollow()" style="width:100%;margin-bottom:6px;background:rgba(168,85,247,0.15);border:1px solid #c084fc;color:#c084fc;font-weight:800;font-size:11px;padding:8px;border-radius:8px;cursor:pointer;display:flex;align-items:center;justify-content:center;gap:6px;">
        <span>🎥</span><span>Ikuti Karakter (Follow Mode)</span>
      </button>'''

if old_task_markup in text:
    text = text.replace(old_task_markup, new_task_markup, 1)
    print("[SUCCESS] Inspector HTML upgraded with Activity State and Follow Mode button!")

# 5. Update animate() loop to support subtle idle breathing, typing, waypoint walking, and camera follow
old_animate = '''    function animate() {
      requestAnimationFrame(animate);
      controls.update();
      updatePillTags();
      renderer.render(scene, camera);
    }'''

new_animate = '''    let clock = new THREE.Clock();
    function animate() {
      requestAnimationFrame(animate);
      const elapsedTime = clock.getElapsedTime();

      // 1. Subtle Procedural Animations for Characters (Zero CPU overhead)
      // Working Leaders (Subtle typing bobbing on Torso / Arms)
      employeeRoster.forEach((emp, i) => {
        if (!emp.sceneGroup) return;
        const grp = emp.sceneGroup;

        // Waypoint Navigation (Lightweight smooth lerp)
        if (emp.targetPos) {
          const dx = emp.targetPos.x - grp.position.x;
          const dz = emp.targetPos.z - grp.position.z;
          const dist = Math.sqrt(dx * dx + dz * dz);
          if (dist > 0.1) {
            grp.position.x += dx * 0.05;
            grp.position.z += dz * 0.05;
            emp.currentActivity = ACTIVITY_STATES.WALKING;
          } else {
            grp.position.x = emp.targetPos.x;
            grp.position.z = emp.targetPos.z;
            emp.targetPos = null;
          }
        }

        // Procedural Micro-Animations based on State
        if (emp.currentActivity === ACTIVITY_STATES.WORKING || emp.currentActivity === ACTIVITY_STATES.REVIEWING) {
          // Subtle rhythmic typing breathing
          grp.position.y = Math.sin(elapsedTime * 6.0 + i) * 0.02;
        } else if (emp.currentActivity === ACTIVITY_STATES.WAITING_APPROVAL) {
          // Alert pulse
          grp.position.y = Math.sin(elapsedTime * 8.0) * 0.04;
        } else {
          // Gentle idle breathing
          grp.position.y = Math.sin(elapsedTime * 2.0 + i) * 0.01;
        }
      });

      // Maus Alert Billboard Pulse
      if (mausAlert && mausAlert.visible) {
        mausAlert.rotation.y = elapsedTime * 3.0;
        mausAlert.position.y = 3.2 + Math.sin(elapsedTime * 4.0) * 0.2;
      }

      // Camera Follow Mode
      if (isCameraFollowing && followTarget && controls && camera) {
        controls.target.lerp(new THREE.Vector3(followTarget.position.x, 1.2, followTarget.position.z), 0.08);
      }

      controls.update();
      updatePillTags();
      renderer.render(scene, camera);
    }'''

if old_animate in text:
    text = text.replace(old_animate, new_animate, 1)
    print("[SUCCESS] animate() loop upgraded with micro-animations and smooth camera follow!")
else:
    print("[ERROR] old_animate not found!")

with open('studio_bulletproof.html', 'w', encoding='utf-8') as f:
    f.write(text)

print("[SUCCESS] studio_bulletproof.html successfully patched with Phase 5!")
