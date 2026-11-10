"""Génère les données fictives servies par la fausse API et la vérité terrain de l'évaluation.

Usage : python -m legacy_api.generate_data

La graine est fixe : deux exécutions produisent exactement les mêmes fichiers.
- legacy_api/data/contacts.json et hunters.json : ce que l'API expose, au format imbriqué.
- eval/ground_truth.json : les attributs cachés de chaque contact (secteur, niveau,
  fonction, pays). L'API ne les expose pas et l'agent ne les voit jamais : ils servent
  uniquement à calculer les métriques, sans dépendre des règles du score évalué.
"""

import json
import random
import uuid
from pathlib import Path

SEED = 20261112
N_CONTACTS = 500
ROOT = Path(__file__).resolve().parent.parent

# (entreprise, secteur réel, nombre de contacts, maison-mère si filiale)
COMPANIES = [
    ('Sopra Steria', 'tech', 26, None), ('Sopra Steria Next', 'tech', 6, 'Sopra Steria'),
    ('Atos', 'tech', 8, None), ('Dassault Systèmes', 'tech', 8, None), ('Microsoft', 'tech', 8, None),
    ('Google', 'tech', 10, None), ('SAP', 'tech', 5, None), ('Thoughtworks', 'tech', 6, None),
    ('TotalEnergies', 'energie', 22, None), ('EDF', 'energie', 14, None), ('Engie', 'energie', 12, None),
    ('Veolia', 'energie', 8, None), ('Schneider Electric', 'energie', 8, None),
    ('BNP Paribas', 'banque', 24, None), ('BNP Paribas Cardif', 'banque', 6, 'BNP Paribas'),
    ('Société Générale', 'banque', 14, None), ('Crédit Agricole', 'banque', 10, None), ('Natixis', 'banque', 6, None),
    ('LVMH', 'luxe', 18, None), ('Kering', 'luxe', 8, None), ('Hermès', 'luxe', 6, None), ('Chanel', 'luxe', 6, None),
    ('Airbus', 'defense', 22, None), ('Thales', 'defense', 10, None), ('Safran', 'defense', 10, None),
    ('Dassault Aviation', 'defense', 5, None),
    ('Renault', 'automobile', 14, None), ('Stellantis', 'automobile', 12, None), ('Valeo', 'automobile', 6, None),
    ('Sanofi', 'pharma', 14, None), ('Servier', 'pharma', 5, None), ('Ipsen', 'pharma', 4, None),
    ('Accenture', 'conseil', 8, None), ('Deloitte', 'conseil', 6, None), ('EY', 'conseil', 6, None),
    ('McKinsey', 'conseil', 4, None),
    ('AXA', 'assurance', 12, None), ('Allianz', 'assurance', 6, None),
    ('Orange', 'telecom', 12, None), ('Bouygues Telecom', 'telecom', 5, None),
    ('SNCF', 'transport', 8, None), ('Air France', 'transport', 8, None),
    ('Saint-Gobain', 'industrie', 8, None), ('Air Liquide', 'industrie', 8, None), ('Alstom', 'industrie', 6, None),
    ('Danone', 'agroalimentaire', 8, None), ('Pernod Ricard', 'agroalimentaire', 5, None),
    ('Nexity', 'immobilier', 5, None), ('Unibail', 'immobilier', 4, None),
]
# Petites sociétés peu connues, dont certaines piègent une recherche par sous-chaîne
# (« Orangerie » contient « orange », « Keyrus » contient « ey », « Metalor » contient « meta »).
SMALL_COMPANIES = [
    ('Orangerie Conseil', 'conseil'), ('Keyrus', 'tech'), ('Metalor', 'industrie'), ('Menuiseries Laval', 'industrie'),
    ('Freelance', 'conseil'), ('Cabinet Bertin', 'conseil'), ('Transports Morel', 'transport'),
    ('Biolab Ouest', 'pharma'), ('Domaine des Aulnes', 'agroalimentaire'), ('Studio Nord', 'tech'),
    ('Ateliers Rochefort', 'luxe'), ('Garage Lemoine', 'automobile'), ('Solaire du Midi', 'energie'),
    ('Courtage Vauban', 'assurance'), ('Pierre et Patrimoine', 'immobilier'),
]

