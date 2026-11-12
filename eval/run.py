"""Évaluation complète d'Iris en une commande.

Usage : python -m eval.run            (toutes les variantes, 3 exécutions par cas)
        python -m eval.run --runs 1 --variants reference --cases ep-lvmh,sal-bonjour

Le script démarre la fausse API, joue chaque cas avec chaque variante, fait noter les
messages par le juge, puis écrit eval/results/resultats.json et eval/results/RESULTATS.md.
Chaque exécution est mise en cache (eval/.cache) : une relance ne rappelle le modèle que
pour ce qui a changé (code du backend, cas, variante ou modèle).
"""

import argparse
import asyncio
import csv
import hashlib
import json
import logging
import random
import threading
from dataclasses import asdict
from pathlib import Path
from typing import Optional

import yaml
from werkzeug.serving import make_server

from backend import agent, api_client, config
from backend.agent import Options
from eval import baselines, judge, metrics, report

HERE = Path(__file__).parent
ROOT = HERE.parent
CACHE = HERE / '.cache'
RESULTS = HERE / 'results'
ANNOTATIONS = HERE / 'annotations'

RANKING_CATEGORIES = {'entreprise_poste', 'secteur', 'synonymes', 'piege_nombre'}
CONTACT_CATEGORIES = RANKING_CATEGORIES | {'nom', 'pagination', 'piege_sans_resultat', 'piege_celebrite',
                                           'piege_email'}
FREE_CATEGORIES = {'entreprise_poste', 'secteur', 'nom', 'synonymes', 'piege_sans_resultat', 'piege_celebrite'}

# Portage fidèle de l'original : toutes les corrections issues de l'évaluation sont désactivées.
PORTAGE_FIDELE = Options(enforce_count=False, strict_company=False, fix_claims=False, empty_search_limit=None,
                         broaden_on_empty=False, neutral_intro=False)

# variante -> (réglages, familles de cas jouées ; None = toutes)
VARIANTS: dict[str, tuple[Optional[Options], Optional[set[str]]]] = {
    'reference': (Options(), None),
    'avant_corrections': (PORTAGE_FIDELE, CONTACT_CATEGORIES),
    'fiches_libres': (None, FREE_CATEGORIES),
    'ordre_api': (Options(ranking='api'), RANKING_CATEGORIES),
    'ordre_aleatoire': (Options(ranking='random'), RANKING_CATEGORIES),
    # Lot réduit à 10 contacts : reproduit la situation de production, où une recherche
    # renvoie bien plus de contacts qu'on ne peut en transmettre au modèle.
    'lot10_score': (Options(pool_size=10), RANKING_CATEGORIES),
    'lot10_api': (Options(ranking='api', pool_size=10), RANKING_CATEGORIES),
    'lot10_aleatoire': (Options(ranking='random', pool_size=10), RANKING_CATEGORIES),
}
JUDGED_VARIANTS = ('reference', 'avant_corrections')
TRANSIENT = {'erreur', 'routeur_indisponible', 'conversation_indisponible'}
ANNOTATION_SAMPLE = 15


def start_fake_api() -> None:
    """Lance la fausse API dans un thread et pointe le client dessus."""
    from legacy_api.app import API_TOKEN, app
    server = make_server('127.0.0.1', 0, app, threaded=True)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    config.LEGACY_API_BASE_URL = f'http://127.0.0.1:{server.server_port}/api'
    config.LEGACY_API_TOKEN = API_TOKEN


def fingerprint() -> str:
    """Empreinte du code et des modèles : toute modification invalide le cache."""
    digest = hashlib.sha256()
    for path in sorted((ROOT / 'backend').glob('*.py')) + [HERE / 'baselines.py', ROOT / 'eval' / 'ground_truth.json']:
        digest.update(path.read_bytes().replace(b'\r\n', b'\n'))
    digest.update(f'{config.MISTRAL_MODEL}|{config.MISTRAL_CHAT_MODEL}'.encode())
    return digest.hexdigest()[:16]


def _cached(key_parts: list, compute):
    """Renvoie le résultat en cache, ou le calcule et l'enregistre."""
    key = hashlib.sha256(json.dumps(key_parts, ensure_ascii=False, sort_keys=True).encode()).hexdigest()[:24]
    path = CACHE / f'{key}.json'

    async def run():
        if path.exists():
            return json.loads(path.read_text(encoding='utf-8'))
        value = await compute()
        path.write_text(json.dumps(value, ensure_ascii=False), encoding='utf-8')
        return value
    return run()


async def _call(variant: str, message: str, history: list[dict], exclude: list[str]) -> dict:
    options = VARIANTS[variant][0]
    for attempt in range(4):
        if options is None:
            reply = await baselines.answer_free(message, history, exclude)
            transient = reply['trace'].outcome not in ('ok', 'UsageLimitExceeded', 'TimeoutError')
        else:
            reply = await agent.answer(message, history, exclude, options)
            transient = reply['trace'].outcome in TRANSIENT
        if not transient:
            break
        await asyncio.sleep(2 * (attempt + 1))
    return reply


