from http.client import HTTPConnection
from http.server import ThreadingHTTPServer
from threading import Thread
import json
import multiprocessing
import time

import pytest

from src import dashboard, dashboard_ops, queue4, security
from src.hq.memory import HQMemoryManager, InternalAuthAuthority, CallerContext
from src.hq.models import JobBudget
from src.hq.queue import HQJobQueue
from src.hq.worker import HQWorker


def large_result(job, token):
    token.check()
    return {'recommendation': 'R' * (128 * 1024), 'requires_hq_review': True}


@pytest.fixture
def isolated(tmp_path, monkeypatch, fresh_db):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(queue4, 'QUEUE_DIR', tmp_path / 'queue')
    monkeypatch.setattr(queue4, 'LOG_PATH', tmp_path / 'queue.log')
    monkeypatch.setenv('REFERENCE_WATCHLIST', str(tmp_path / 'missing.json'))
    return tmp_path


@pytest.mark.parametrize('name', ['SYSTEM', 'ADMIN', 'OWNER', 'HQ', 'PEMILIK', 'EMP-L01', 'EMP-L02'])
def test_names_are_never_credentials(tmp_path, monkeypatch, name):
    monkeypatch.setattr(InternalAuthAuthority, '_server_bootstrap_secret', '')
    assert not CallerContext.resolve_actor(name).authenticated
    assert InternalAuthAuthority.issue_principal(name, '') is None
    memory = HQMemoryManager(tmp_path / 'memory.db')
    with pytest.raises(PermissionError):
        memory.store('HQ_ONLY', 'POLICY', 'Test', 'Test content', actor_id=name)
    with pytest.raises(PermissionError):
        memory.store('ORGANIZATIONAL', 'POLICY', 'Test', 'Test content')


def test_memory_tokens_scope_and_rotation(tmp_path):
    secret = 'fixture-bootstrap-secret-62-rotate'
    InternalAuthAuthority.set_bootstrap_secret(secret)
    try:
        hq = InternalAuthAuthority.issue_principal('HQ', secret)
        agent = InternalAuthAuthority.issue_principal('EMP-L02', secret)
        other = InternalAuthAuthority.issue_principal('EMP-L05', secret)
        assert hq.session_token not in repr(hq)
        memory = HQMemoryManager(tmp_path / 'memory.db')
        memory.store('HQ_ONLY', 'POLICY', 'HQ', 'Synthetic', auth_token=hq.session_token)
        memory.store('AGENT:EMP-L02', 'POLICY', 'Hermes', 'Synthetic', auth_token=agent.session_token)
        assert not memory.query(reader_agent_id='HQ')
        assert [row.title for row in memory.query(auth_token=agent.session_token)] == ['Hermes']
        assert not memory.query(auth_token=other.session_token)
        assert len(memory.query(auth_token=hq.session_token)) == 2
        with pytest.raises(PermissionError):
            memory.query(reader_agent_id='HQ', auth_token=agent.session_token)
        assert InternalAuthAuthority.revoke(agent.session_token)
        with pytest.raises(PermissionError):
            memory.query(auth_token=agent.session_token)
        InternalAuthAuthority.set_bootstrap_secret(secret + '-new')
        assert not InternalAuthAuthority.authenticate(hq.session_token)
    finally:
        InternalAuthAuthority.set_bootstrap_secret('')


def test_spawn_worker_large_result_and_separate_owner_decision(isolated):
    q = HQJobQueue()
    job = q.enqueue('EXECUTIVE_SUITE', 'PEMILIK', 'Audit fixture', {}, [], 'EMP-L01', 'large-output-62')
    assert HQWorker(q, process_start_method='spawn').execute_one_cycle(large_result, use_process_isolation=True)
    detail = q.review_detail(job.task_id)
    assert detail['status'] == 'COMPLETED'
    assert len(detail['result']['recommendation']) == 128 * 1024
    assert detail['review'] is None
    assert dashboard.action({'action':'hq_job_review','task_id':job.task_id,'decision':'APPROVED'})['actor'] == 'PEMILIK'
    assert q.review_detail(job.task_id)['review']['decision'] == 'APPROVED'
    with pytest.raises(ValueError, match='sudah diputuskan'):
        q.review_job(job.task_id, 'REVISION', '')


