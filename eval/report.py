"""Mise en forme des résultats de l'évaluation en tableaux Markdown."""

from typing import Optional

DEFINITIONS = {
    'routage': "Part des cas où l'intention détectée (recherche ou conversation) est la bonne.",
    'outil': "Part des cas où l'outil attendu a été appelé (ou aucun outil, quand aucun n'est attendu).",
    'precision': "Part des contacts proposés qui sont pertinents (note 1 ou 2).",
    'precision_stricte': "Part des contacts proposés qui répondent exactement à la demande (note 2).",
    'ndcg': "nDCG@8 : qualité du choix et de l'ordre, de 0 à 1, rapportée au meilleur résultat possible.",
    'reponse_utile': "Part des cas où au moins un contact pertinent est proposé, quand il en existe.",
    'france': "Part des contacts proposés basés en France, hors demande d'un autre pays.",
    'vide_attendu': "Part des cas sans réponse possible où aucun contact n'est présenté.",
    'nombre_respecte': "Part des cas où le nombre de contacts demandé est exactement respecté.",
    'sans_doublon': "Part des demandes de suite qui ne répètent aucun contact déjà montré.",
    'cabinets': "Part des demandes de chasseurs de tête qui présentent au moins un cabinet.",
    'texte_conforme': "Part des cas dont le texte respecte les interdits (email, nom, consigne détournée).",
    'ids_inventes_par_le_modele': "Part des identifiants proposés par le modèle que le validateur a écartés.",
    'fiches_inventees': "Part des fiches rédigées par le modèle qui ne correspondent à aucun contact renvoyé.",
    'fiches_alterees': "Part des fiches rédigées dont le poste ou l'entreprise a été modifié.",
    'message_fidele': "Part des messages d'introduction jugés fidèles aux fiches par le juge LLM.",
    'echec_technique': "Part des exécutions terminées par une réponse de secours (délai, limite d'appels).",
    'latence_s': "Durée moyenne d'une réponse, en secondes.",
    'tokens': "Nombre moyen de tokens consommés par réponse (entrée et sortie).",
    'cout_usd': "Coût moyen d'une réponse, en dollars.",
}
MAIN = ['routage', 'outil', 'precision', 'precision_stricte', 'ndcg', 'reponse_utile', 'france', 'vide_attendu',
        'nombre_respecte', 'sans_doublon', 'cabinets', 'texte_conforme', 'ids_inventes_par_le_modele',
        'message_fidele', 'echec_technique']
RATE_FREE = {'latence_s', 'tokens', 'cout_usd', 'ndcg'}


def _fmt(name: str, value: float) -> str:
    if value is None or value != value:
        return 'n/d'
    if name == 'cout_usd':
        return f'{value:.5f} $'
    if name == 'latence_s':
        return f'{value:.1f} s'
    if name == 'tokens':
        return f'{value:.0f}'
    if name == 'ndcg':
        return f'{value:.2f}'
    return f'{100 * value:.0f} %'


def _cell(name: str, m: Optional[dict]) -> str:
    if not m:
        return 'n/d'
    return f"{_fmt(name, m['moyenne'])} [{_fmt(name, m['ic95'][0])} ; {_fmt(name, m['ic95'][1])}]"


def _variant_table(results: dict, variants: list[str], names: list[str]) -> list[str]:
    present = [v for v in variants if v in results['variantes']]
    lines = ['| Métrique | ' + ' | '.join(present) + ' |', '|---|' + '---|' * len(present)]
    for name in names:
        cells = [_cell(name, results['variantes'][v]['metriques'].get(name)) for v in present]
        if any(c != 'n/d' for c in cells):
            lines.append(f'| {name} | ' + ' | '.join(cells) + ' |')
    return lines