# fonction -> niveau -> intitulés possibles
TITLES = {
    'finance': {
        'c_level': ['CFO', 'Chief Financial Officer', 'Directeur Administratif et Financier', 'DAF Groupe'],
        'directeur': ['Directeur Financier', 'Directrice Financière', 'Directeur du Contrôle de Gestion',
                      'Finance Director'],
        'manager': ['Responsable Comptabilité', 'Finance Manager', 'Responsable Trésorerie'],
        'support': ['Contrôleur de Gestion', 'Analyste Financier', 'Assistant Comptable'],
    },
    'rh': {
        'c_level': ['DRH Groupe', 'Chief Human Resources Officer', 'Directrice des Ressources Humaines Groupe'],
        'directeur': ['Directeur des Ressources Humaines', 'Directrice des Ressources Humaines', 'HR Director'],
        'manager': ['Responsable Ressources Humaines', 'HR Business Partner', 'Responsable Recrutement'],
        'support': ['Chargé de Recrutement', 'Chargée de Mission RH', 'Assistante RH'],
    },
    'direction': {
        'c_level': ['CEO', 'Président Directeur Général', 'Directeur Général', 'Directrice Générale',
                    'Président', 'Chief Executive Officer'],
        'directeur': ['Directeur Général Adjoint', 'Directeur de Business Unit', 'Managing Director',
                      'Directeur de la Stratégie'],
        'manager': ['Responsable de Programme', 'Chef de Projet Stratégie'],
        'support': ['Assistante de Direction', 'Chargé de Mission'],
    },
    'commercial': {
        'c_level': ['Chief Commercial Officer', 'Directeur Commercial Groupe'],
        'directeur': ['Directeur Commercial', 'Directrice Commerciale', 'Vice President Sales', 'Sales Director'],
        'manager': ['Responsable Grands Comptes', 'Key Account Manager', 'Responsable Commercial'],
        'support': ['Chargé de Clientèle', 'Assistant Commercial', 'Business Developer Junior'],
    },
    'operations': {
        'c_level': ['COO', 'Chief Operating Officer', 'Directeur des Opérations Groupe'],
        'directeur': ['Directeur des Opérations', 'Directeur Industriel', 'Directeur Supply Chain',
                      'Head of Operations'],
        'manager': ['Responsable de Production', 'Responsable Logistique', 'Operations Manager'],
        'support': ['Technicien Méthodes', 'Coordinateur Logistique', 'Opérateur de Production'],
    },
    'tech': {
        'c_level': ['CTO', 'Chief Technology Officer', 'Chief Information Officer', 'DSI Groupe'],
        'directeur': ['Directeur des Systèmes d\'Information', 'Directeur Technique', 'Head of Data',
                      'Directrice de l\'Innovation'],
        'manager': ['Responsable Infrastructure', 'Engineering Manager', 'Responsable Data'],
        'support': ['Analyste Données', 'Technicien Support', 'Développeur Junior'],
    },
    'marketing': {
        'c_level': ['CMO', 'Chief Marketing Officer'],
        'directeur': ['Directeur Marketing', 'Directrice de la Communication', 'Head of Brand'],
        'manager': ['Responsable Marketing', 'Brand Manager'],
        'support': ['Chargée de Communication', 'Assistant Marketing'],
    },
    'juridique': {
        'c_level': ['Secrétaire Général', 'Directeur Juridique Groupe'],
        'directeur': ['Directeur Juridique', 'Directrice Conformité'],
        'manager': ['Responsable Juridique'],
        'support': ['Juriste', 'Assistante Juridique'],
    },
}
FUNCTION_WEIGHTS = {'finance': 16, 'rh': 12, 'direction': 14, 'commercial': 16, 'operations': 16,
                    'tech': 14, 'marketing': 8, 'juridique': 4}
LEVEL_WEIGHTS = {'c_level': 12, 'directeur': 38, 'manager': 26, 'support': 24}

