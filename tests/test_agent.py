"""Tests de l'agent avec un modèle simulé : aucun appel réseau."""

from types import SimpleNamespace

from pydantic_ai.messages import ModelMessage, ModelResponse, TextPart, ToolCallPart
from pydantic_ai.models.function import AgentInfo, FunctionModel

from backend import agent, api_client
from backend.agent import SearchDeps, SearchReply, keep_known_ids

CONTACTS = [
    {'id': 'vrai-1', 'prenom': 'Adèle', 'nom': 'Fontaine', 'poste': 'CFO', 'entreprise': 'Sanofi',
     'linkedin': 'https://l/1', 'telephone': '', 'email': '', 'localisation': 'Paris',
     'type_contact': 'alumni', 'amene_par': 'Paul MARTINEAU'},
    {'id': 'vrai-2', 'prenom': 'Hugo', 'nom': 'Picard', 'poste': 'DAF Groupe', 'entreprise': 'Sanofi',
     'linkedin': 'https://l/2', 'telephone': '', 'email': '', 'localisation': 'Lyon',
     'type_contact': 'contact_reseau', 'amene_par': ''},
    {'id': 'injoignable', 'prenom': 'Zoé', 'nom': 'Vidal', 'poste': 'CFO', 'entreprise': 'Sanofi',
     'linkedin': '', 'telephone': '', 'email': '', 'localisation': '',
     'type_contact': 'contact_reseau', 'amene_par': ''},
]


def test_le_validateur_ecarte_les_identifiants_inconnus_et_les_doublons():
    deps = SearchDeps(exclude_ids=set(), contacts_by_id={'a': {}, 'b': {}})
    reply = SearchReply(message='x', contact_ids=['a', 'invente', 'a', 'b'], hunter_ids=['h-invente'])
    result = keep_known_ids(SimpleNamespace(deps=deps), reply)
    assert result.contact_ids == ['a', 'b'] and result.hunter_ids == []


def test_le_validateur_limite_a_huit():
    deps = SearchDeps(exclude_ids=set(), contacts_by_id={str(i): {} for i in range(12)})
    reply = SearchReply(message='x', contact_ids=[str(i) for i in range(12)])
    assert len(keep_known_ids(SimpleNamespace(deps=deps), reply).contact_ids) == 8


def _router(is_search: bool) -> FunctionModel:
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {'is_search': is_search})])
    return FunctionModel(respond)


def _searcher(final_ids: list[str], seen: list) -> FunctionModel:
    """Modèle simulé : appelle search_contacts, puis renvoie `final_ids`."""
    def respond(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        seen.append((messages, info))
        if not any(p.part_kind == 'tool-return' for p in messages[-1].parts):
            return ModelResponse(parts=[ToolCallPart('search_contacts', {'position': 'CFO', 'company': 'Sanofi'})])
        args = {'message': 'Voici des profils — choisis.', 'contact_ids': final_ids}
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, args)])
    return FunctionModel(respond)


async def _fake_search_contacts(**kwargs):
    return list(CONTACTS)


async def test_un_contact_invente_n_atteint_jamais_la_reponse(monkeypatch):
    monkeypatch.setattr(api_client, 'search_contacts', _fake_search_contacts)
    seen: list = []
    with agent.router_agent.override(model=_router(True)), \
            agent.search_agent.override(model=_searcher(['vrai-2', 'id-invente', 'injoignable'], seen)):
        reply = await agent.answer('un CFO chez Sanofi')

    assert [c['id'] for c in reply['contacts']] == ['vrai-2']       # inventé et injoignable écartés
    assert reply['contacts'][0]['nom'] == 'Picard'                  # la fiche vient des données
    assert reply['response'] == 'Voici des profils, choisis.'       # texte nettoyé
    assert reply['sources_used'] == ['search_contacts']
    assert reply['trace'].intent == 'recherche'


async def test_le_modele_ne_voit_ni_les_contacts_exclus_ni_les_coordonnees(monkeypatch):
    monkeypatch.setattr(api_client, 'search_contacts', _fake_search_contacts)
    seen: list = []
    with agent.router_agent.override(model=_router(True)), \
            agent.search_agent.override(model=_searcher(['vrai-1', 'vrai-2'], seen)):
        reply = await agent.answer('un CFO chez Sanofi', exclude_ids=['vrai-1'])

    tool_return = next(p for p in seen[-1][0][-1].parts if p.part_kind == 'tool-return')
    assert [c['id'] for c in tool_return.content] == ['vrai-2']
    assert 'linkedin' not in tool_return.content[0] and 'telephone' not in tool_return.content[0]
    assert [c['id'] for c in reply['contacts']] == ['vrai-2']


