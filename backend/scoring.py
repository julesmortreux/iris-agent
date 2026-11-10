"""Score de pertinence déterministe des contacts.

L'API renvoie les contacts sans ordre utile. Ce score les classe avant que le
modèle ne choisisse : il est gratuit, instantané, testable et explicable au client.
"""

import re

MAX_CONTACTS = 60  # taille du lot classé transmis au modèle

# Un secteur est recherché via ses principales entreprises : l'API ne filtre pas par secteur.
SECTOR_COMPANIES: dict[str, list[str]] = {
    'energie': ['énergie', 'Engie', 'EDF', 'TotalEnergies', 'Shell', 'Veolia', 'Schneider Electric'],
    'tech': ['tech', 'Google', 'Microsoft', 'Amazon', 'Meta', 'Apple', 'SAP', 'Dassault Systèmes',
             'Sopra Steria', 'Atos'],
    'luxe': ['luxe', 'LVMH', 'Kering', 'Hermès', 'Chanel', 'Dior', 'Cartier', 'Richemont'],
    'banque': ['banque', 'BNP', 'Société Générale', 'Crédit Agricole', 'Natixis', 'HSBC', 'Goldman'],
    'automobile': ['auto', 'Renault', 'Stellantis', 'Peugeot', 'Volkswagen', 'BMW', 'Mercedes', 'Valeo'],
    'pharma': ['pharma', 'Sanofi', 'Servier', 'Pfizer', 'Roche', 'Novartis', 'AstraZeneca', 'Ipsen'],
    'industrie': ['industrie', 'Saint-Gobain', 'Safran', 'Alstom', 'Legrand', 'Air Liquide'],
    'conseil': ['conseil', 'consulting', 'McKinsey', 'BCG', 'Bain', 'Accenture', 'Deloitte', 'EY', 'PwC', 'KPMG'],
    'immobilier': ['immobilier', 'Nexity', 'Bouygues Immobilier', 'Unibail', 'Gecina'],
    'assurance': ['assurance', 'AXA', 'Allianz', 'Generali', 'Groupama', 'AG2R'],
    'telecom': ['telecom', 'Orange', 'SFR', 'Bouygues Telecom', 'Free', 'Iliad', 'Nokia'],
    'agroalimentaire': ['agro', 'alimentaire', 'Danone', 'Nestlé', 'Lactalis', 'Pernod Ricard', 'Bonduelle'],
    'transport': ['transport', 'SNCF', 'Air France', 'CMA CGM', 'Geodis', 'Bolloré'],
    'defense': ['défense', 'Thales', 'Dassault Aviation', 'Naval Group', 'MBDA', 'Nexter'],
    'sante': ['santé', 'Sanofi', 'Roche', 'Medtronic', 'Siemens Health'],
}
_GENERIC_TERMS = {
    'énergie', 'tech', 'luxe', 'banque', 'auto', 'pharma', 'industrie', 'conseil', 'consulting',
    'immobilier', 'assurance', 'telecom', 'agro', 'alimentaire', 'transport', 'défense', 'santé',
}

_SENIOR = (
    'ceo', 'cfo', 'coo', 'cto', 'cmo', 'cio', 'cdo', 'pdg', 'daf', 'drh', 'dsi',
    'président', 'president', 'chairman', 'managing director', 'managing partner',
    'directeur', 'directrice', 'director', 'vice-président', 'vice president', 'vice-president',
    'vp', 'evp', 'svp', 'head of', 'chief', 'fondateur', 'fondatrice', 'founder', 'co-founder',
    'associé', 'partner', 'gérant', 'administrateur', 'board member', 'secrétaire général',
)
_JUNIOR = (
    'assistant', 'coordinateur', 'coordinatrice', 'coordinator', 'controller', 'contrôleur',
    'analyst', 'analyste', 'technicien', 'technician', 'stagiaire', 'apprenti', 'intern',
    'opérateur', 'operator', 'superviseur', 'supervisor', 'chargé', 'spécialiste', 'specialist',
    'employé', 'employee', 'junior', 'juriste',
)

WEIGHTS = {'senior': 8, 'junior': -6, 'linkedin': 10, 'known_company': 6,
           'alumni': 9, 'client_actuel': 5, 'introduced': 1}


def _words_re(words, suffixes: str = r'(?:e|s|es)?') -> re.Pattern:
    """Mots entiers (accords compris), pour ne pas trouver « intern » dans « international »."""
    return re.compile(r'\b(?:' + '|'.join(map(re.escape, words)) + r')' + suffixes + r'\b', re.IGNORECASE)


_SENIOR_RE = _words_re(_SENIOR)
_JUNIOR_RE = _words_re(_JUNIOR)
_KNOWN_COMPANY_RE = _words_re(
    {c for companies in SECTOR_COMPANIES.values() for c in companies} - _GENERIC_TERMS, suffixes=''
)


def relevance(contact: dict) -> int:
    """Score d'un contact : séniorité du poste, LinkedIn, entreprise connue, statut dans le réseau."""
    poste = contact.get('poste') or ''
    score = 0
    if _SENIOR_RE.search(poste):
        score += WEIGHTS['senior']
    elif _JUNIOR_RE.search(poste):
        score += WEIGHTS['junior']
    if contact.get('linkedin'):
        score += WEIGHTS['linkedin']
    if _KNOWN_COMPANY_RE.search(contact.get('entreprise') or ''):
        score += WEIGHTS['known_company']
    score += WEIGHTS.get(contact.get('type_contact', ''), 0)
    if contact.get('amene_par'):
        score += WEIGHTS['introduced']
    return score


def rank(contacts: list[dict], limit: int = MAX_CONTACTS) -> list[dict]:
    """Classe par score décroissant (tri stable) et garde les `limit` premiers."""
    return sorted(contacts, key=relevance, reverse=True)[:limit]