def test_watchlist_and_chat_keep_relevant_history(isolated):
    for i in range(201):
        dashboard_ops.add_watchlist({'url':f'https://example.org/{i}'})
    assert len(dashboard_ops.watchlist()) == 201
    assert len(dashboard_ops.watchlist(limit=100, offset=200)) == 1
    class Provider:
        available = True
        def __init__(self): self.calls = []
        def chat(self, messages):
            self.calls.append(messages)
            return 'Synthetic response'
    provider = Provider()
    dashboard_ops.chat(provider, {'prompt':'Context about Rina','bot_id':'EMP-L02'})
    dashboard_ops.chat(provider, {'prompt':'Other agent private context','bot_id':'EMP-L05'})
    dashboard_ops.chat(provider, {'prompt':'Follow-up','bot_id':'EMP-L02'})
    assert any(m['content'] == 'Context about Rina' for m in provider.calls[-1])
    assert not any(m['content'] == 'Other agent private context' for m in provider.calls[-1])


def test_approval_dedup_only_for_real_waiting_duplicate(isolated):
    pending = [{'id':'episode-1','status':'pending_approval','title':'Episode','hook':'Hook'}]
    linked = [{'id':'content-1','episode_id':'episode-1','status':'REVISI'}]
    assert dashboard._approval_cards(linked, pending)[0]['episode_id'] == 'episode-1'
    linked[0]['status'] = 'MENUNGGU'
    assert [row['id'] for row in dashboard._approval_cards(linked, pending)] == ['content-1']


def test_direct_upload_requires_publication_confirmation(isolated, monkeypatch):
    import ootto
    from ootto import tiktok
    monkeypatch.setattr(ootto, 'ALLOW_DIRECT', True)
    monkeypatch.setattr(tiktok, 'direct_post', lambda _: {'publish_id':'mock-ref','status':'terkirim_direct'})
    video = isolated / 'synthetic.mp4'
    video.write_bytes(b'test video placeholder')
    queue4.create('synthetic','Fixture',video=str(video))
    queue4.owner_decision('synthetic','SETUJU')
    row = queue4.transition('synthetic','TERJADWAL','ootto')
    row['mode_tiktok'] = 'direct'
    row = ootto.kirim(row)
    assert row['status'] == 'DIKIRIM_TIKTOK'
    monkeypatch.setattr(tiktok, 'post_status', lambda _: {'status':'PROCESSING_UPLOAD'})
    assert ootto.reconcile_direct(row) is None
    monkeypatch.setattr(tiktok, 'post_status', lambda _: {'status':'PUBLISH_COMPLETE'})
    assert ootto.reconcile_direct(row)['status'] == 'TAYANG'


def test_http_session_matrix_and_hq_access_gate(isolated, monkeypatch):
    password = 'local-phase62-fixture-password'
    auth = security.AuthManager(password)
    monkeypatch.setattr(dashboard, 'RUNTIME', security.Runtime(auth))
    with ThreadingHTTPServer(('127.0.0.1', 0), dashboard.Handler) as server:
        server_thread = Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        def request(method, url, data=None, token=None):
            headers = {'Content-Type':'application/json'}
            if token is not None:
                headers['Authorization'] = f'Bearer {token}'
            connection = HTTPConnection('127.0.0.1', server.server_port, timeout=5)
            try:
                connection.request(method, url, None if data is None else json.dumps(data), headers)
                res = connection.getresponse()
                return res.status, json.loads(res.read())
            finally:
                connection.close()
        try:
            assert request('POST','/api/login',{})[0] == 400
            assert request('POST','/api/login',{'password':'incorrect'})[0] == 401
            assert request('GET','/api/hq/jobs/absent')[0] == 401
            assert request('GET','/api/state',token='invalid')[0] == 401
            expired, _ = auth.login(password,'expired-fixture',now=1)
            assert request('GET','/api/state',token=expired)[0] == 401
            code, session = request('POST','/api/login',{'password':password})
            assert code == 200
            token = session['token']
            assert request('GET','/api/hq/jobs/absent',token=token)[0] == 404
            assert request('GET','/api/watchlist',token=token)[0] == 200
            assert request('POST','/api/logout',{},token=token)[0] == 200
            assert request('GET','/api/state',token=token)[0] == 401
            assert request('POST','/api/login',{'password':password})[0] == 200
        finally:
            server.shutdown()
            server_thread.join(timeout=5)