async def play(variant: str, case: dict, run: int) -> dict:
    """Joue un cas une fois et renvoie l'enregistrement de l'exécution."""
    history, exclude, record = [], [], {}
    if 'setup' in case:
        first = await _call(variant, case['setup'], [], [])
        exclude = [c['id'] for c in first['contacts'] if c['id']]
        history = [{'role': 'user', 'content': case['setup']}, {'role': 'assistant', 'content': first['response']}]
        record['previous_ids'] = exclude
    reply = await _call(variant, case['query'], history, exclude)
    trace = reply['trace']
    record.update({
        'case': case['id'], 'variant': variant, 'run': run,
        'intent': trace.intent, 'outcome': trace.outcome, 'tools': reply['sources_used'],
        'tool_calls': trace.tool_calls, 'message': reply['response'],
        'contact_ids': [c['id'] for c in reply['contacts']], 'hunter_ids': [h.get('id') for h in reply['hunters']],
        'shown': [{k: c.get(k, '') for k in ('poste', 'entreprise', 'type_contact')} for c in reply['contacts']],
        'latency_s': round(trace.timings.get('total', 0.0), 3), 'timings': trace.timings, 'usage': trace.usage,
        'rejected_ids': trace.rejected_ids,
    })
    if 'cards' in reply:
        record['cards'] = reply['cards']
        record.pop('rejected_ids')
    return record


async def score_only(case: dict, reference: dict) -> dict:
    """Variante sans sélection par le modèle : les 8 premiers contacts du lot classé par le score.

    Les critères de recherche sont ceux que le modèle a choisis dans l'exécution de référence.
    """
    seen: dict[str, dict] = {}
    for call in reference['tool_calls']:
        if call['tool'] != 'search_contacts' or call.get('refused') or not call.get('returned'):
            continue
        results = await api_client.search_contacts(name=call['name'], position=call['position'],
                                                   company=call['company'], sector=call['sector'])
        for c in results:
            if c['linkedin'] or c['telephone'] or c['email']:
                seen.setdefault(c['id'], c)
    ids = list(seen)[:min(agent.MAX_SHOWN, case.get('count', agent.MAX_SHOWN))]
    return {**reference, 'variant': 'score_seul', 'contact_ids': ids, 'message': '', 'usage': [],
            'latency_s': 0.0, 'rejected_ids': []}


