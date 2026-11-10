"""Agent Iris : routage du message, recherche outillée et construction de la réponse.

Principe central : le modèle ne rédige jamais les fiches. Il choisit des identifiants
parmi les résultats des outils, un validateur écarte les identifiants inconnus, et les
fiches renvoyées à l'interface proviennent directement des données de l'API.
"""

import asyncio
import logging
import os
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.exceptions import UsageLimitExceeded
from pydantic_ai.messages import ModelMessage, ModelRequest, ModelResponse, TextPart, UserPromptPart
from pydantic_ai.models.mistral import MistralModel
from pydantic_ai.providers.mistral import MistralProvider
from pydantic_ai.usage import UsageLimits

from backend import api_client, config
from backend.prompts import CHAT_PROMPT, ROUTER_PROMPT, SEARCH_PROMPT
from backend.text import SCOPE_REPLY, clean, within_scope

logger = logging.getLogger(__name__)

MAX_SHOWN = 8
MAX_HUNTERS_LISTED = 12
REQUEST_LIMIT = 6      # appels au modèle par recherche
ROUTER_TIMEOUT = 12    # secondes
CHAT_TIMEOUT = 18
SEARCH_TIMEOUT = 40
MODEL_TIMEOUT = 30     # par appel au modèle

HUNTERS_REPLY = ("Voici une sélection de cabinets de chasseurs de tête partenaires du cabinet. Leur spécialité "
                 "n'est pas renseignée dans la base. Souhaitez-vous en voir d'autres ?")
PRECISION_REPLY = ("Pouvez-vous préciser votre recherche ? Indiquez un poste, une entreprise, "
                   "un secteur ou un nom.")
TIMEOUT_REPLY = "La recherche a pris trop de temps. Pouvez-vous préciser un poste ou une entreprise ?"
LIMIT_REPLY = "Pouvez-vous préciser votre recherche (poste, entreprise, secteur ou nom) ?"
ERROR_REPLY = "Je n'ai pas pu traiter cette demande. Indiquez un poste, une entreprise ou un secteur."
DEFAULT_INTRO = "Voici des profils qui correspondent à votre recherche."

Sector = Literal[
    'energie', 'tech', 'luxe', 'banque', 'automobile', 'pharma', 'industrie', 'conseil',
    'immobilier', 'assurance', 'telecom', 'agroalimentaire', 'transport', 'defense', 'sante',
]


@dataclass
class Options:
    """Réglages d'une exécution. Les valeurs par défaut sont celles du produit."""
    ranking: api_client.Ranking = 'score'


@dataclass
class SearchDeps:
    """État d'une recherche, partagé entre les outils et le validateur."""
    exclude_ids: set[str]
    options: Options = field(default_factory=Options)
    contacts_by_id: dict[str, dict] = field(default_factory=dict)
    hunters_by_id: dict[str, dict] = field(default_factory=dict)
    tool_calls: list[dict] = field(default_factory=list)
    needs_precision: bool = False


class Intent(BaseModel):
    is_search: bool = Field(
        description="true si le membre veut trouver ou lister des contacts ou des chasseurs de tête, "
                    "y compris une demande de suite après une recherche. false pour une salutation, "
                    "une question sur l'assistante ou un sujet sans rapport."
    )


class SearchReply(BaseModel):
    message: str = Field(
        description="Phrase d'introduction et éventuelle question de relance. "
                    "Ne contient AUCUN nom, poste ou entreprise de contact."
    )
    contact_ids: list[str] = Field(
        default_factory=list,
        description="Identifiants des contacts retenus (8 au plus), pris dans les résultats de search_contacts.",
    )
    hunter_ids: list[str] = Field(
        default_factory=list,
        description="Identifiants des cabinets retenus, pris dans les résultats de search_hunters.",
    )


# Outils

def compact(contact: dict) -> dict:
    """Vue d'un contact transmise au modèle : de quoi choisir, sans coordonnées."""
    return {
        'id': contact['id'], 'prenom': contact['prenom'], 'nom': contact['nom'],
        'poste': contact['poste'], 'entreprise': contact['entreprise'],
        'a_linkedin': bool(contact['linkedin']), 'amene_par': contact['amene_par'],
        'type': contact['type_contact'],
    }


