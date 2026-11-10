"""Nettoyage déterministe des textes produits par le modèle."""

import re

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