# (pays, marqueur ajouté à l'intitulé, ville)
FOREIGN = [
    ('Emirats arabes unis', 'Middle East', 'Dubaï'), ('Royaume-Uni', 'UK', 'Londres'),
    ('Singapour', 'Asia-Pacific', 'Singapour'), ('Etats-Unis', 'Americas', 'New York'),
    ('Belgique', 'Belux', 'Bruxelles'), ('Maroc', 'Afrique', 'Casablanca'), ('Allemagne', 'EMEA', 'Munich'),
]
FRENCH_CITIES = ['Paris', 'Paris', 'Paris', 'Lyon', 'Toulouse', 'Nantes', 'Lille', 'Bordeaux', 'Marseille']

FIRST_NAMES = [
    'Adèle', 'Alban', 'Amélie', 'Anselme', 'Apolline', 'Armand', 'Aurore', 'Baptiste', 'Bérénice', 'Blaise',
    'Capucine', 'Cédric', 'Clémence', 'Corentin', 'Daphné', 'Edgar', 'Eléonore', 'Emeric', 'Fanny', 'Florent',
    'Gaëlle', 'Gaspard', 'Héloïse', 'Hugo', 'Inès', 'Jérémie', 'Joséphine', 'Killian', 'Laure', 'Léandre',
    'Lison', 'Loïc', 'Maëlle', 'Marius', 'Mathilde', 'Maxence', 'Nadia', 'Noé', 'Océane', 'Octave',
    'Pauline', 'Quentin', 'Rachel', 'Raphaël', 'Sabine', 'Samir', 'Solène', 'Tanguy', 'Théodora', 'Titouan',
    'Ulysse', 'Valentine', 'Victor', 'Yasmine', 'Yann', 'Zoé',
]
LAST_NAMES = [
    'Abadie', 'Arnoux', 'Bachelet', 'Barthes', 'Bellamy', 'Bertrand', 'Besnard', 'Bouvier', 'Brunel', 'Carlier',
    'Castel', 'Chabert', 'Charpentier', 'Colas', 'Cordier', 'Courtois', 'Delattre', 'Delmas', 'Deschamps',
    'Drouet', 'Dubreuil', 'Dufresne', 'Estève', 'Fabre', 'Ferrand', 'Fontaine', 'Gaillard', 'Garnier', 'Gauthier',
    'Gilbert', 'Guérin', 'Hamon', 'Henry', 'Jacquet', 'Joubert', 'Lacroix', 'Lagarde', 'Lambert', 'Langlois',
    'Lebrun', 'Leclerc', 'Lefort', 'Maillard', 'Marchetti', 'Mercier', 'Meunier', 'Monnier', 'Navarro', 'Noël',
    'Pasquier', 'Perrot', 'Picard', 'Poirier', 'Prévost', 'Renaud', 'Rigal', 'Rousseau', 'Sabatier', 'Seguin',
    'Tessier', 'Thibault', 'Vasseur', 'Verdier', 'Vidal',
]
MALE_FIRST_NAMES = {
    'Alban', 'Anselme', 'Armand', 'Baptiste', 'Blaise', 'Cédric', 'Corentin', 'Edgar', 'Emeric', 'Florent',
    'Gaspard', 'Hugo', 'Jérémie', 'Killian', 'Léandre', 'Loïc', 'Marius', 'Maxence', 'Noé', 'Octave', 'Quentin',
    'Raphaël', 'Samir', 'Tanguy', 'Titouan', 'Ulysse', 'Victor', 'Yann',
}
_MASCULINE = {'Directrice': 'Directeur', 'Chargée': 'Chargé', 'Assistante': 'Assistant', 'Générale': 'Général',
              'Financière': 'Financier', 'Commerciale': 'Commercial'}
MEMBER_NAMES = ['Paul MARTINEAU', 'Hélène ROUX', 'Bruno CAZALS', 'Sophie LEGRAND', 'Marc PELLETIER',
                'Claire DUVAL', 'Antoine BERGER', 'Nathalie FOREST', 'Julien MARCHAND', 'Isabelle CORNU']

