"""Client asynchrone de l'API legacy : recherche de contacts et de chasseurs de tête."""

import asyncio
import logging
import random
from typing import Literal, Optional
from urllib.parse import urlparse

import httpx

from backend import config
from backend.scoring import MAX_CONTACTS, SECTOR_COMPANIES, rank

logger = logging.getLogger(__name__)

SECTOR_LIMIT_PER_COMPANY = 20
HTTP_TIMEOUT = httpx.Timeout(connect=5.0, read=30.0, write=10.0, pool=5.0)

# Ordre du lot transmis au modèle. `score` est le comportement du produit ;
# `api` et `random` servent de points de comparaison dans l'évaluation.
Ranking = Literal['score', 'api', 'random']

_client: Optional[httpx.AsyncClient] = None
_client_loop: Optional[asyncio.AbstractEventLoop] = None


def _http() -> httpx.AsyncClient:
    """Client HTTP partagé, recréé si la boucle asyncio a changé (un client est lié à sa boucle)."""
    global _client, _client_loop
    loop = asyncio.get_running_loop()
    if _client is None or _client_loop is not loop:
        headers = {'Accept': 'application/json'}
        cookies = None
        if config.LEGACY_API_TOKEN:
            headers['Authorization'] = f'Bearer {config.LEGACY_API_TOKEN}'
        else:
            domain = urlparse(config.LEGACY_API_BASE_URL).hostname
            cookies = httpx.Cookies()
            cookies.set('auth_token', config.LEGACY_API_SESSION, domain=domain)
        _client = httpx.AsyncClient(base_url=config.LEGACY_API_BASE_URL, headers=headers,
                                    cookies=cookies, timeout=HTTP_TIMEOUT)
        _client_loop = loop
    return _client


async def _get(path: str, params: Optional[dict] = None):
    response = await _http().get(path, params=params)
    response.raise_for_status()
    return response.json()


async def _get_list(path: str, params: dict) -> list[dict]:
    data = await _get(path, params)
    return data if isinstance(data, list) else []


# Contacts

_MEMBER_TYPES = {'ACTIVE_MEMBER': 'client_actuel', 'MEMBER': 'client_actuel', 'ALUMNI_MEMBER': 'alumni'}


def map_contact(raw: dict) -> dict:
    """Convertit un contact de GET /contact (format imbriqué) en fiche plate."""
    name = (raw.get('mainName') or {}).get('name') or {}
    job = (raw.get('currentJob') or {}).get('job') or {}
    contact = {
        'id': raw.get('id', ''),
        'prenom': name.get('first', ''),
        'nom': name.get('last', ''),
        'poste': (job.get('title') or {}).get('name', ''),
        'entreprise': (job.get('company') or {}).get('name', ''),
        'localisation': (job.get('location') or {}).get('city', ''),
        'email': '',
        'telephone': '',
        'linkedin': '',
        'type_contact': _MEMBER_TYPES.get((raw.get('user') or {}).get('memberType'), 'contact_reseau'),
    }

    for info in raw.get('infos', []):
        kind = info.get('type')
        if kind == 'ContactNameInfo' and not (contact['prenom'] or contact['nom']):
            n = info.get('name') or {}
            contact['prenom'], contact['nom'] = n.get('first', ''), n.get('last', '')
        elif kind == 'ContactJobInfo' and info.get('isCurrent') and not contact['poste']:
            j = info.get('job') or {}
            contact['poste'] = (j.get('title') or {}).get('name', '')
            contact['entreprise'] = contact['entreprise'] or (j.get('company') or {}).get('name', '')
            contact['localisation'] = contact['localisation'] or (j.get('location') or {}).get('city', '')
        elif kind == 'ContactEmailInfo' and not contact['email']:
            contact['email'] = info.get('email', '')
        elif kind == 'ContactPhoneInfo' and not contact['telephone']:
            num = info.get('number') or {}
            number, code = num.get('number', ''), num.get('countryCode')
            if number:
                contact['telephone'] = f'0{number}' if code == 33 else (f'+{code} {number}' if code else number)
        elif kind == 'ContactLinkedinInfo' and not contact['linkedin']:
            contact['linkedin'] = info.get('linkedinUrl', '')
        elif kind == 'ContactLocationInfo' and not contact['localisation']:
            contact['localisation'] = (info.get('location') or {}).get('city', '')

    introducers: list[str] = []
    for connection in raw.get('connections', []):
        label = ((connection.get('user') or {}).get('label') or '').strip()
        if label and label not in introducers:
            introducers.append(label)
    contact['amene_par'] = ', '.join(introducers)
    return contact


