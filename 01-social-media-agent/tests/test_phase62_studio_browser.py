"""Studio Phase 6.2 against a real local Handler; all records and transports isolated."""
import json
import os
import threading
from datetime import datetime, timedelta
from http.server import ThreadingHTTPServer
from pathlib import Path

import pytest

pw = pytest.importorskip('playwright.sync_api')

import ootto
from src import approve, dashboard, dashboard_ops, db, queue4, security
from src.hq import memory
from src.hq.queue import HQJobQueue


def test_owner_workflows_in_browser(tmp_path, monkeypatch, fresh_db):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv('OOTTO_MODE', 'draft')
    monkeypatch.setenv('REFERENCE_WATCHLIST', str(tmp_path / 'no-seed.json'))
    monkeypatch.setattr(memory, 'DEFAULT_MEMORY_DB', tmp_path / 'memory.db')
    monkeypatch.setattr(queue4, 'QUEUE_DIR', tmp_path / 'queue')
    monkeypatch.setattr(queue4, 'LOG_PATH', tmp_path / 'queue.log')
    monkeypatch.setattr(dashboard, 'RUNTIME', security.Runtime(security.AuthManager('Studio-fixture-password-62')))
    monkeypatch.setattr(dashboard, 'LLM_INSTANCE', dashboard.LLM([]))
    monkeypatch.setattr(dashboard, '_get_telemetry', lambda: {'status':'unavailable'})

    def output(key):
        p = tmp_path / 'out' / key
        p.mkdir(parents=True, exist_ok=True)
        return p

    for module in (approve, dashboard, dashboard_ops):
        monkeypatch.setattr(module, 'out_dir', output)

    script = {'title':'Episode yang perlu ditinjau', 'hook':'Hook uji', 'caption':'Caption fixture',
              'sources':[{'title':'Referensi fixture', 'url':'https://example.org/reference'}],
              'beats':[{'kind':kind, 'headline':kind, 'narration':line, 'visual':{'type':'card'}, 'source_refs':[0]}
                       for kind,line in [('hook','Kalimat pembuka uji'), ('limit','Batasan nyata dalam naskah'), ('cta','Baca sumber lengkap')]]}
    db.save_episode('pending-fixture', 'pending_approval', {}, script)
    queue4.create('revision-fixture', 'Queue4 sedang revisi', episode_id='pending-fixture')
    queue4.owner_decision('revision-fixture', 'REVISI')
    video = output('ready-fixture') / 'final.mp4'
    video.write_bytes(b'fixture: video contents are not streamed')
    ready_script = {**script, 'title':'Episode siap ditautkan'}
    db.save_episode('ready-fixture', 'rendered', {}, ready_script, {'video':str(video)})
    (video.parent / 'decision.json').write_text(json.dumps({'status':'approve','script_sha256':approve.script_fingerprint(ready_script)}))
    (video.parent / 'qc_report.json').write_text(json.dumps({'video':str(video),'passed':True}))
    queue4.create('handoff-fixture', 'Draf Hermes untuk Ootto', naskah='Isi draf Hermes yang harus ditinjau.')
    queue4.transition('handoff-fixture', 'MENUNGGU', 'hermes')

    for key, title in [('preflight-fixture', 'Gagal sebelum upload'), ('unknown-fixture', 'Gagal tidak pasti'), ('sent-fixture', 'Belum dikonfirmasi tayang')]:
        queue4.create(key, title)
        queue4.owner_decision(key, 'SETUJU')
        queue4.transition(key, 'TERJADWAL', 'ootto')
    ootto.kirim(queue4.get('preflight-fixture'))  # Missing local video: no attempt to call TikTok.
    queue4.transition('unknown-fixture','GAGAL','ootto', ootto_result={'dispatch':'UNKNOWN','error':'Kesalahan transport fixture'})
    queue4.transition('sent-fixture','DIKIRIM_TIKTOK','ootto', tiktok_publish_id='fixture-only')

    q = HQJobQueue()
    job = q.enqueue('EXECUTIVE_SUITE','PEMILIK','Kajian UI HQ',{},[],'EMP-L01','browser62')
    lease = q.acquire_lease('fixture-worker')
    assert q.complete_job('fixture-worker', job.task_id, lease.fencing_token,
                          {'recommendation':'Rekomendasi fixture <script>teks aman</script>', 'requires_hq_review':True})
    for i in range(201):
        dashboard_ops.add_watchlist({'url':f'https://example.org/{i}', 'catatan':f'Referensi {i}'})
    dashboard_ops._append('chat', {'bot_id':'EMP-L02','role':'assistant','text':'Riwayat Hermes saja'},
                         {'bot_id':'EMP-L05','role':'assistant','text':'Riwayat Ardi saja'})

    assert dashboard.state()["hq"]["hq_jobs"][0]["task_id"] == job.task_id
    with ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            with pw.sync_playwright() as play:
                if not os.path.isfile(play.chromium.executable_path) and not os.getenv('PLAYWRIGHT_BROWSERS_PATH'):
                    pytest.skip('Chromium not installed')
                browser = play.chromium.launch()
                page = browser.new_page(viewport={'width':1280,'height':900})
                page.set_default_timeout(9000)
                errors = []
                page.on('pageerror', lambda err: errors.append(str(err)))
                page.route('https://**/*', lambda route: route.abort())
                page.route('**/api/state', lambda route: route.abort())
                page.goto(f'http://127.0.0.1:{server.server_port}/index.html')
                login = page.locator('#login-form button[type=submit]')
                page.locator('#login-pass').fill('Studio-fixture-password-62')
                login.click()
                pw.expect(page.locator('#login-screen')).to_be_visible()
                pw.expect(page.locator('#login-err')).to_contain_text('data dashboard belum bisa dimuat')
                pw.expect(page.locator('#toast')).not_to_contain_text('Berhasil masuk')
                page.unroute('**/api/state')
                page.reload()
                pw.expect(page.locator('#login-screen')).to_be_hidden()

                page.locator('#btnAcc').click()
                panel = page.locator('#phase62-dialog')
                page.locator('#workflow-cards-banner [data-review-card=pending-fixture]').click()
                pw.expect(panel).to_contain_text('Batasan nyata dalam naskah')
                pw.expect(panel.get_by_role('link', name='Referensi fixture ↗')).to_have_attribute('href','https://example.org/reference')
                panel.get_by_role('button', name='Beri ACC naskah').click()
                pw.expect(panel).to_be_visible()  # Required acknowledgement; no accidental approval.
                assert db.get_episode('pending-fixture')['status'] == 'pending_approval'
                panel.get_by_role('checkbox').check()
                edited = {**script, 'caption':'Caption diubah setelah tinjauan dibuka'}
                db.save_episode('pending-fixture', 'pending_approval', {}, edited)
                panel.get_by_role('button', name='Beri ACC naskah').click()
                pw.expect(page.locator('#phase62-error')).to_contain_text('Naskah berubah sejak ditinjau')
                assert db.get_episode('pending-fixture')['status'] == 'pending_approval'
                panel.get_by_role('button', name='Tutup').click()
                page.locator('#workflow-cards-banner [data-review-card=pending-fixture]').click()
                pw.expect(panel).to_contain_text('Caption diubah setelah tinjauan dibuka')
                panel.get_by_role('checkbox').check()
                panel.get_by_role('button', name='Beri ACC naskah').click()
                pw.expect(panel).to_be_hidden()
                assert db.get_episode('pending-fixture')['status'] == 'approved'

                page.locator('#workflow-cards-banner [data-review-card=handoff-fixture]').click()
                pw.expect(panel).to_contain_text('Isi draf Hermes')
                panel.get_by_role('checkbox').check()
                panel.get_by_role('button', name='Beri ACC naskah').click()
                pw.expect(panel).to_be_hidden()
                pw.expect(page.locator('[data-ootto-link=handoff-fixture]')).to_be_visible()
                pw.expect(page.locator('[data-ootto-sched=handoff-fixture]')).to_have_count(0)
                page.locator('[data-ootto-link=handoff-fixture]').click()
                panel.get_by_label('ID episode').fill('pending-fixture')
                panel.get_by_role('checkbox').check()
                panel.get_by_role('button', name='Tautkan video').click()
                pw.expect(page.locator('#phase62-error')).to_contain_text('Render episode belum tersedia')
                assert not queue4.get('handoff-fixture')['video']
                panel.get_by_label('ID episode').fill('ready-fixture')
                panel.get_by_role('button', name='Tautkan video').click()
                pw.expect(panel).to_be_hidden()
                pw.expect(page.locator('[data-ootto-sched=handoff-fixture]')).to_be_visible()
                when = (datetime.now(ootto.TZ) + timedelta(hours=1)).isoformat()
                page.once('dialog', lambda prompt: prompt.accept(when))
                page.locator('[data-ootto-sched=handoff-fixture]').click()
                pw.expect(page.locator('#col-sched')).to_contain_text('Draf Hermes untuk Ootto')
                pw.expect(page.locator('#col-sched')).to_contain_text('TikTok belum mengonfirmasi tayang')
                assert queue4.get('handoff-fixture')['status'] == 'TERJADWAL'

                page.locator('[data-ootto-recover=unknown-fixture]').click()
                pw.expect(panel).to_contain_text('Jangan mengirim ulang')
                pw.expect(panel.get_by_role('button', name='Kembalikan untuk ditinjau')).to_have_count(0)
                panel.get_by_role('button', name='Tutup').click()
                page.locator('[data-ootto-recover=preflight-fixture]').click()
                panel.get_by_role('textbox', name='Catatan pemulihan').fill('Periksa ulang artefak fixture')
                panel.get_by_role('button', name='Kembalikan untuk ditinjau').click()
                pw.expect(page.locator('#cnt-col-failed')).to_have_text('1')
                assert queue4.get('preflight-fixture')['status'] == 'MENUNGGU'

                page.locator('.nav-btn[data-page=studio]').click()
                pw.expect(page.locator('#wl-status')).to_contain_text('Halaman 1 · 100')
                page.locator('#wl-next').click()
                pw.expect(page.locator('#wl-status')).to_contain_text('Halaman 2 · 100')
                page.locator('#wl-next').click()
                pw.expect(page.locator('#wl-status')).to_contain_text('Halaman 3 · 1')
                pw.expect(page.locator('#watchlist-items')).to_contain_text('Referensi 200')
                pw.expect(page.locator('#wl-next')).to_be_disabled()
                page.locator('#toggle-chat-btn').click()
                pw.expect(page.locator('#chat-feed')).to_contain_text('Riwayat Hermes saja')
                pw.expect(page.locator('#chat-feed')).not_to_contain_text('Riwayat Ardi saja')
                page.locator('[data-select-bot=EMP-L05]').click()
                pw.expect(page.locator('#chat-feed')).to_contain_text('Riwayat Ardi saja')
                pw.expect(page.locator('#chat-feed')).not_to_contain_text('Riwayat Hermes saja')
                page.locator('#close-chat-btn').click()

                page.locator('#nav-btn-office').click()
                page.locator('[data-dock=projects]').click()
                page.locator('[data-hq-detail]').click()
                pw.expect(panel).to_contain_text('Rekomendasi fixture <script>teks aman</script>')
                pw.expect(panel).to_contain_text('Belum diputuskan')
                panel.get_by_role('combobox', name='Keputusan').select_option('REVISION')
                panel.get_by_role('textbox', name='Catatan').fill('Revisi fixture')
                panel.get_by_role('button', name='Catat keputusan HQ').click()
                pw.expect(panel).to_be_hidden()
                page.locator('[data-hq-detail]').click()
                pw.expect(panel).to_contain_text('Perlu revisi')
                pw.expect(panel).to_contain_text('COMPLETED')
                assert q.review_detail(job.task_id)['review']['decision'] == 'REVISION'
                assert not errors, errors
                browser.close()
        finally:
            server.shutdown()
            worker.join(5)
