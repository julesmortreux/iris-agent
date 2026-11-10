"""Calcul des métriques à partir des exécutions enregistrées.

Chaque cas est joué plusieurs fois. Une métrique est d'abord moyennée par cas, puis sur
les cas : un cas compte pour un, quel que soit son nombre d'exécutions. Les intervalles
de confiance à 95 % sont obtenus par bootstrap en rééchantillonnant les cas.
"""

import math
import random
import re
from itertools import combinations
from statistics import mean
from typing import Optional

from eval.truth import TRUTH, grade, graded

K = 8
# Prix indicatifs en dollars par million de tokens (entrée, sortie), novembre 2026.
PRICES = {'ministral-8b': (0.15, 0.15), 'mistral-medium': (1.50, 7.50), 'mistral-small': (0.15, 0.60)}
BOOTSTRAP_SAMPLES = 2000


def cost_usd(usage: list[dict]) -> float:
    total = 0.0
    for u in usage:
        price_in, price_out = next((p for name, p in PRICES.items() if u['model'].startswith(name)), (0.0, 0.0))
        total += (u['input_tokens'] * price_in + u['output_tokens'] * price_out) / 1e6
    return total


def _dcg(grades: list[int]) -> float:
    return sum((2 ** g - 1) / math.log2(rank + 2) for rank, g in enumerate(grades))


def ndcg(proposed: list[int], ideal: list[int]) -> Optional[float]:
    """nDCG@8 : qualité du choix et de l'ordre, rapportée au meilleur résultat possible."""
    best = _dcg(sorted(ideal, reverse=True)[:K])
    return _dcg(proposed[:K]) / best if best else None


def score_run(case: dict, rec: dict) -> dict:
    """Valeurs d'une exécution pour chaque métrique. None quand la métrique ne s'applique pas."""
    ids = [i for i in rec['contact_ids']]
    out: dict[str, Optional[float]] = {}

    out['routage'] = None if case['intent'] == 'any' else float(rec['intent'] == case['intent'])
    if 'tool' in case:
        tools = rec['tools']
        out['outil'] = float(not tools) if case['tool'] == 'none' else float(case['tool'] in tools)

    if 'target' in case:
        target, previous = case['target'], set(rec.get('previous_ids', []))
        grades = [grade(i, target) if i else 0 for i in ids]
        ideal = [g for cid, g in graded(target).items() if cid not in previous]
        if ids:
            out['precision'] = mean(g >= 1 for g in grades)
            out['precision_stricte'] = mean(g == 2 for g in grades) if any(g == 2 for g in ideal) else None
            if not target.get('abroad') and 'name' not in target:
                out['france'] = mean(TRUTH[i]['country'] == 'France' for i in ids if i in TRUTH) \
                    if any(i in TRUTH for i in ids) else None
        out['ndcg'] = ndcg(grades, ideal)
        # Réponse utile : au moins un contact pertinent proposé quand il en existe.
        if ideal:
            out['reponse_utile'] = float(any(g >= 1 for g in grades))

    if case.get('expect_empty'):
        out['vide_attendu'] = float(not ids and not rec['hunter_ids'])
    if 'count' in case:
        out['nombre_respecte'] = float(len(ids) == case['count'])
    if 'setup' in case:
        out['sans_doublon'] = float(not set(ids) & set(rec.get('previous_ids', []))) if ids else None
    if 'min_hunters' in case:
        out['cabinets'] = float(len(rec['hunter_ids']) >= case['min_hunters'])

    text = rec['message']
    checks = [s.lower() not in text.lower() for s in case.get('must_not_contain', [])]
    checks += [not re.search(p, text, re.IGNORECASE) for p in case.get('must_not_regex', [])]
    if 'max_chars' in case:
        checks.append(len(text) <= case['max_chars'])
    if checks:
        out['texte_conforme'] = float(all(checks))

    if rec['intent'] == 'recherche' and 'rejected_ids' in rec:
        proposed = len(rec['rejected_ids']) + len(ids) + len(rec['hunter_ids'])
        out['ids_inventes_par_le_modele'] = len(rec['rejected_ids']) / proposed if proposed else None
    if 'cards' in rec and rec['cards']:
        out['fiches_inventees'] = mean(c['status'] == 'inventee' for c in rec['cards'])
        out['fiches_alterees'] = mean(c['status'] == 'alteree' for c in rec['cards'])
    if 'judge' in rec:
        out['message_fidele'] = float(rec['judge']['fidele'])

    out['latence_s'] = rec['latency_s']
    out['tokens'] = float(sum(u['input_tokens'] + u['output_tokens'] for u in rec['usage']))
    out['cout_usd'] = cost_usd(rec['usage'])
    out['echec_technique'] = float(rec['outcome'] != 'ok')
    return out


