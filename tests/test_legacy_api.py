import pytest

from legacy_api.app import REFRESH_LIMIT, app

AUTH = {'Authorization': 'Bearer demo-token'}


@pytest.fixture
def client():
    return app.test_client()


def test_refuse_sans_authentification(client):
    assert client.get('/api/contact').status_code == 401


def test_accepte_le_cookie_de_session(client):
    client.set_cookie('auth_token', 'demo-session')
    assert client.get('/api/contact?limit=1').status_code == 200


def test_limit_tronque(client):
    assert len(client.get('/api/contact?limit=7', headers=AUTH).json) == 7


def test_recherche_par_sous_chaine_sans_accent(client):
    results = client.get('/api/contact?company=societe generale', headers=AUTH).json
    assert results and all('Société Générale' in str(r) for r in results)


def test_refresh_limite_a_dix_resultats(client):
    results = client.get('/api/contact?company=BNP&refresh=true&limit=60', headers=AUTH).json
    assert len(results) == REFRESH_LIMIT


def test_le_filtre_linkedin(client):
    results = client.get('/api/contact?withLinkedinProfile=true', headers=AUTH).json
    assert all(any(i['type'] == 'ContactLinkedinInfo' for i in r['infos']) for r in results)
    assert 0.2 < len(results) / 500 < 0.45


def test_les_cabinets_n_ont_pas_de_specialite(client):
    items = client.get('/api/hunter', headers=AUTH).json['items']
    assert len(items) == 30 and all(h['functions'] == [] and h['sectors'] == [] for h in items)