HUNTER_FIRMS = [
    'Arcane Executive', 'Haussmann Search', 'Cabinet Voltaire', 'Meridienne Conseil', 'Lumen Partners',
    'Atelier des Talents', 'Belvédère Search', 'Cap Dirigeants', 'Sillage RH', 'Eclipse Executive',
    'Grand Large Search', 'Horizon Cadres', 'Kairos Talents', 'Latitude Executive', 'Maison Carrée Search',
    'Néo Dirigeants', 'Olympe Conseil', 'Passerelle Executive', 'Quai des Talents', 'Rive Gauche Search',
    'Solstice Partners', 'Trajectoire Dirigeants', 'Ulysse Executive', 'Vendôme Search', 'Zénith Talents',
    'Alizé Conseil', 'Boussole RH', 'Cime Executive', 'Delta Dirigeants', 'Equinoxe Search',
]

# Contacts imposés, cités par leur nom dans le jeu d'évaluation.
ANCHORS = [
    dict(first='Héloïse', last='Marchetti', company='Sanofi', function='rh', level='c_level',
         title='DRH Groupe', linkedin=True, phone=True, member='ALUMNI_MEMBER'),
    dict(first='Octave', last='Verdier', company='LVMH', function='finance', level='directeur',
         title='Directeur Financier', linkedin=True, phone=False, member=None),
    dict(first='Yasmine', last='Abadie', company='Sopra Steria', function='direction', level='directeur',
         title='Managing Director', linkedin=True, phone=True, member='ALUMNI_MEMBER'),
]


def _uuid(rng):
    return str(uuid.UUID(int=rng.getrandbits(128), version=4))


def _pick(rng, weights):
    return rng.choices(list(weights), weights=list(weights.values()))[0]


def _slug(text):
    table = str.maketrans('àâäéèêëîïôöùûüç', 'aaaeeeeiioouuuc')
    return ''.join(c for c in text.lower().translate(table) if c.isalnum() or c == '-')