async def search_contacts(
    ctx: RunContext[SearchDeps],
    name: Optional[str] = None,
    position: Optional[str] = None,
    company: Optional[str] = None,
    sector: Optional[Sector] = None,
) -> list[dict]:
    """Recherche des contacts dirigeants dans le réseau du cabinet.

    À utiliser dès que le membre cherche une personne, un poste, une entreprise ou un
    secteur. Pour un secteur (énergie, tech, luxe...), renseigner `sector` et laisser
    `company` vide.
    """
    call = {'tool': 'search_contacts', 'name': name, 'position': position, 'company': company, 'sector': sector}
    ctx.deps.tool_calls.append(call)
    if not any([name, position, company, sector]):
        ctx.deps.needs_precision = True
        return [{'info': "Aucun critère de recherche. Ne rappelle pas cet outil sans critère : demande au "
                         "membre de préciser un poste, une entreprise, un secteur ou un nom."}]

    results = await api_client.search_contacts(
        name=name, position=position, company=company, sector=sector,
        refresh=config.ENRICH_ON_SEARCH, ranking=ctx.deps.options.ranking,
    )
    reachable = [c for c in results if c['linkedin'] or c['telephone'] or c['email']]
    fresh = [c for c in reachable if c['id'] and c['id'] not in ctx.deps.exclude_ids]
    call['returned'] = len(fresh)
    if not fresh:
        if reachable:
            return [{'info': "Tous les contacts de cette recherche ont déjà été présentés. Dis-le au membre "
                             "et propose d'affiner. NE PRÉSENTE AUCUN contact."}]
        return [{'info': "Aucun contact joignable (LinkedIn, téléphone ou email) pour cette recherche. "
                         "Dis-le au membre et propose d'affiner ou d'élargir. NE PRÉSENTE AUCUN contact."}]

    ctx.deps.contacts_by_id.update((c['id'], c) for c in fresh)
    return [compact(c) for c in fresh]


async def search_hunters(ctx: RunContext[SearchDeps], name: Optional[str] = None) -> list[dict]:
    """Recherche des cabinets de chasseurs de tête partenaires.

    Les cabinets n'ont NI spécialité NI secteur renseignés. Si le membre demande une
    spécialité (luxe, tech...), appeler sans `name` et présenter les cabinets disponibles.
    """
    call: dict[str, Any] = {'tool': 'search_hunters', 'name': name}
    ctx.deps.tool_calls.append(call)
    results = await api_client.search_hunters(name=name)
    if not results and name:
        results = await api_client.search_hunters()
    results = [h for h in results if h['id']][:MAX_HUNTERS_LISTED]
    call['returned'] = len(results)
    ctx.deps.hunters_by_id.update((h['id'], h) for h in results)
    return [{'id': h['id'], 'cabinet': h['cabinet'], 'contact_principal': h['contact_principal']} for h in results]


TOOLS = [search_contacts, search_hunters]


def keep_known_ids(ctx: RunContext[SearchDeps], reply: SearchReply) -> SearchReply:
    """Validateur de sortie : ne garde que les identifiants réellement renvoyés par les outils."""
    reply.contact_ids = [i for i in dict.fromkeys(reply.contact_ids) if i in ctx.deps.contacts_by_id][:MAX_SHOWN]
    reply.hunter_ids = [i for i in dict.fromkeys(reply.hunter_ids) if i in ctx.deps.hunters_by_id][:MAX_SHOWN]
    return reply


# Agents

_provider = MistralProvider(api_key=config.MISTRAL_API_KEY or 'cle-absente')
_settings = {'timeout': MODEL_TIMEOUT}

# `instructions` plutôt que `system_prompt` : elles sont renvoyées à chaque appel, alors
# qu'un `system_prompt` n'est pas régénéré quand un historique de conversation est fourni.
router_agent = Agent(
    MistralModel(config.MISTRAL_MODEL, provider=_provider),
    output_type=Intent, instructions=ROUTER_PROMPT, model_settings=_settings,
)
chat_agent = Agent(
    MistralModel(config.MISTRAL_CHAT_MODEL, provider=_provider),
    output_type=str, instructions=CHAT_PROMPT,
    model_settings={**_settings, 'max_tokens': 160, 'temperature': 0.0},
)
search_agent = Agent(
    MistralModel(config.MISTRAL_MODEL, provider=_provider),
    deps_type=SearchDeps, output_type=SearchReply, instructions=SEARCH_PROMPT,
    tools=TOOLS, retries=2, model_settings=_settings,
)
search_agent.output_validator(keep_known_ids)


# Mise en forme

_CONTACT_FIELDS = ('id', 'prenom', 'nom', 'poste', 'entreprise', 'linkedin', 'amene_par',
                   'type_contact', 'email', 'telephone', 'localisation')
_HUNTER_FIELDS = ('id', 'cabinet', 'contact_principal', 'specialites', 'secteurs', 'email', 'telephone')


def to_history(messages: list[dict]) -> list[ModelMessage]:
    """Convertit l'historique envoyé par le widget au format de pydantic-ai."""
    history: list[ModelMessage] = []
    for m in messages:
        content = str(m.get('content', ''))
        if m.get('role') == 'user':
            history.append(ModelRequest(parts=[UserPromptPart(content=content)]))
        elif m.get('role') == 'assistant':
            history.append(ModelResponse(parts=[TextPart(content=content)]))
    return history


@dataclass
class Trace:
    """Mesures d'une exécution : intention, outils, durées et consommation par modèle."""
    intent: Optional[str] = None
    tool_calls: list[dict] = field(default_factory=list)
    timings: dict[str, float] = field(default_factory=dict)
    usage: list[dict] = field(default_factory=list)
    outcome: str = 'ok'

    def add_usage(self, step: str, model: str, result) -> None:
        usage = result.usage() if callable(result.usage) else result.usage
        self.usage.append({'step': step, 'model': model, 'requests': usage.requests,
                           'input_tokens': usage.input_tokens or 0, 'output_tokens': usage.output_tokens or 0})


