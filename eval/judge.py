"""Juge LLM : le message d'introduction est-il fidèle aux fiches affichées ?

Le validateur garantit que les fiches sont réelles, mais le texte d'introduction reste
rédigé librement par le modèle. Le juge vérifie qu'il n'affirme rien que les fiches ne
montrent pas. Il utilise un autre modèle que celui qui a produit la réponse, une grille
explicite, une température nulle et une sortie structurée.
"""

from typing import Literal

from pydantic import BaseModel, Field
from pydantic_ai import Agent
from pydantic_ai.models.mistral import MistralModel

from backend import agent, config

JUDGE_MODEL = config.MISTRAL_CHAT_MODEL

JUDGE_PROMPT = """Tu évalues la FIDÉLITÉ du message d'introduction d'une assistante de recherche de contacts.

On te donne : la demande du membre, le message de l'assistante, et la liste des fiches réellement affichées sous ce message (poste, entreprise, statut). Tu ne juges ni le style ni la pertinence des fiches, uniquement si le message affirme des choses vraies au regard des fiches.

Le message est INFIDÈLE s'il présente au moins un de ces problèmes :
- nombre_faux : il annonce un nombre de profils différent du nombre de fiches affichées.
- attribut_non_montre : il attribue aux profils une caractéristique que les fiches ne montrent pas ou contredisent (une spécialité, un poste, une entreprise, un secteur ou un pays qui n'apparaît pas dans les fiches). Exemple : "des directeurs financiers" alors qu'aucune fiche n'a un poste financier ; "chez Airbus" alors que les fiches sont chez Renault.
- personne_nommee : il cite le nom d'une personne.
- promesse_hors_perimetre : il propose un service autre que la recherche de contacts (rédaction, conseil...).

Le message est FIDÈLE dans les autres cas. Sont notamment fidèles : une formule générale ("voici des profils qui correspondent"), une proposition d'affiner, le fait de dire qu'aucun profil exact n'a été trouvé, et une description approximative mais non contredite par les fiches ("des dirigeants" quand les fiches sont des postes de direction).

Réponds en choisissant d'abord le problème principal ("aucun" si le message est fidèle), puis justifie en une phrase."""


class Verdict(BaseModel):
    probleme: Literal['aucun', 'nombre_faux', 'attribut_non_montre', 'personne_nommee', 'promesse_hors_perimetre']
    justification: str = Field(description="Une phrase qui cite l'élément du message en cause.")

    @property
    def fidele(self) -> bool:
        return self.probleme == 'aucun'


judge_agent = Agent(
    MistralModel(JUDGE_MODEL, provider=agent._provider),
    output_type=Verdict, instructions=JUDGE_PROMPT,
    model_settings={'timeout': 30, 'temperature': 0.0, 'max_tokens': 200},
)


def render(query: str, message: str, cards: list[dict], hunters: int) -> str:
    """Texte soumis au juge (et à l'annotateur humain) : demande, message et fiches affichées."""
    lines = [f'DEMANDE DU MEMBRE : {query}', f'MESSAGE DE L\'ASSISTANTE : {message}', '']
    if hunters:
        lines.append(f'FICHES AFFICHÉES : {hunters} cabinets de chasseurs de tête, sans spécialité indiquée.')
    elif not cards:
        lines.append('FICHES AFFICHÉES : aucune.')
    else:
        lines.append(f'FICHES AFFICHÉES ({len(cards)}) :')
        lines += [f"- {c['poste']}, {c['entreprise']}" + (' (Alumni)' if c.get('type_contact') == 'alumni' else '')
                  for c in cards]
    return '\n'.join(lines)


async def judge(query: str, message: str, cards: list[dict], hunters: int) -> dict:
    result = await judge_agent.run(render(query, message, cards, hunters))
    usage = result.usage() if callable(result.usage) else result.usage
    return {'probleme': result.output.probleme, 'fidele': result.output.fidele,
            'justification': result.output.justification,
            'input_tokens': usage.input_tokens or 0, 'output_tokens': usage.output_tokens or 0}