def build_contacts(rng):
    slots = []
    for name, sector, count, parent in COMPANIES:
        slots += [(name, sector, parent)] * count
    while len(slots) < N_CONTACTS - len(ANCHORS):
        name, sector = rng.choice(SMALL_COMPANIES)
        slots.append((name, sector, None))
    rng.shuffle(slots)
    sector_of = {name: (sector, parent) for name, sector, _, parent in COMPANIES}

    people = []
    for anchor in ANCHORS:
        sector, parent = sector_of[anchor['company']]
        people.append(dict(anchor, sector=sector, parent=parent, country='France', marker=None,
                           city='Paris', email=False))
    for company, sector, parent in slots:
        function = _pick(rng, FUNCTION_WEIGHTS)
        level = _pick(rng, LEVEL_WEIGHTS)
        country, marker, city = 'France', None, rng.choice(FRENCH_CITIES)
        if rng.random() < 0.22:
            country, marker, city = rng.choice(FOREIGN)
        linkedin = rng.random() < 0.25
        people.append(dict(
            first=rng.choice(FIRST_NAMES), last=rng.choice(LAST_NAMES), company=company, sector=sector,
            parent=parent, function=function, level=level, title=rng.choice(TITLES[function][level]),
            country=country, marker=marker, city=city, linkedin=linkedin,
            phone=rng.random() < (0.25 if linkedin else 0.02), email=rng.random() < 0.03,
            member=rng.choices(['ALUMNI_MEMBER', 'ACTIVE_MEMBER', 'NON_MEMBER', None], weights=[4, 2, 30, 64])[0],
        ))

    # Garanties utiles aux cas d'évaluation.
    for p in people:
        # Piège : aucun dirigeant financier d'Airbus n'est joignable.
        if p['company'] == 'Airbus' and p['function'] == 'finance' and p['level'] in ('c_level', 'directeur'):
            p.update(linkedin=False, phone=False, email=False)
    for company, minimum in (('Airbus', 9), ('Sopra Steria', 12), ('BNP Paribas', 10), ('TotalEnergies', 9)):
        pool = [p for p in people if p['company'] == company and p['level'] in ('c_level', 'directeur')
                and not (company == 'Airbus' and p['function'] == 'finance')]
        for p in pool[:minimum]:
            p['linkedin'] = True

    contacts, truth = [], {}
    for p in people:
        cid = _uuid(rng)
        title = p['title']
        if p['first'] in MALE_FIRST_NAMES:
            title = ' '.join(_MASCULINE.get(word, word) for word in title.split())
        if p['marker']:
            title = f"{title} {p['marker']}"
        infos = []
        if p['linkedin']:
            infos.append({'type': 'ContactLinkedinInfo',
                          'linkedinUrl': f"https://www.linkedin.com/in/{_slug(p['first'])}-{_slug(p['last'])}-{cid[:6]}"})
        if p['phone']:
            infos.append({'type': 'ContactPhoneInfo', 'tag': 'mobile',
                          'number': {'countryCode': 33, 'number': f"6{rng.randrange(10**7, 10**8)}"}})
        if p['email']:
            infos.append({'type': 'ContactEmailInfo',
                          'email': f"{_slug(p['first'])}.{_slug(p['last'])}@exemple.fr"})
        past_company = None
        if rng.random() < 0.06:  # ancien poste : le filtre `company` de l'API le prend aussi en compte
            past_company = rng.choice([c[0] for c in COMPANIES if c[0] != p['company']])
            infos.append({'type': 'ContactJobInfo', 'isCurrent': False,
                          'job': {'title': {'name': 'Directeur de Projet'}, 'company': {'name': past_company}}})
        contacts.append({
            'id': cid,
            'mainName': {'name': {'first': p['first'], 'last': p['last']}},
            'currentJob': {'isCurrent': True, 'job': {
                'title': {'name': title}, 'company': {'name': p['company']},
                'location': {'city': p['city'], 'country': {'name': p['country']}},
            }},
            'user': {'memberType': p['member']} if p['member'] else None,
            'infos': infos,
            'connections': [{'user': {'label': label}}
                            for label in rng.sample(MEMBER_NAMES, k=rng.choice([1, 1, 2, 3]))],
        })
        truth[cid] = {
            'name': f"{p['first']} {p['last']}", 'title': title, 'company': p['company'],
            'parent_company': p['parent'], 'sector': p['sector'], 'function': p['function'],
            'level': p['level'], 'country': p['country'], 'member_type': p['member'],
            'reachable': bool(p['linkedin'] or p['phone'] or p['email']), 'past_company': past_company,
        }
    order = list(range(len(contacts)))
    rng.shuffle(order)  # l'API renvoie les contacts sans ordre de pertinence
    return [contacts[i] for i in order], truth


def build_hunters(rng):
    hunters = []
    for firm in HUNTER_FIRMS:
        hunters.append({
            'id': _uuid(rng),
            'contact': {'mainName': {'name': {'first': rng.choice(FIRST_NAMES), 'last': rng.choice(LAST_NAMES)}},
                        'infos': []},
            'firm': {'name': firm, 'phones': [{'number': f"01{rng.randrange(10**7, 10**8)}"}],
                     'address': {'city': rng.choice(FRENCH_CITIES)}},
            'functions': [],  # jamais renseigné dans les données d'origine
            'sectors': [],
        })
    return hunters


def main():
    rng = random.Random(SEED)
    contacts, truth = build_contacts(rng)
    hunters = build_hunters(rng)
    outputs = {
        ROOT / 'legacy_api' / 'data' / 'contacts.json': contacts,
        ROOT / 'legacy_api' / 'data' / 'hunters.json': hunters,
        ROOT / 'eval' / 'ground_truth.json': truth,
    }
    for path, data in outputs.items():
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, ensure_ascii=False, indent=1), encoding='utf-8', newline='\n')
    reachable = sum(t['reachable'] for t in truth.values())
    print(f"{len(contacts)} contacts ({reachable} joignables), {len(hunters)} cabinets")


if __name__ == '__main__':
    main()
