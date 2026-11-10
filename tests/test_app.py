import pytest

from backend import app as app_module
from backend.agent import Trace


@pytest.fixture
def client(monkeypatch):
    def fake_run_agent(message, history, exclude_ids):
        return {'response': f'ok:{message}', 'contacts': [], 'hunters': [], 'sources_used': [], 'trace': Trace()}
    monkeypatch.setattr(app_module, 'run_agent', fake_run_agent)
    return app_module.app.test_client()


def test_chat_repond(client):
    response = client.post('/api/chat', json={'message': 'bonjour'})
    assert response.status_code == 200 and response.json['response'] == 'ok:bonjour'
    assert 'trace' not in response.json and response.headers['X-Request-Id']


@pytest.mark.parametrize('payload', [{}, {'message': '   '}, {'message': 'x' * 501},
                                     {'message': 'a', 'history': 'pas une liste'}])
def test_chat_refuse_les_entrees_invalides(client, payload):
    assert client.post('/api/chat', json=payload).status_code == 400


def test_chat_refuse_un_corps_non_json(client):
    assert client.post('/api/chat', data='texte', content_type='text/plain').status_code == 400


def test_health(client):
    assert client.get('/api/health').json == {'status': 'ok'}