def export_annotations(records: list[dict], queries: dict[str, str]) -> None:
    """Écrit les réponses à annoter à la main, sans le verdict du juge (annotation à l'aveugle)."""
    path = ANNOTATIONS / 'a_annoter.csv'
    if path.exists():
        return
    judged = [r for r in records if 'judge' in r]
    rng = random.Random(7)
    unfaithful = [r for r in judged if not r['judge']['fidele']]
    faithful = [r for r in judged if r['judge']['fidele']]
    rng.shuffle(unfaithful)
    rng.shuffle(faithful)
    sample = unfaithful[:ANNOTATION_SAMPLE // 2]
    sample += faithful[:ANNOTATION_SAMPLE - len(sample)]
    rng.shuffle(sample)
    ANNOTATIONS.mkdir(exist_ok=True)
    with path.open('w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f, delimiter=';')
        writer.writerow(['cle', 'reponse_a_evaluer', 'verdict_humain (fidele ou infidele)'])
        for r in sample:
            text = judge.render(queries[r['case']], r['message'], r['shown'], len(r['hunter_ids']))
            writer.writerow([f"{r['variant']}|{r['case']}|{r['run']}", text, ''])


def judge_agreement(records: list[dict]) -> Optional[dict]:
    """Accord entre le juge et l'annotation humaine, si le fichier a été rempli."""
    path = ANNOTATIONS / 'a_annoter.csv'
    if not path.exists():
        return None
    verdicts = {f"{r['variant']}|{r['case']}|{r['run']}": r['judge']['fidele'] for r in records if 'judge' in r}
    pairs = []
    with path.open(encoding='utf-8-sig', newline='') as f:
        for row in list(csv.reader(f, delimiter=';'))[1:]:
            human = (row[2] if len(row) > 2 else '').strip().lower()
            if human and row[0] in verdicts:
                pairs.append((human.startswith('fid'), verdicts[row[0]]))
    if not pairs:
        return None
    n = len(pairs)
    agree = sum(h == j for h, j in pairs) / n
    p_h, p_j = sum(h for h, _ in pairs) / n, sum(j for _, j in pairs) / n
    expected = p_h * p_j + (1 - p_h) * (1 - p_j)
    kappa = (agree - expected) / (1 - expected) if expected < 1 else 1.0
    return {'reponses_annotees': n, 'accord': agree, 'kappa_de_cohen': kappa,
            'juge_infidele_humain_fidele': sum(h and not j for h, j in pairs),
            'juge_fidele_humain_infidele': sum(j and not h for h, j in pairs)}


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split('\n')[0])
    parser.add_argument('--runs', type=int, default=3)
    parser.add_argument('--variants', default=','.join(VARIANTS))
    parser.add_argument('--cases', default='')
    parser.add_argument('--concurrency', type=int, default=3)
    parser.add_argument('--no-judge', action='store_true')
    args = parser.parse_args()

    logging.basicConfig(level=logging.ERROR)
    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    start_fake_api()
    CACHE.mkdir(exist_ok=True)
    RESULTS.mkdir(exist_ok=True)
    cases = yaml.safe_load((HERE / 'dataset.yaml').read_text(encoding='utf-8'))
    if args.cases:
        cases = [c for c in cases if c['id'] in args.cases.split(',')]
    queries = {c['id']: c['query'] for c in cases}
    code = fingerprint()
    gate = asyncio.Semaphore(args.concurrency)
    done = 0

    async def one(variant: str, case: dict, run: int) -> dict:
        nonlocal done
        async with gate:
            record = await _cached([code, variant, case, run], lambda: play(variant, case, run))
        done += 1
        if done % 20 == 0:
            print(f'  {done} exécutions')
        return record

    jobs = []
    for variant in args.variants.split(','):
        categories = VARIANTS[variant][1]
        jobs += [one(variant, case, run) for case in cases for run in range(args.runs)
                 if categories is None or case['category'] in categories]
    print(f'{len(jobs)} exécutions à jouer (cache : {code})')
    records = list(await asyncio.gather(*jobs))

    if not args.no_judge:
        async def add_verdict(record: dict) -> None:
            async with gate:
                text = [judge.JUDGE_PROMPT, judge.JUDGE_MODEL, queries[record['case']], record['message'],
                        record['shown'], len(record['hunter_ids'])]
                record['judge'] = await _cached(text, lambda: judge.judge(
                    queries[record['case']], record['message'], record['shown'], len(record['hunter_ids'])))
        to_judge = [r for r in records if r['variant'] in JUDGED_VARIANTS and r['intent'] == 'recherche']
        print(f'{len(to_judge)} messages soumis au juge')
        await asyncio.gather(*(add_verdict(r) for r in to_judge))
        export_annotations(records, queries)

    by_id = {c['id']: c for c in cases}
    for ref in [r for r in records if r['variant'] == 'reference' and r['run'] == 0
                and by_id[r['case']]['category'] in RANKING_CATEGORIES]:
        records.append(await score_only(by_id[ref['case']], ref))

    variants = sorted({r['variant'] for r in records})
    results = {'empreinte_du_code': code, 'modeles': {'recherche': config.MISTRAL_MODEL,
                                                      'conversation': config.MISTRAL_CHAT_MODEL,
                                                      'juge': judge.JUDGE_MODEL},
               'executions_par_cas': args.runs, 'cas': len(cases), 'variantes': {}}
    per_case = {}
    for variant in variants:
        recs = [r for r in records if r['variant'] == variant]
        per_case[variant] = metrics.per_case(cases, recs)
        latencies = [r['latency_s'] for r in recs]
        results['variantes'][variant] = {
            'executions': len(recs),
            'metriques': metrics.summarize(per_case[variant]),
            'latence_p50_s': metrics.percentile(latencies, 50), 'latence_p95_s': metrics.percentile(latencies, 95),
            'stabilite': metrics.stability(recs),
            'par_famille': {
                family: metrics.summarize(metrics.per_case(
                    cases, [r for r in recs if by_id[r['case']]['category'] == family]))
                for family in sorted({by_id[r['case']]['category'] for r in recs})
            },
        }
    if {'reference', 'avant_corrections'} <= set(variants):
        results['avant_apres'] = {
            name: metrics.paired_comparison(per_case['avant_corrections'].get(name, {}),
                                            per_case['reference'].get(name, {}))
            for name in ('precision', 'precision_stricte', 'ndcg', 'nombre_respecte', 'message_fidele',
                         'reponse_utile', 'echec_technique', 'latence_s')
        }
    if {'lot10_score', 'lot10_aleatoire'} <= set(variants):
        results['score_contre_aleatoire_lot10'] = {
            name: metrics.paired_comparison(per_case['lot10_aleatoire'].get(name, {}),
                                            per_case['lot10_score'].get(name, {}))
            for name in ('precision_stricte', 'ndcg')
        }
    results['accord_juge_humain'] = judge_agreement(records)

    (RESULTS / 'resultats.json').write_text(json.dumps(results, ensure_ascii=False, indent=1), encoding='utf-8')
    (RESULTS / 'executions.json').write_text(
        json.dumps([{**r, 'timings': r.get('timings', {})} for r in records], ensure_ascii=False, indent=1,
                   default=asdict), encoding='utf-8')
    (RESULTS / 'RESULTATS.md').write_text(report.render(results), encoding='utf-8')
    print(f"Résultats écrits dans {RESULTS}")


if __name__ == '__main__':
    asyncio.run(main())
