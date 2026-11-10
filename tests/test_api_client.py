from backend.api_client import map_contact, map_hunter

RAW = {
    'id': 'c-1',
    'mainName': {'name': {'first': 'Adèle', 'last': 'Fontaine'}},
    'currentJob': {'isCurrent': True, 'job': {'title': {'name': 'CFO'}, 'company': {'name': 'Sanofi'},
                                              'location': {'city': 'Paris'}}},
    'user': {'memberType': 'ALUMNI_MEMBER'},
    'infos': [
        {'type': 'ContactLinkedinInfo', 'linkedinUrl': 'https://www.linkedin.com/in/adele'},
        {'type': 'ContactPhoneInfo', 'number': {'countryCode': 33, 'number': '612345678'}},
        {'type': 'ContactJobInfo', 'isCurrent': False, 'job': {'title': {'name': 'DAF'}, 'company': {'name': 'AXA'}}},
    ],
    'connections': [{'user': {'label': 'Paul MARTINEAU'}}, {'user': {'label': 'Paul MARTINEAU'}},
                    {'user': {'label': ' Hélène ROUX '}}],
}


def test_map_contact_aplatit_le_format_imbrique():
    c = map_contact(RAW)
    assert (c['prenom'], c['nom'], c['poste'], c['entreprise']) == ('Adèle', 'Fontaine', 'CFO', 'Sanofi')
    assert c['linkedin'].endswith('/adele')
    assert c['telephone'] == '0612345678'
    assert c['type_contact'] == 'alumni'
    assert c['amene_par'] == 'Paul MARTINEAU, Hélène ROUX'  # dédoublonné, espaces retirés


def test_map_contact_ignore_les_anciens_postes():
    assert map_contact(RAW)['entreprise'] == 'Sanofi'


def test_map_contact_supporte_les_champs_absents():
    c = map_contact({'id': 'c-2', 'user': None, 'infos': []})
    assert c['id'] == 'c-2' and c['prenom'] == '' and c['type_contact'] == 'contact_reseau'


def test_map_contact_telephone_etranger():
    raw = {'id': 'c-3', 'infos': [{'type': 'ContactPhoneInfo', 'number': {'countryCode': 44, 'number': '7700900'}}]}
    assert map_contact(raw)['telephone'] == '+44 7700900'


def test_map_hunter():
    raw = {'id': 'h-1', 'contact': {'mainName': {'name': {'first': 'Jeanne', 'last': 'Morel'}}, 'infos': []},
           'firm': {'name': 'Arcane Executive', 'phones': [{'number': '0140000000'}]}, 'functions': [], 'sectors': []}
    h = map_hunter(raw)
    assert h['cabinet'] == 'Arcane Executive' and h['contact_principal'] == 'Jeanne Morel'
    assert h['telephone'] == '0140000000' and h['specialites'] == []
