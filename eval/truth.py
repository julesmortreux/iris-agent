"""Vérité terrain : pertinence d'un contact pour un cas, calculée depuis les attributs cachés.

Les attributs (secteur réel, fonction, niveau hiérarchique, pays) viennent du générateur
de données. L'agent ne les voit pas et son score ne les utilise pas : l'évaluation ne
reprend donc pas les règles de ce qu'elle mesure.

Note de pertinence d'un contact pour un cas :
- 2 : répond exactement à la demande (bonne entité, bonne fonction, poste de direction, en France) ;
- 1 : acceptable (bonne entité, mais autre fonction, cadre intermédiaire, filiale ou poste à l'étranger) ;
- 0 : hors cible (autre entreprise ou autre secteur, poste de support, contact injoignable).
"""

import json
import unicodedata
from pathlib import Path

TRUTH: dict[str, dict] = json.loads((Path(__file__).parent / 'ground_truth.json').read_text(encoding='utf-8'))
LEADERS = ('c_level', 'directeur')


def fold(text: str) -> str:
    text = unicodedata.normalize('NFD', text or '')
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn').lower()


def grade(contact_id: str, spec: dict) -> int:
    """Note 0, 1 ou 2 du contact pour la cible `spec` d'un cas (company, sector, name, function, abroad)."""
    t = TRUTH.get(contact_id)
    if t is None or not t['reachable']:
        return 0
    subsidiary = False
    if 'company' in spec:
        if t['company'] != spec['company']:
            if t['parent_company'] != spec['company']:
                return 0
            subsidiary = True
    if 'sector' in spec and t['sector'] != spec['sector']:
        return 0
    if 'name' in spec and fold(spec['name']) not in fold(t['name']):
        return 0
    if 'name' in spec:
        return 2
    if t['level'] == 'support':
        return 0
    exact = (
        t['level'] in LEADERS
        and ('function' not in spec or t['function'] in spec['function'])
        and not subsidiary
        and (t['country'] == 'France' or spec.get('abroad', False))
    )
    return 2 if exact else 1


def graded(spec: dict) -> dict[str, int]:
    """Tous les contacts de note non nulle pour une cible."""
    grades = {cid: grade(cid, spec) for cid in TRUTH}
    return {cid: g for cid, g in grades.items() if g}
