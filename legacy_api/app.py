"""Fausse API « legacy » : reproduit les contraintes de l'API de la plateforme d'origine.

Ce service remplace l'API réelle, confidentielle. Il en garde les limites, parce que
ce sont elles qui ont dicté la conception de l'agent :
- recherche par sous-chaîne sur le nom, le poste et l'entreprise, sans filtre par secteur ;
- résultats renvoyés sans ordre de pertinence, tronqués par `limit` ;
- `refresh=true` (enrichissement des coordonnées) limite la réponse à 10 résultats ;
- authentification par jeton Bearer ou par cookies de session ;
- cabinets de chasseurs de tête sans spécialité ni secteur renseignés.

Lancement : python -m legacy_api.app
"""

import json
import os
import time
import unicodedata
from pathlib import Path

from flask import Flask, jsonify, request

DATA = Path(__file__).resolve().parent / 'data'
API_TOKEN = os.getenv('LEGACY_API_TOKEN', 'demo-token')
SESSION_COOKIE = os.getenv('LEGACY_API_SESSION', 'demo-session')
LATENCY_MS = int(os.getenv('LEGACY_API_LATENCY_MS', '0'))
REFRESH_LIMIT = 10
PAGE_SIZE = 50

app = Flask(__name__)
CONTACTS = json.loads((DATA / 'contacts.json').read_text(encoding='utf-8'))
HUNTERS = json.loads((DATA / 'hunters.json').read_text(encoding='utf-8'))


def _fold(text):
    """Minuscules sans accents, pour une recherche par sous-chaîne tolérante."""
    text = unicodedata.normalize('NFD', text or '')
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn').lower()


def _job_fields(contact):
    """Postes et entreprises du contact, poste actuel et anciens postes confondus."""
    jobs = [(contact.get('currentJob') or {}).get('job') or {}]
    jobs += [i.get('job') or {} for i in contact['infos'] if i.get('type') == 'ContactJobInfo']
    titles = [_fold((j.get('title') or {}).get('name')) for j in jobs]
    companies = [_fold((j.get('company') or {}).get('name')) for j in jobs]
    return titles, companies


def _has_linkedin(contact):
    return any(i.get('type') == 'ContactLinkedinInfo' for i in contact['infos'])


def _enrich(contact):
    """Simule l'enrichissement : ajoute un mobile aux contacts qui ont un profil LinkedIn."""
    if not _has_linkedin(contact) or any(i.get('type') == 'ContactPhoneInfo' for i in contact['infos']):
        return contact
    digits = int(contact['id'].replace('-', '')[:7], 16) % 10**8
    phone = {'type': 'ContactPhoneInfo', 'tag': 'mobile', 'number': {'countryCode': 33, 'number': f'6{digits:08d}'}}
    return {**contact, 'infos': contact['infos'] + [phone]}


@app.before_request
def _gate():
    if LATENCY_MS:
        time.sleep(LATENCY_MS / 1000)
    bearer = request.headers.get('Authorization', '') == f'Bearer {API_TOKEN}'
    session = request.cookies.get('auth_token') == SESSION_COOKIE
    if not (bearer or session):
        return jsonify({'error': 'Unauthorized'}), 401
    return None


@app.get('/api/contact')
def contacts():
    name = _fold(request.args.get('name'))
    position = _fold(request.args.get('position'))
    company = _fold(request.args.get('company'))
    member_type = request.args.get('memberType')
    with_linkedin = request.args.get('withLinkedinProfile') == 'true'
    refresh = request.args.get('refresh') == 'true'
    try:
        limit = int(request.args['limit']) if 'limit' in request.args else None
    except ValueError:
        return jsonify({'error': 'limit must be an integer'}), 400

    results = []
    for contact in CONTACTS:
        full_name = contact['mainName']['name']
        titles, companies = _job_fields(contact)
        if name and name not in _fold(f"{full_name['first']} {full_name['last']}"):
            continue
        if position and not any(position in t for t in titles):
            continue
        if company and not any(company in c for c in companies):
            continue
        if member_type and (contact.get('user') or {}).get('memberType') != member_type:
            continue
        if with_linkedin and not _has_linkedin(contact):
            continue
        results.append(contact)

    if refresh:
        results = [_enrich(c) for c in results[:REFRESH_LIMIT]]
    if limit is not None:
        results = results[:limit]
    return jsonify(results)


@app.get('/api/hunter')
def hunters():
    name = _fold(request.args.get('name'))
    page = int(request.args.get('pageToken') or 0)
    results = [h for h in HUNTERS if not name or name in _fold(h['firm']['name'])]
    start = page * PAGE_SIZE
    next_token = str(page + 1) if start + PAGE_SIZE < len(results) else None
    return jsonify({'items': results[start:start + PAGE_SIZE], 'nextPageToken': next_token})


if __name__ == '__main__':
    app.run(host='127.0.0.1', port=int(os.getenv('LEGACY_API_PORT', '5001')))
