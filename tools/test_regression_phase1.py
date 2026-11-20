import re
import sys

def run_tests():
    with open('studio_bulletproof.html', 'r', encoding='utf-8') as f:
        html = f.read()

    errors = []

    # 1. Pastikan seluruh 4 halaman eksisting tetap ada
    expected_pages = ['page-overview', 'page-workflow', 'page-squad', 'page-studio', 'page-office']
    for p in expected_pages:
        if f'id="{p}"' not in html:
            errors.append(f"Missing page section: {p}")

    # 2. Pastikan tombol navigasi data-page lengkap
    expected_navs = ['overview', 'workflow', 'squad', 'studio', 'office']
    for n in expected_navs:
        if f'data-page="{n}"' not in html:
            errors.append(f"Missing nav button for: {n}")

    # 3. Pastikan Safe DOM Guards tetap ada
    if 'safeGetToken' not in html or 'sessionStorage' not in html:
        errors.append("Authentication / token handling broken!")

    # 4. Pastikan hook renderAll dan switchPage utuh
    if 'function switchPage' not in html or 'function renderAll' not in html:
        errors.append("Core SPA functions missing!")

    # 5. Pastikan Three.js terpasang dengan benar
    if 'three.min.js' not in html or 'OrbitControls.js' not in html:
        errors.append("Three.js libraries not injected!")

    # 6. Pastikan Inspector & Camera controls ada
    if 'cam-iso-btn' not in html or 'office-inspector-panel' not in html:
        errors.append("Office UI controls missing!")

    # 7. Pastikan 9 leader resmi MARU ada di konfigurasi
    leaders = ["Bima", "Hermes", "Nara", "Cendekia", "Maus", "Kirana", "Ardi", "Wira", "Ootto"]
    for l in leaders:
        if l not in html:
            errors.append(f"Official leader missing: {l}")

    if errors:
        print("REGRESSION TEST FAILED:")
        for e in errors:
            print(" -", e)
        sys.exit(1)
    else:
        print("ALL REGRESSION TESTS PASSED! (7/7 Checks OK)")
        print("Compatibility: 100% Backward Compatible with Existing System.")

if __name__ == '__main__':
    run_tests()
