"""End-to-end smoke test against the real handler and temporary state (no external providers)."""
import os
import threading
from pathlib import Path
from http.server import ThreadingHTTPServer

import pytest

pw = pytest.importorskip('playwright.sync_api')

from src import dashboard, queue4, security


@pytest.mark.parametrize('webgl', [False, True])
def test_corporate_browser(tmp_path, monkeypatch, fresh_db, webgl):
    assets = os.getenv('MARU_TEST_THREE_ASSETS')
    if webgl and not assets:
        pytest.skip('Set MARU_TEST_THREE_ASSETS to pinned Three.js and OrbitControls assets for WebGL smoke test')
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(queue4, 'QUEUE_DIR', tmp_path / 'queue')
    monkeypatch.setattr(queue4, 'LOG_PATH', tmp_path / 'queue.log')
    monkeypatch.setattr(dashboard, 'RUNTIME', security.Runtime(security.AuthManager('Local-Test-Password-2026')))
    monkeypatch.setattr(dashboard, 'LLM_INSTANCE', dashboard.LLM([]))
    monkeypatch.setattr(dashboard, '_get_telemetry', lambda: {'status':'available', 'cpu_pct':0,
                                                              'ram_used_mb':1024, 'ram_total_mb':2048,
                                                              'ram_pct':50, 'disk_pct':22})
    queue4.create('approval', 'Approve test')
    queue4.transition('approval', 'MENUNGGU', 'hermes')
    with ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler) as server:
        runner = threading.Thread(target=server.serve_forever, daemon=True)
        runner.start()
        try:
            with pw.sync_playwright() as play:
                if not os.path.isfile(play.chromium.executable_path) and not os.getenv('PLAYWRIGHT_BROWSERS_PATH'):
                    pytest.skip('Chromium not installed; run playwright install chromium')
                browser = play.chromium.launch(args=['--use-angle=swiftshader', '--enable-unsafe-swiftshader'] if webgl else [])
                page = browser.new_page(viewport={'width': 390, 'height': 844}, timezone_id='UTC')

                def route_asset(route):
                    filename = route.request.url.rsplit('/', 1)[-1]
                    if webgl and filename in {'three.min.js', 'OrbitControls.js'}:
                        route.fulfill(path=str(Path(assets) / filename), content_type='application/javascript')
                    else:
                        route.abort()

                page.route('https://**/*', route_asset)
                errors = []
                page.on('pageerror', lambda error: errors.append(str(error)))
                page.goto(f'http://127.0.0.1:{server.server_port}/')
                pw.expect(page.locator('#preview-quick-login')).to_have_count(0)
                page.locator('#login-pass').fill('Local-Test-Password-2026')
                page.locator('#login-form button[type=submit]').click()
                pw.expect(page.locator('#login-screen')).to_be_hidden()
                page.reload()
                pw.expect(page.locator('#login-screen')).to_be_hidden()
                page.locator('#mobile-menu-btn').click()
                page.locator('#nav-btn-office').click()
                pw.expect(page.locator('#hud-pending-approvals')).to_have_text('1 Pending ACC')
                pw.expect(page.locator('#hud-cpu-val')).to_have_text('0.0%')
                pw.expect(page.locator('#hud-memory-val')).to_have_text('0 entri organisasi')
                pw.expect(page.locator('#hud-company-balance')).to_have_text('Tidak tersedia')
                assert page.locator('#hq-hud-bottom-dock').evaluate('(el)=>el.clientWidth < 390 && el.scrollWidth > el.clientWidth')
                hours = page.evaluate("new Intl.DateTimeFormat('id-ID',{hour:'2-digit',timeZone:'Asia/Jakarta'}).format(new Date())")
                assert page.locator('#hud-clock').inner_text().startswith(hours)
                if webgl:
                    pw.expect(page.locator('#office-3d-viewport canvas')).to_be_visible(timeout=15000)
                    page.locator('.room-tag', has_text='Executive HQ').evaluate('(el)=>el.click()')
                    pw.expect(page.locator('#office-inspector-panel')).to_be_visible()
                    page.locator('#insp-open-module-btn').click()
                    pw.expect(page.locator('#page-overview')).to_be_visible()
                    page.locator('#mobile-menu-btn').click()
                    page.locator('#nav-btn-office').click()
                else:
                    pw.expect(page.get_by_role('button', name='Buka roster 2D')).to_be_visible()
                page.locator('[data-dock=projects]').click()
                pw.expect(page.locator('#page-projects')).to_be_visible()
                page.locator('#hq-goal').fill('Uji tugas UI')
                page.locator('#hq-task-form button').click()
                pw.expect(page.locator('#hq-job-list')).to_contain_text('Uji tugas UI')
                page.locator('#mobile-menu-btn').click()
                page.locator('#btnAcc').click()
                pw.expect(page.locator('#cnt-col-wait')).to_have_text('1')
                page.locator('#workflow-cards-banner [data-card-act=DENY]').click()
                pw.expect(page.locator('#cnt-col-wait')).to_have_text('0')
                page.locator('#mobile-menu-btn').click()
                page.locator('[data-page=squad]').click()
                pw.expect(page.locator('#voxel-squad-grid button').first).to_be_visible()
                assert errors == []
                browser.close()
        finally:
            server.shutdown()
            runner.join(5)
