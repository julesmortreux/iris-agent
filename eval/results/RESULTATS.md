# Résultats de l'évaluation

47 cas, 3 exécutions par cas. Modèles : recherche `ministral-8b-2512`, conversation `mistral-medium-2604`, juge `mistral-medium-2604`.

Les valeurs sont des moyennes par cas, suivies de leur intervalle de confiance à 95 % (bootstrap sur les cas).

## Version de référence

| Métrique | Valeur [IC 95 %] | Cas | Ce que ça mesure |
|---|---|---|---|
| routage | 100 % [100 % ; 100 %] | 41 | Part des cas où l'intention détectée (recherche ou conversation) est la bonne. |
| outil | 99 % [98 % ; 100 %] | 41 | Part des cas où l'outil attendu a été appelé (ou aucun outil, quand aucun n'est attendu). |
| precision | 99 % [98 % ; 100 %] | 28 | Part des contacts proposés qui sont pertinents (note 1 ou 2). |
| precision_stricte | 79 % [70 % ; 88 %] | 26 | Part des contacts proposés qui répondent exactement à la demande (note 2). |
| ndcg | 0.74 [0.63 ; 0.83] | 30 | nDCG@8 : qualité du choix et de l'ordre, de 0 à 1, rapportée au meilleur résultat possible. |
| reponse_utile | 90 % [80 % ; 98 %] | 30 | Part des cas où au moins un contact pertinent est proposé, quand il en existe. |
| france | 85 % [79 % ; 91 %] | 25 | Part des contacts proposés basés en France, hors demande d'un autre pays. |
| vide_attendu | 100 % [100 % ; 100 %] | 13 | Part des cas sans réponse possible où aucun contact n'est présenté. |
| nombre_respecte | 100 % [100 % ; 100 %] | 3 | Part des cas où le nombre de contacts demandé est exactement respecté. |
| sans_doublon | 100 % [100 % ; 100 %] | 3 | Part des demandes de suite qui ne répètent aucun contact déjà montré. |
| cabinets | 100 % [100 % ; 100 %] | 3 | Part des demandes de chasseurs de tête qui présentent au moins un cabinet. |
| texte_conforme | 100 % [100 % ; 100 %] | 9 | Part des cas dont le texte respecte les interdits (email, nom, consigne détournée). |
| ids_inventes_par_le_modele | 0 % [0 % ; 1 %] | 31 | Part des identifiants proposés par le modèle que le validateur a écartés. |
| message_fidele | 77 % [66 % ; 89 %] | 38 | Part des messages d'introduction jugés fidèles aux fiches par le juge LLM. |
| echec_technique | 0 % [0 % ; 0 %] | 47 | Part des exécutions terminées par une réponse de secours (délai, limite d'appels). |
| latence_s | 3.0 s [2.7 s ; 3.3 s] | 47 | Durée moyenne d'une réponse, en secondes. |
| tokens | 3734 [3234 ; 4203] | 47 | Nombre moyen de tokens consommés par réponse (entrée et sortie). |
| cout_usd | 0.00066 $ [0.00063 $ ; 0.00070 $] | 47 | Coût moyen d'une réponse, en dollars. |

Latence : médiane 3.1 s, 95e centile 5.5 s.

Stabilité : recouvrement moyen des contacts entre deux exécutions du même cas (Jaccard) 0.84 sur 28 cas ; intention identique d'une exécution à l'autre dans 100 % des cas.

## Par famille de cas

| Famille | Cas | routage | precision | ndcg | texte_conforme |
|---|---|---|---|---|---|
| chasseurs | 3 | 100 % | n/d | n/d | 100 % |
| entreprise_poste | 8 | 100 % | 100 % | 0.68 | n/d |
| hors_perimetre | 3 | 100 % | n/d | n/d | 100 % |
| injection | 3 | n/d | n/d | n/d | 100 % |
| nom | 3 | 100 % | 100 % | 0.89 | n/d |
| pagination | 3 | 100 % | 94 % | 0.79 | n/d |
| piege_celebrite | 2 | 100 % | 100 % | 0.55 | 100 % |
| piege_email | 2 | 100 % | 100 % | 0.50 | 100 % |
| piege_nombre | 3 | 100 % | 100 % | 1.00 | n/d |
| piege_sans_resultat | 2 | 100 % | n/d | 0.00 | n/d |
| salutation | 3 | 100 % | n/d | n/d | n/d |
| secteur | 6 | 100 % | 100 % | 0.79 | n/d |
| synonymes | 3 | 100 % | 100 % | 0.81 | n/d |
| vague | 3 | n/d | n/d | n/d | n/d |

## Expérience 1 : sélection d'identifiants ou fiches rédigées par le modèle

| Métrique | reference | fiches_libres |
|---|---|---|
| ids_inventes_par_le_modele | 0 % [0 % ; 1 %] | n/d |
| fiches_inventees | n/d | 0 % [0 % ; 0 %] |
| fiches_alterees | n/d | 0 % [0 % ; 0 %] |
| precision | 99 % [98 % ; 100 %] | 97 % [92 % ; 100 %] |
| ndcg | 0.74 [0.63 ; 0.83] | 0.72 [0.63 ; 0.81] |
| latence_s | 3.0 s [2.7 s ; 3.3 s] | 4.1 s [3.5 s ; 4.7 s] |
| tokens | 3734 [3234 ; 4203] | 3747 [3006 ; 4855] |

## Expérience 2 : ordre du lot transmis au modèle

| Métrique | reference | ordre_api | ordre_aleatoire | score_seul |
|---|---|---|---|---|
| precision | 99 % [98 % ; 100 %] | 100 % [99 % ; 100 %] | 99 % [97 % ; 100 %] | 92 % [79 % ; 100 %] |
| precision_stricte | 79 % [70 % ; 88 %] | 79 % [68 % ; 89 %] | 75 % [61 % ; 87 %] | 71 % [56 % ; 85 %] |
| ndcg | 0.74 [0.63 ; 0.83] | 0.76 [0.66 ; 0.85] | 0.73 [0.65 ; 0.82] | 0.53 [0.34 ; 0.72] |
| france | 85 % [79 % ; 91 %] | 87 % [80 % ; 94 %] | 87 % [80 % ; 93 %] | 85 % [76 % ; 92 %] |
| reponse_utile | 90 % [80 % ; 98 %] | 98 % [95 % ; 100 %] | 98 % [95 % ; 100 %] | 65 % [45 % ; 85 %] |

## Expérience 2 bis : même comparaison avec un lot réduit à 10 contacts

| Métrique | lot10_score | lot10_api | lot10_aleatoire |
|---|---|---|---|
| precision | 100 % [100 % ; 100 %] | 100 % [100 % ; 100 %] | 99 % [98 % ; 100 %] |
| precision_stricte | 85 % [76 % ; 93 %] | 86 % [77 % ; 93 %] | 68 % [52 % ; 82 %] |
| ndcg | 0.77 [0.67 ; 0.86] | 0.69 [0.58 ; 0.79] | 0.66 [0.55 ; 0.77] |
| france | 89 % [82 % ; 95 %] | 93 % [86 % ; 98 %] | 86 % [79 % ; 92 %] |
| reponse_utile | 98 % [95 % ; 100 %] | 95 % [85 % ; 100 %] | 95 % [87 % ; 100 %] |

Score contre ordre aléatoire, precision_stricte, test apparié sur 18 cas : différence +0.171 [+0.046 ; +0.326], p = 0.011.
Score contre ordre aléatoire, ndcg, test apparié sur 20 cas : différence +0.108 [+0.041 ; +0.183], p = 0.011.

## Avant et après les corrections

| Métrique | Cas | Avant | Après | Différence [IC 95 %] | p (test apparié) |
|---|---|---|---|---|---|
| precision | 25 | 99 % | 99 % | +0.000 [-0.015 ; +0.015] | 1.000 |
| precision_stricte | 23 | 80 % | 80 % | -0.005 [-0.065 ; +0.062] | 0.901 |
| ndcg | 30 | 0.59 | 0.74 | +0.143 [+0.052 ; +0.237] | 0.012 |
| nombre_respecte | 3 | 100 % | 100 % | +0.000 [+0.000 ; +0.000] | 1.000 |
| message_fidele | 32 | 39 % | 73 % | +0.344 [+0.208 ; +0.490] | 0.000 |
| reponse_utile | 30 | 76 % | 90 % | +0.144 [+0.033 ; +0.267] | 0.036 |
| echec_technique | 32 | 16 % | 0 % | -0.156 [-0.271 ; -0.052] | 0.016 |
| latence_s | 32 | 4.4 s | 3.4 s | -1.061 [-1.624 ; -0.530] | 0.000 |

## Validation du juge LLM

Annotation humaine en attente : remplir `eval/annotations/a_annoter.csv` puis relancer.
