from backend.scoring import WEIGHTS, rank, relevance


def contact(**fields):
    base = {'poste': '', 'entreprise': '', 'linkedin': '', 'type_contact': 'contact_reseau', 'amene_par': ''}
    return {**base, **fields}


def test_poste_de_direction_et_poste_de_support():
    assert relevance(contact(poste='Directrice Financière')) == WEIGHTS['senior']
    assert relevance(contact(poste='Assistante de Direction')) == WEIGHTS['junior']
    assert relevance(contact(poste='Responsable Logistique')) == 0


def test_les_mots_cles_sont_des_mots_entiers():
    # « coo » ne doit pas être trouvé dans « Coordinateur », ni « intern » dans « International ».
    assert relevance(contact(poste='Coordinateur Logistique')) == WEIGHTS['junior']
    assert relevance(contact(poste='Responsable International')) == 0


def test_entreprise_connue_sans_faux_positif():
    assert relevance(contact(entreprise='Orange')) == WEIGHTS['known_company']
    assert relevance(contact(entreprise='Orangerie Conseil')) == 0
    assert relevance(contact(entreprise='Keyrus')) == 0  # contient « ey »
    assert relevance(contact(entreprise='BNP Paribas Cardif')) == WEIGHTS['known_company']


def test_les_criteres_se_cumulent():
    full = contact(poste='CFO', entreprise='Sanofi', linkedin='https://x', type_contact='alumni', amene_par='A B')
    expected = sum(WEIGHTS[k] for k in ('senior', 'linkedin', 'known_company', 'alumni', 'introduced'))
    assert relevance(full) == expected


def test_rank_trie_et_limite():
    contacts = [contact(poste='Assistant', id='a'), contact(poste='CEO', linkedin='x', id='b'),
                contact(poste='Responsable', id='c')]
    assert [c['id'] for c in rank(contacts)] == ['b', 'c', 'a']
    assert len(rank(contacts, limit=2)) == 2
