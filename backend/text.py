"""Nettoyage déterministe des textes produits par le modèle."""

import re
import unicodedata
from typing import Optional

_EMOJI_RE = re.compile(
    '[\U0001F300-\U0001FAFF\U00002600-\U000027BF\U0001F000-\U0001F0FF'
    '\U00002190-\U000021FF\U00002B00-\U00002BFF\U0000FE00-\U0000FE0F\U0000200D]'
)
_CARD_LINE_RE = re.compile(
    r'^\s*(?:\*\*[^*]+\*\*\s*$|\[[^\]]+\]\(https?://|Amené par\s*:|Alumni\s*$|Client actuel\s*$'
    r'|(?:Spécialités|Secteurs)\s*:)',
    re.IGNORECASE,
)
_OUT_OF_SCOPE = (
    'rédig', 'redig', 'lettre de motiv', 'poèm', 'devoir', 'résumé', 'traduc', 'grammaire', 'slogan',
    'scénario', 'améliorer', 'question générale', 'questions générale', 'stratégie', ' cv', 'conseils',
)
SCOPE_REPLY = ("Je peux vous aider à trouver des contacts dirigeants et des chasseurs de tête "
               "dans le réseau du cabinet. Indiquez-moi un poste, une entreprise ou un secteur.")

_NUMBER_WORDS = {'un': 1, 'une': 1, 'deux': 2, 'trois': 3, 'quatre': 4, 'cinq': 5, 'six': 6,
                 'sept': 7, 'huit': 8, 'neuf': 9, 'dix': 10}
_NOUNS = r'(?:contacts?|profils?|dirigeants?|dirigeantes?|personnes?|noms?|cabinets?|chasseurs?)'
_NUMBER = r'(\d{1,2}|' + '|'.join(_NUMBER_WORDS) + r')'
# « 3 contacts », « trois profils », « deux autres dirigeants » : au plus deux mots entre le nombre et le nom.
_COUNT_RE = re.compile(r'\b' + _NUMBER + r'\s+(?:(?!chez\b|dans\b)\w+\s+){0,2}?' + _NOUNS + r'\b', re.IGNORECASE)
_SINGLE_RE = re.compile(r'\b(?:un seul|une seule|1)\s+' + _NOUNS + r'\b', re.IGNORECASE)


def fold(text: str) -> str:
    """Minuscules sans accents, pour comparer deux textes."""
    text = unicodedata.normalize('NFD', text or '')
    return ''.join(c for c in text if unicodedata.category(c) != 'Mn').lower()


def _to_int(token: str) -> int:
    return int(token) if token.isdigit() else _NUMBER_WORDS[token.lower()]


def requested_count(message: str) -> Optional[int]:
    """Nombre de résultats explicitement demandé (« donne-moi 3 contacts »), sinon None.

    « un » et « une » sont des articles : « un CFO » ne demande pas un seul résultat.
    """
    if _SINGLE_RE.search(message):
        return 1
    for match in _COUNT_RE.finditer(message):
        count = _to_int(match.group(1))
        if count >= 2:
            return count
    return None


def fix_count_claims(message: str, shown: int) -> str:
    """Corrige un nombre annoncé dans le texte quand il contredit le nombre de fiches affichées."""
    def repl(match: re.Match) -> str:
        token = match.group(1)
        if token.lower() in ('un', 'une') or _to_int(token) == shown:
            return match.group(0)
        return str(shown) + match.group(0)[len(token):]
    return _COUNT_RE.sub(repl, message) if shown else message


def clean(text: str) -> str:
    """Retire emojis, tirets longs, titres markdown et lignes imitant une fiche contact."""
    text = _EMOJI_RE.sub('', text or '')
    text = re.sub(r'\s*[—–]\s*', ', ', text)
    text = re.sub(r'(?m)^\s{0,3}#{1,6}\s*', '', text)
    lines = [line for line in text.split('\n') if not _CARD_LINE_RE.match(line)]
    return re.sub(r'\n{3,}', '\n\n', '\n'.join(lines)).strip()


def within_scope(text: str) -> str:
    """Remplace une réponse de conversation qui annonce des capacités hors périmètre."""
    low = text.lower()
    bullets = sum(low.count(mark) for mark in ('\n- ', '\n• ', '\n* '))
    return SCOPE_REPLY if bullets >= 2 or any(word in low for word in _OUT_OF_SCOPE) else text
