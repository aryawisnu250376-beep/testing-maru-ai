
import pytest

from src import dashboard, dashboard_ops, queue4
from src.hq.queue import HQJobQueue
from src.hq.worker import HQWorker


@pytest.fixture
def isolated(tmp_path, monkeypatch, fresh_db):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(queue4, 'QUEUE_DIR', tmp_path / 'queue')
    monkeypatch.setattr(queue4, 'LOG_PATH', tmp_path / 'queue.log')
    return tmp_path


def test_dashboard_task_idempotency_and_worker_completion(isolated, monkeypatch):
    payload = {'action': 'task_create', 'goal': 'Tinjau antrean', 'idempotency_key': 'test-1'}
    first = dashboard.action(payload)
    assert first == dashboard.action(payload)
    with pytest.raises(ValueError, match='berbeda'):
        dashboard.action({**payload, 'goal': 'Tugas berbeda'})
    assert dashboard._get_hq_data()['hq_status_counts'] == {'QUEUED': 1}

    class Provider:
        available = True

        def chat(self, messages):
            assert 'Tinjau antrean' in messages[-1]['content']
            return 'Respons fixture untuk pengujian'

    monkeypatch.setattr(dashboard_ops.LLM, 'from_config', lambda _: Provider())
    queue = HQJobQueue()
    assert HQWorker(queue).execute_one_cycle(dashboard_ops.execute_hq_job, use_process_isolation=False)
    job = queue.get_job(first['task_id'])
    assert job.status == 'COMPLETED'
    assert job.result_payload['requires_hq_review'] is True
    assert dashboard._get_hq_data()['hq_status_counts'] == {'COMPLETED': 1}


def test_approval_is_state_backed_and_provider_does_not_fabricate(isolated, monkeypatch):
    llm = dashboard.LLM([])
    monkeypatch.setattr(dashboard, 'LLM_INSTANCE', llm)
    with pytest.raises(RuntimeError, match='belum dikonfigurasi'):
        dashboard.action({'action': 'chat_assistant', 'prompt': 'Halo'})
    assert dashboard_ops.records('chat') == []
    queue4.create('test-card', 'Contoh', naskah='Draf sintetis')
    queue4.transition('test-card', 'MENUNGGU', 'hermes')
    state = dashboard.state()
    assert state['totals']['pending'] == 1
    assert state['mausbot_cards'][0]['content_id'] == 'test-card'
    approval = {'action': 'mausbot_card_decision', 'card_id': 'test-card', 'card_kind': 'content', 'decision': 'DENY'}
    assert dashboard.action(approval)['status'] == 'DITOLAK'
    assert dashboard.state()['totals']['pending'] == 0
    with pytest.raises(ValueError, match='sudah berubah'):
        dashboard.action(approval)


def test_chat_draft_and_watchlist_use_real_adapters(isolated, monkeypatch):
    class Provider:
        available = True

        def chat(self, messages):
            return 'Respons fixture yang berbeda dari prompt'

    monkeypatch.setattr(dashboard, 'LLM_INSTANCE', Provider())
    dashboard.action({'action': 'chat_assistant', 'bot_id': 'EMP-L02', 'prompt': 'Halo'})
    assert [m['role'] for m in dashboard_ops.records('chat')] == ['user', 'assistant']
    draft = dashboard.action({'action': 'hermes_create_draft', 'topic': 'Topik uji'})
    assert queue4.get(draft['content_id'])['status'] == 'MENUNGGU'
    assert queue4.get(draft['content_id'])['naskah'] == 'Respons fixture yang berbeda dari prompt'
    dashboard.action({'action': 'watchlist_add', 'url': 'https://example.org/ref', 'transcript': 'Pola naskah uji'})
    assert any(w['url'] == 'https://example.org/ref' and w['transcript'] == 'Pola naskah uji' for w in dashboard_ops.watchlist())
    with pytest.raises(ValueError, match='URL'):
        dashboard.action({'action': 'watchlist_add', 'url': 'file:///tmp/local'})
