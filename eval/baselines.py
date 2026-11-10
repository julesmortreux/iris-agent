"""Variante de comparaison : le modèle rédige lui-même les fiches.

C'est l'approche naïve que le produit a écartée. Elle sert à mesurer ce que la
sélection par identifiants apporte : mêmes outils, mêmes données, mais la sortie
contient des fiches écrites par le modèle au lieu d'identifiants.
"""

import asyncio
import time

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.mistral import MistralModel
from pydantic_ai.usage import UsageLimits

from backend import agent, config
from backend.prompts import SEARCH_PROMPT
from eval.truth import fold


class Card(BaseModel):
    prenom: str
    nom: str
    poste: str
    entreprise: str


class FreeReply(BaseModel):
    message: str = Field(description="Phrase d'introduction et éventuelle question de relance.")
    contacts: list[Card] = Field(default_factory=list, description="Fiches des contacts retenus (8 au plus).")


_FREE_FORMAT = """FORMAT DE RÉPONSE :
- Rédige dans `contacts` la fiche de chaque contact retenu : prénom, nom, poste, entreprise.
- `message` contient une phrase d'introduction et, si utile, une question de relance.
- Retiens 6 à 8 contacts pertinents (8 si possible).
- Privilégie les Alumni pertinents, les postes de direction, les grands groupes, la maison-mère et les profils basés en France.
- Pas d'emoji. Sois concise."""

FREE_PROMPT = SEARCH_PROMPT.split('FORMAT DE RÉPONSE')[0] + _FREE_FORMAT

free_agent = Agent(
    MistralModel(config.MISTRAL_MODEL, provider=agent._provider),
    deps_type=agent.SearchDeps, output_type=FreeReply, instructions=FREE_PROMPT,
    tools=agent.TOOLS, retries=2, model_settings=agent._settings,
)


def _key(prenom: str, nom: str) -> str:
    return fold(f'{prenom} {nom}').strip()


def match_cards(cards: list[Card], contacts_by_id: dict[str, dict]) -> list[dict]:
    """Rapproche chaque fiche rédigée d'un contact réellement renvoyé par les outils.

    Statut : `exacte` (nom, poste et entreprise identiques), `alteree` (la personne existe
    mais son poste ou son entreprise a été modifié), `inventee` (personne absente des résultats).
    """
    by_name = {_key(c['prenom'], c['nom']): c for c in contacts_by_id.values()}
    matched = []
    for card in cards:
        real = by_name.get(_key(card.prenom, card.nom))
        if real is None:
            status = 'inventee'
        elif fold(card.poste) == fold(real['poste']) and fold(card.entreprise) == fold(real['entreprise']):
            status = 'exacte'
        else:
            status = 'alteree'
        matched.append({'id': real['id'] if real else None, 'status': status, **card.model_dump()})
    return matched


async def answer_free(message: str, history: list[dict], exclude_ids: list[str]) -> dict:
    """Mêmes outils et mêmes réglages que le produit ; seule la forme de la sortie change."""
    trace = agent.Trace(intent='recherche')
    deps = agent.SearchDeps(exclude_ids=set(exclude_ids), message=message,
                            options=agent.Options())
    trace.tool_calls = deps.tool_calls
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            free_agent.run(message, deps=deps, message_history=agent.to_history(history),
                           usage_limits=UsageLimits(request_limit=agent.REQUEST_LIMIT)),
            agent.SEARCH_TIMEOUT,
        )
    except Exception as exc:
        trace.outcome = type(exc).__name__
        trace.timings['total'] = time.perf_counter() - start
        return {'response': '', 'cards': [], 'contacts': [], 'hunters': [], 'sources_used': [], 'trace': trace}
    trace.add_usage('recherche', config.MISTRAL_MODEL, result)
    trace.timings['total'] = time.perf_counter() - start
    cards = match_cards(result.output.contacts[:agent.MAX_SHOWN], deps.contacts_by_id)
    return {
        'response': result.output.message, 'cards': cards,
        'contacts': [{'id': c['id']} for c in cards if c['id']], 'hunters': [],
        'sources_used': list(dict.fromkeys(c['tool'] for c in trace.tool_calls)), 'trace': trace,
    }