async def _fetch_contacts(params: dict, refresh: bool) -> list[dict]:
    """Profils avec LinkedIn d'abord ; sans ce filtre si la recherche ne renvoie rien."""
    linkedin_only = {**params, 'withLinkedinProfile': 'true'}
    if refresh:
        try:
            items = await _get_list('/contact', {**linkedin_only, 'refresh': 'true'})
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Enrichissement indisponible, recherche sans enrichissement : %s", exc)
            items = await _get_list('/contact', linkedin_only)
    else:
        items = await _get_list('/contact', linkedin_only)
    return items or await _get_list('/contact', params)


async def _fetch_sector(sector: str, params: dict) -> list[dict]:
    """Une requête par entreprise du secteur, lancées en parallèle puis dédoublonnées."""
    async def fetch(company: str) -> list[dict]:
        try:
            return await _get_list('/contact', {**params, 'company': company, 'limit': SECTOR_LIMIT_PER_COMPANY})
        except (httpx.HTTPError, ValueError) as exc:
            logger.warning("Recherche %s / %s en échec : %s", sector, company, exc)
            return []

    batches = await asyncio.gather(*(fetch(company) for company in SECTOR_COMPANIES[sector]))
    unique: dict[str, dict] = {}
    for item in (i for batch in batches for i in batch):
        if item.get('id'):
            unique.setdefault(item['id'], item)
    return list(unique.values())


async def search_contacts(
    name: Optional[str] = None,
    position: Optional[str] = None,
    company: Optional[str] = None,
    sector: Optional[str] = None,
    refresh: bool = False,
    ranking: Ranking = 'score',
) -> list[dict]:
    """Recherche des contacts et renvoie au plus MAX_CONTACTS fiches, classées selon `ranking`.

    `refresh` active l'enrichissement des coordonnées, que l'API limite à 10 résultats.
    """
    params = {key: value for key, value in (('name', name), ('position', position)) if value}
    if sector in SECTOR_COMPANIES and not company:
        items = (await _fetch_sector(sector, {**params, 'withLinkedinProfile': 'true'})
                 or await _fetch_sector(sector, params))
    else:
        if company:
            params['company'] = company
        items = await _fetch_contacts({**params, 'limit': MAX_CONTACTS}, refresh)

    contacts = [map_contact(item) for item in items]
    if ranking == 'score':
        contacts = rank(contacts)
    elif ranking == 'random':
        random.Random(len(contacts)).shuffle(contacts)
    contacts = contacts[:MAX_CONTACTS]
    logger.info("search_contacts(%s, secteur=%s) : %d contacts", params, sector, len(contacts))
    return contacts


# Chasseurs de tête

def map_hunter(raw: dict) -> dict:
    """Convertit un cabinet de GET /hunter en fiche plate."""
    contact = raw.get('contact') or {}
    firm = raw.get('firm') or {}
    name = (contact.get('mainName') or {}).get('name') or {}
    email = phone = ''
    for info in contact.get('infos', []):
        if info.get('type') == 'ContactEmailInfo':
            email = info.get('email', '')
        elif info.get('type') == 'ContactPhoneInfo':
            phone = (info.get('number') or {}).get('number', '')
    return {
        'id': raw.get('id', ''),
        'cabinet': firm.get('name', ''),
        'contact_principal': f"{name.get('first', '')} {name.get('last', '')}".strip(),
        'specialites': [f.get('name', '') for f in raw.get('functions', [])],
        'secteurs': [s.get('name', '') for s in raw.get('sectors', [])],
        'email': email,
        'telephone': phone or (firm.get('phones') or [{}])[0].get('number', ''),
    }


async def search_hunters(name: Optional[str] = None) -> list[dict]:
    """Chasseurs de tête de la première page de GET /hunter, filtrés par nom si fourni."""
    data = await _get('/hunter', {'name': name} if name else None)
    items = data.get('items', []) if isinstance(data, dict) else data
    return [map_hunter(item) for item in items or []]