def test_no_generated_password_in_local_server_logs(monkeypatch, capsys):
    monkeypatch.delenv('STUDIO_PASSWORD', raising=False)
    monkeypatch.delenv('STUDIO_ACCESS_TOKEN', raising=False)
    with pytest.raises(RuntimeError, match='STUDIO_PASSWORD'):
        security.from_environment('127.0.0.1')
    assert not capsys.readouterr().out


def test_verified_handoff_requires_owner_confirmation_and_current_qc(isolated, monkeypatch):
    from datetime import datetime, timedelta
    from src import approve, db
    import ootto
    episode_id = 'handoff-fixture'
    output = isolated / episode_id
    output.mkdir()
    monkeypatch.setattr(approve, 'out_dir', lambda _: output)
    monkeypatch.setattr(dashboard_ops, 'out_dir', lambda _: output)
    video = output / 'final.mp4'
    video.write_bytes(b'fixture, not a real video')
    script = {'title': 'Test handoff', 'beats': [], 'sources': []}
    db.save_episode(episode_id, 'rendered', {}, script, {'video': str(video)})
    (output / 'decision.json').write_text(json.dumps({'status':'approve','script_sha256':approve.script_fingerprint(script)}))
    queue4.create('handoff','Draft')
    queue4.owner_decision('handoff','SETUJU')
    args = {'action':'ootto_attach_approved_video','episode_id':episode_id,'content_id':'handoff','confirmed':True}
    with pytest.raises(ValueError, match='Konfirmasi'):
        dashboard.action({**args, 'confirmed':False})
    with pytest.raises(ValueError, match='QC'):
        dashboard.action(args)
    (output / 'qc_report.json').write_text(json.dumps({'video':str(video), 'passed':True}))
    assert dashboard.action(args)['verified_episode_video'] is True
    when = (datetime.now(ootto.TZ) + timedelta(hours=1)).isoformat()
    assert ootto.jadwalkan('handoff', when)['status'] == 'TERJADWAL'
    approve.invalidate(episode_id)
    result = ootto.kirim(queue4.get('handoff'))
    assert result['status'] == 'GAGAL'
    assert not result.get('tiktok_publish_id')


def never_returns(job, token):
    while True:
        time.sleep(.05)


def test_spawn_timeout_reaps_child(isolated):
    q = HQJobQueue()
    job = q.enqueue('EXECUTIVE_SUITE', 'PEMILIK', 'Timeout fixture', {}, [], 'EMP-L01', 'timeout-62',
                    budget=JobBudget(max_duration_sec=1))
    start = time.monotonic()
    before = {proc.pid for proc in multiprocessing.active_children()}
    assert not HQWorker(q, process_start_method='spawn').execute_one_cycle(never_returns, use_process_isolation=True)
    assert time.monotonic() - start < 5
    assert 'exceeded max duration budget' in q.get_job(job.task_id).error_message
    assert not {proc.pid for proc in multiprocessing.active_children()} - before


def test_hermes_only_reads_configured_inputs(isolated, monkeypatch):
    base = isolated / 'inbox'
    base.mkdir()
    (base / 'draft.txt').write_text('Synthetic input')
    outside = isolated / 'outside.txt'
    outside.write_text('Synthetic restricted input')
    monkeypatch.setenv('HERMES_INPUT_DIR', str(base))
    for value in ('../outside.txt', str(outside)):
        with pytest.raises(ValueError, match='direktori input'):
            dashboard.action({'action':'queue4_hermes', 'path':value})
    actions = []
    monkeypatch.setattr(dashboard.queue, 'enqueue', lambda *a, **kw: actions.append(kw['payload']) or 'fixture-job')
    assert dashboard.action({'action':'queue4_hermes','path':'draft.txt'})['queued'] == 'fixture-job'
    assert actions[0]['path'] == str(base / 'draft.txt')
