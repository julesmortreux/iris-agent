"""Configuration lue depuis l'environnement (fichier .env à la racine en local)."""

import os

from dotenv import load_dotenv

load_dotenv()
os.environ.setdefault('PYDANTIC_AI_NO_BANNER', '1')


def _flag(name: str, default: str = 'false') -> bool:
    return os.getenv(name, default).strip().lower() == 'true'


MISTRAL_API_KEY = os.getenv('MISTRAL_API_KEY', '')
# Versions datées plutôt que « -latest » : un alias change sans prévenir et rend
# deux évaluations incomparables.
MISTRAL_MODEL = os.getenv('MISTRAL_MODEL', 'ministral-8b-2512')
MISTRAL_CHAT_MODEL = os.getenv('MISTRAL_CHAT_MODEL', 'mistral-medium-2604')

LEGACY_API_BASE_URL = os.getenv('LEGACY_API_BASE_URL', 'http://127.0.0.1:5001/api').rstrip('/')
LEGACY_API_TOKEN = os.getenv('LEGACY_API_TOKEN', 'demo-token')
LEGACY_API_SESSION = os.getenv('LEGACY_API_SESSION', '')

ENRICH_ON_SEARCH = _flag('IRIS_ENRICH_ON_SEARCH')

PORT = int(os.getenv('PORT', '5000'))
FLASK_DEBUG = _flag('FLASK_DEBUG')
CORS_ORIGINS = [o.strip() for o in os.getenv('CORS_ORIGINS', '*').split(',') if o.strip()]

PUBLIC_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', 'public'))