def render(results: dict) -> str:
    ref = results['variantes'].get('reference')
    out = ['# Résultats de l\'évaluation', '',
           f"{results['cas']} cas, {results['executions_par_cas']} exécutions par cas. "
           f"Modèles : recherche `{results['modeles']['recherche']}`, conversation "
           f"`{results['modeles']['conversation']}`, juge `{results['modeles']['juge']}`.", '',
           "Les valeurs sont des moyennes par cas, suivies de leur intervalle de confiance à 95 % "
           "(bootstrap sur les cas).", '']

    if ref:
        out += ['## Version de référence', '', '| Métrique | Valeur [IC 95 %] | Cas | Ce que ça mesure |',
                '|---|---|---|---|']
        for name in MAIN + ['latence_s', 'tokens', 'cout_usd']:
            m = ref['metriques'].get(name)
            if m:
                out.append(f"| {name} | {_cell(name, m)} | {m['cas']} | {DEFINITIONS[name]} |")
        stab = ref['stabilite']
        out += ['', f"Latence : médiane {ref['latence_p50_s']:.1f} s, 95e centile {ref['latence_p95_s']:.1f} s.", '']
        if stab['jaccard'] is not None:
            out += [f"Stabilité : recouvrement moyen des contacts entre deux exécutions du même cas (Jaccard) "
                    f"{stab['jaccard']:.2f} sur {stab['cas_jaccard']} cas ; intention identique d'une exécution "
                    f"à l'autre dans {100 * stab['intention_constante']:.0f} % des cas.", '']

        out += ['## Par famille de cas', '', '| Famille | Cas | routage | precision | ndcg | texte_conforme |',
                '|---|---|---|---|---|---|']
        for family, m in ref['par_famille'].items():
            n = max((v['cas'] for v in m.values()), default=0)
            cells = [_fmt(k, m[k]['moyenne']) if k in m else 'n/d'
                     for k in ('routage', 'precision', 'ndcg', 'texte_conforme')]
            out.append(f'| {family} | {n} | ' + ' | '.join(cells) + ' |')
        out.append('')

    if 'fiches_libres' in results['variantes']:
        out += ['## Expérience 1 : sélection d\'identifiants ou fiches rédigées par le modèle', '']
        out += _variant_table(results, ['reference', 'fiches_libres'],
                              ['ids_inventes_par_le_modele', 'fiches_inventees', 'fiches_alterees', 'precision',
                               'ndcg', 'latence_s', 'tokens'])
        out.append('')

    if 'ordre_api' in results['variantes']:
        out += ['## Expérience 2 : ordre du lot transmis au modèle', '']
        out += _variant_table(results, ['reference', 'ordre_api', 'ordre_aleatoire', 'score_seul'],
                              ['precision', 'precision_stricte', 'ndcg', 'france', 'reponse_utile'])
        out.append('')

    if 'lot10_score' in results['variantes']:
        out += ['## Expérience 2 bis : même comparaison avec un lot réduit à 10 contacts', '']
        out += _variant_table(results, ['lot10_score', 'lot10_api', 'lot10_aleatoire'],
                              ['precision', 'precision_stricte', 'ndcg', 'france', 'reponse_utile'])
        out.append('')
        for name, c in (results.get('score_contre_aleatoire_lot10') or {}).items():
            if c:
                out.append(f"Score contre ordre aléatoire, {name}, test apparié sur {c['cas']} cas : différence "
                           f"{c['difference']:+.3f} [{c['ic95'][0]:+.3f} ; {c['ic95'][1]:+.3f}], p = {c['p']:.3f}.")
        out.append('')

    if results.get('avant_apres'):
        out += ['## Avant et après les corrections', '',
                '| Métrique | Cas | Avant | Après | Différence [IC 95 %] | p (test apparié) |', '|---|---|---|---|---|---|']
        for name, c in results['avant_apres'].items():
            if c:
                out.append(f"| {name} | {c['cas']} | {_fmt(name, c['avant'])} | {_fmt(name, c['apres'])} | "
                           f"{c['difference']:+.3f} [{c['ic95'][0]:+.3f} ; {c['ic95'][1]:+.3f}] | {c['p']:.3f} |")
        out.append('')

    agreement = results.get('accord_juge_humain')
    out += ['## Validation du juge LLM', '']
    if agreement:
        out += [f"{agreement['reponses_annotees']} réponses annotées à la main. Accord avec le juge : "
                f"{100 * agreement['accord']:.0f} %, kappa de Cohen {agreement['kappa_de_cohen']:.2f}. "
                f"Désaccords : {agreement['juge_infidele_humain_fidele']} messages jugés infidèles par le juge "
                f"seul, {agreement['juge_fidele_humain_infidele']} par l'humain seul.", '']
    else:
        out += ["Annotation humaine en attente : remplir `eval/annotations/a_annoter.csv` puis relancer.", '']
    return '\n'.join(out)