async def test_les_instructions_sont_envoyees_meme_avec_un_historique(monkeypatch):
    monkeypatch.setattr(api_client, 'search_contacts', _fake_search_contacts)
    seen: list = []
    history = [{'role': 'user', 'content': 'un CFO chez Sanofi'}, {'role': 'assistant', 'content': 'Voici.'}]
    with agent.router_agent.override(model=_router(True)), \
            agent.search_agent.override(model=_searcher(['vrai-1'], seen)):
        await agent.answer("donne m'en d'autres", history=history)
    assert 'Iris' in (seen[0][1].instructions or '')


async def test_un_message_hors_recherche_ne_declenche_aucun_outil():
    def chat(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        return ModelResponse(parts=[TextPart('Bonjour, je peux rédiger votre CV \U0001F600')])
    with agent.router_agent.override(model=_router(False)), agent.chat_agent.override(model=FunctionModel(chat)):
        reply = await agent.answer('bonjour')
    assert reply['contacts'] == [] and reply['sources_used'] == []
    assert reply['response'] == agent.SCOPE_REPLY   # promesse hors périmètre remplacée
    assert reply['trace'].intent == 'conversation'


async def test_si_le_routeur_echoue_on_tente_la_recherche(monkeypatch):
    monkeypatch.setattr(api_client, 'search_contacts', _fake_search_contacts)

    def broken(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        raise RuntimeError('panne')
    with agent.router_agent.override(model=FunctionModel(broken)), \
            agent.search_agent.override(model=_searcher(['vrai-1'], [])):
        reply = await agent.answer('un CFO chez Sanofi')
    assert [c['id'] for c in reply['contacts']] == ['vrai-1']
    assert reply['trace'].outcome == 'routeur_indisponible'


async def test_le_nombre_demande_est_respecte(monkeypatch):
    monkeypatch.setattr(api_client, 'search_contacts', _fake_search_contacts)
    with agent.router_agent.override(model=_router(True)), \
            agent.search_agent.override(model=_searcher(['vrai-1', 'vrai-2'], [])):
        reply = await agent.answer('un seul contact chez Sanofi')
    assert [c['id'] for c in reply['contacts']] == ['vrai-1']


async def test_une_entreprise_demandee_n_est_pas_elargie_a_un_secteur(monkeypatch):
    async def nothing(**kwargs):
        return []
    monkeypatch.setattr(api_client, 'search_contacts', nothing)

    def drifting(messages: list[ModelMessage], info: AgentInfo) -> ModelResponse:
        returns = sum(p.part_kind == 'tool-return' for m in messages for p in m.parts)
        if returns == 0:
            return ModelResponse(parts=[ToolCallPart('search_contacts', {'position': 'CFO', 'company': 'Airbus'})])
        if returns == 1:
            return ModelResponse(parts=[ToolCallPart('search_contacts', {'position': 'CFO', 'sector': 'automobile'})])
        return ModelResponse(parts=[ToolCallPart(info.output_tools[0].name, {'message': 'Aucun profil.'})])

    with agent.router_agent.override(model=_router(True)), \
            agent.search_agent.override(model=FunctionModel(drifting)):
        reply = await agent.answer('un CFO chez Airbus')
    calls = reply['trace'].tool_calls
    assert calls[0].get('refused') is None and calls[1]['refused'] is True
    assert reply['contacts'] == []


async def test_un_filtre_de_poste_sans_resultat_est_elargi(monkeypatch):
    calls: list[dict] = []

    async def api(**kwargs):
        calls.append(kwargs)
        return [] if kwargs.get('position') else list(CONTACTS)
    monkeypatch.setattr(api_client, 'search_contacts', api)
    seen: list = []
    with agent.router_agent.override(model=_router(True)), \
            agent.search_agent.override(model=_searcher(['vrai-1'], seen)):
        reply = await agent.answer('un directeur financier chez Sanofi')

    assert len(calls) == 2 and calls[1].get('position') is None      # relance sans le poste
    assert reply['trace'].tool_calls[0]['broadened'] is True
    tool_return = next(p for p in seen[-1][0][-1].parts if p.part_kind == 'tool-return')
    assert 'info' in tool_return.content[0]                           # le modèle est prévenu
    assert [c['id'] for c in reply['contacts']] == ['vrai-1']
