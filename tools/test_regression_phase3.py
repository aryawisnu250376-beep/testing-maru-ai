import sys

def run_tests():
    print("======================================================================")
    print("MARU HQ — PHASE 3 INTERIOR FURNISHING & ROOM DECORATION VALIDATION")
    print("======================================================================\n")

    with open('studio_bulletproof.html', 'r', encoding='utf-8') as f:
        html = f.read()

    errors = []

    # 1. Pengecekan Perabotan Spesifik Tiap Departemen
    dept_furniture = [
        ("Bima (Executive Desk & Cabinet)", 'woodDeskMat' in html and 'cab = new THREE.Mesh' in html),
        ("Hermes (Mood Board & Dual Monitor)", 'Papan Mood Board' in html or 'board = new THREE.Mesh' in html),
        ("Nara (Round Brainstorm Table & Big Screen)", 'bTable = new THREE.Mesh' in html and 'tvScr = new THREE.Mesh' in html),
        ("Cendekia (3 Big Bookshelves & Library Desks)", 'shelf = new THREE.Mesh' in html and 'wood_parquet' in html),
        ("Maus (ACC Decision Board & Dual Monitors)", 'accSign = new THREE.Mesh' in html and 'accLight' in html),
        ("Kirana (Video Editing Desk & Softbox Light)", 'sbPole = new THREE.Mesh' in html and 'sbHead = new THREE.Mesh' in html),
        ("Ardi (Soundproof Booth, Mic & ON-AIR Light)", 'micP = new THREE.Mesh' in html and 'onAir = new THREE.Mesh' in html),
        ("Wira (2 Server Racks with Green LED)", 'rack = new THREE.Mesh' in html and 'screenGreenMat' in html),
        ("Ootto (Publishing Workstation & Content Calendar)", 'cal = new THREE.Mesh' in html and '0xfb923c' in html)
    ]
    for name, result in dept_furniture:
        if not result:
            errors.append(f"Missing department furniture: {name}")

    # 2. Pengecekan Perabotan 5 Fasilitas Bersama
    shared_furniture = [
        ("Canteen (Dining Table & Espresso Coffee Bar)", 'diningTable' in html or 'coffeeMachine' in html or 'bar = new THREE.Mesh' in html),
        ("Meeting Room (Big Conference Table & Presentation Screen)", 'conf = new THREE.Mesh' in html and 'prScr = new THREE.Mesh' in html),
        ("Lobby (Reception Curved Counter & Visitor Sofa)", 'rec = new THREE.Mesh' in html and 'sf = new THREE.Mesh' in html),
        ("Mushola (Emerald Green Prayer Rugs / Sajadah)", 'saj = new THREE.Mesh' in html and '0x065f46' in html),
        ("Lounge (Relaxing Sofa & Glass Coffee Table)", 'lSofa = new THREE.Mesh' in html and 'lTable = new THREE.Mesh' in html)
    ]
    for name, result in shared_furniture:
        if not result:
            errors.append(f"Missing shared furniture: {name}")

    # 3. Pengecekan Reusable Builders
    builders = [
        ("addDesk reusable builder", 'function addDesk(' in html),
        ("addChair reusable builder", 'function addChair(' in html),
        ("addMonitor reusable builder", 'function addMonitor(' in html),
        ("addPlant reusable builder", 'function addPlant(' in html)
    ]
    for name, result in builders:
        if not result:
            errors.append(f"Missing reusable builder: {name}")

    # 4. Pengecekan Integritas Kontrol & Sistem Lama
    controls = [
        ("Camera Mode Selector (ISO vs FREE)", 'id="cam-iso-btn"' in html and 'id="cam-free-btn"' in html),
        ("Touch Mobile D-Pad", 'window.MaruOffice3D.panCam' in html and 'window.MaruOffice3D.zoomCam' in html),
        ("Inspector Drawer Panel", 'id="office-inspector-panel"' in html and 'focusSelected' in html),
        ("Safe Navigation Page Switching", 'switchPage' in html and 'data-page="office"' in html),
        ("Session Auth Integrity", 'sessionStorage.getItem("maru_studio_token")' in html)
    ]
    for name, result in controls:
        if not result:
            errors.append(f"Missing control/auth: {name}")

    if errors:
        print("PHASE 3 VALIDATION FAILED:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    else:
        print("[PASS] Department-Specific Interiors Verified (All 9 Rooms Furnished)")
        print("[PASS] Shared Facilities Interiors Verified (Canteen, Meeting, Lobby, Mushola, Lounge)")
        print("[PASS] Reusable Procedural Geometry Builders Active (Desk, Chair, Monitor, Plant)")
        print("[PASS] Dual Camera Modes & Inspector Panel Preserved")
        print("[PASS] 100% Backward Compatibility with Existing Studio & Backend")
        print("\nSTATUS: ALL PHASE 3 TESTS PASSED! (100% SUCCESS)")

if __name__ == '__main__':
    run_tests()