def _reply(message: str, trace: Trace, contacts=(), hunters=()) -> dict:
    return {
        'response': message, 'contacts': list(contacts), 'hunters': list(hunters),
        'sources_used': list(dict.fromkeys(c['tool'] for c in trace.tool_calls)), 'trace': trace,
    }


# Exécution

async def _is_search(message: str, history: list[dict], trace: Trace) -> bool:
    start = time.perf_counter()
    try:
        result = await asyncio.wait_for(
            router_agent.run(message, message_history=to_history(history[-4:])), ROUTER_TIMEOUT
        )
        trace.add_usage('routeur', config.MISTRAL_MODEL, result)
        return result.output.is_search
    except Exception:
        logger.warning("Routeur indisponible, message traité comme une recherche")
        trace.outcome = 'routeur_indisponible'
        return True
    finally:
        trace.timings['routeur'] = time.perf_counter() - start


async def _chat(message: str, history: list[dict], trace: Trace) -> dict:
    try:
        result = await asyncio.wait_for(chat_agent.run(message, message_history=to_history(history)), CHAT_TIMEOUT)
    except Exception:
        logger.warning("Réponse de conversation indisponible")
        trace.outcome = 'conversation_indisponible'
        return _reply(SCOPE_REPLY, trace)
    trace.add_usage('conversation', config.MISTRAL_CHAT_MODEL, result)
    return _reply(within_scope(clean(result.output)), trace)


async def _search(message: str, history: list[dict], exclude_ids: list[str], options: Options, trace: Trace) -> dict:
    deps = SearchDeps(exclude_ids=set(exclude_ids), options=options)
    trace.tool_calls = deps.tool_calls
    try:
        result = await asyncio.wait_for(
            search_agent.run(message, deps=deps, message_history=to_history(history),
                             usage_limits=UsageLimits(request_limit=REQUEST_LIMIT)),
            SEARCH_TIMEOUT,
        )
    except asyncio.TimeoutError:
        logger.warning("Recherche interrompue (délai dépassé)")
        trace.outcome = 'delai_depasse'
        return _reply(TIMEOUT_REPLY, trace)
    except UsageLimitExceeded:
        logger.warning("Recherche interrompue (trop d'appels au modèle)")
        trace.outcome = 'limite_appels'
        return _reply(LIMIT_REPLY, trace)
    except Exception:
        logger.exception("Échec de la recherche")
        trace.outcome = 'erreur'
        return _reply(ERROR_REPLY, trace)

    trace.add_usage('recherche', config.MISTRAL_MODEL, result)
    reply = result.output
    contacts = [{k: deps.contacts_by_id[i][k] for k in _CONTACT_FIELDS} for i in reply.contact_ids]
    hunters = [{k: deps.hunters_by_id[i][k] for k in _HUNTER_FIELDS} for i in reply.hunter_ids]
    if deps.needs_precision and not (contacts or hunters):
        return _reply(PRECISION_REPLY, trace)
    # Les cabinets n'ont pas de spécialité en base : texte fixe, pour ne rien leur attribuer.
    message_out = HUNTERS_REPLY if hunters and not contacts else clean(reply.message)
    if contacts and not message_out:
        message_out = DEFAULT_INTRO
    return _reply(message_out, trace, contacts, hunters)


async def answer(message: str, history: Optional[list[dict]] = None, exclude_ids: Optional[list[str]] = None,
                 options: Optional[Options] = None) -> dict:
    """Répond à un message. Renvoie {response, contacts, hunters, sources_used, trace}."""
    history, trace = history or [], Trace()
    start = time.perf_counter()
    if await _is_search(message, history, trace):
        trace.intent = 'recherche'
        reply = await _search(message, history, exclude_ids or [], options or Options(), trace)
    else:
        trace.intent = 'conversation'
        reply = await _chat(message, history, trace)
    trace.timings['total'] = time.perf_counter() - start
    return reply


# Flask est synchrone et pydantic-ai asynchrone : toutes les exécutions passent par une
# boucle unique, dans un thread de fond, à laquelle les clients HTTP restent liés. Elle
# démarre au premier message et est recréée après un fork, pour supporter les serveurs
# qui dupliquent leurs processus après le chargement de l'application.
_loop: Optional[asyncio.AbstractEventLoop] = None
_loop_pid: Optional[int] = None
_loop_lock = threading.Lock()


def _get_loop() -> asyncio.AbstractEventLoop:
    global _loop, _loop_pid
    if _loop is None or _loop_pid != os.getpid():
        with _loop_lock:
            if _loop is None or _loop_pid != os.getpid():
                loop = asyncio.new_event_loop()
                threading.Thread(target=loop.run_forever, name='iris-agent', daemon=True).start()
                _loop, _loop_pid = loop, os.getpid()
    return _loop


def run_agent(message: str, history: Optional[list[dict]] = None, exclude_ids: Optional[list[str]] = None) -> dict:
    """Point d'entrée synchrone, appelé par Flask."""
    return asyncio.run_coroutine_threadsafe(answer(message, history, exclude_ids), _get_loop()).result()