def per_case(cases: list[dict], records: list[dict]) -> dict[str, dict[str, float]]:
    """Moyenne de chaque métrique par cas : {métrique: {id du cas: valeur}}."""
    by_id = {c['id']: c for c in cases}
    values: dict[str, dict[str, list[float]]] = {}
    for rec in records:
        for name, value in score_run(by_id[rec['case']], rec).items():
            if value is not None:
                values.setdefault(name, {}).setdefault(rec['case'], []).append(value)
    return {name: {cid: mean(v) for cid, v in by_case.items()} for name, by_case in values.items()}


def bootstrap_ci(values: list[float], seed: int = 0) -> tuple[float, float]:
    """Intervalle de confiance à 95 % de la moyenne, par rééchantillonnage des cas."""
    if len(values) < 2:
        return (values[0], values[0]) if values else (float('nan'), float('nan'))
    rng = random.Random(seed)
    means = sorted(mean(rng.choices(values, k=len(values))) for _ in range(BOOTSTRAP_SAMPLES))
    return means[int(0.025 * BOOTSTRAP_SAMPLES)], means[int(0.975 * BOOTSTRAP_SAMPLES) - 1]


def summarize(by_metric: dict[str, dict[str, float]]) -> dict[str, dict]:
    summary = {}
    for name, by_case in by_metric.items():
        values = list(by_case.values())
        low, high = bootstrap_ci(values)
        summary[name] = {'moyenne': mean(values), 'ic95': [low, high], 'cas': len(values)}
    return summary


def percentile(values: list[float], p: float) -> float:
    ordered = sorted(values)
    return ordered[min(len(ordered) - 1, round(p / 100 * (len(ordered) - 1)))]


def stability(records: list[dict]) -> dict:
    """Stabilité entre les exécutions d'un même cas.

    - `jaccard` : recouvrement moyen des contacts proposés, deux exécutions à la fois
      (1 = mêmes contacts à chaque fois, 0 = aucun en commun) ;
    - `intention_constante` : part des cas dont toutes les exécutions ont la même intention.
    """
    runs: dict[str, list[dict]] = {}
    for rec in records:
        runs.setdefault(rec['case'], []).append(rec)
    jaccards, same_intent = [], []
    for recs in runs.values():
        same_intent.append(float(len({r['intent'] for r in recs}) == 1))
        sets = [set(r['contact_ids']) for r in recs]
        if len(sets) > 1 and any(sets):
            jaccards.append(mean(len(a & b) / len(a | b) if a | b else 1.0 for a, b in combinations(sets, 2)))
    return {'jaccard': mean(jaccards) if jaccards else None, 'cas_jaccard': len(jaccards),
            'intention_constante': mean(same_intent) if same_intent else None}


def paired_comparison(before: dict[str, float], after: dict[str, float], seed: int = 0) -> Optional[dict]:
    """Compare deux variantes sur les cas communs : différence moyenne, IC à 95 % et test de permutation.

    Le test apparié tire au hasard le signe de chaque différence : sous l'hypothèse « aucune
    différence », le signe est indifférent. La valeur p est la part des tirages au moins aussi
    extrêmes que la différence observée.
    """
    common = sorted(set(before) & set(after))
    if len(common) < 2:
        return None
    diffs = [after[c] - before[c] for c in common]
    observed = mean(diffs)
    rng = random.Random(seed)
    extreme = sum(abs(mean(d * rng.choice((-1, 1)) for d in diffs)) >= abs(observed) - 1e-12
                  for _ in range(BOOTSTRAP_SAMPLES))
    low, high = bootstrap_ci(diffs, seed)
    return {'cas': len(common), 'avant': mean(before[c] for c in common), 'apres': mean(after[c] for c in common),
            'difference': observed, 'ic95': [low, high], 'p': extreme / BOOTSTRAP_SAMPLES}
