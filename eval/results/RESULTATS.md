# Résultats de l'évaluation

7 cas, 1 exécutions par cas. Modèles : recherche `ministral-8b-2512`, conversation `mistral-medium-2604`, juge `mistral-medium-2604`.

Les valeurs sont des moyennes par cas, suivies de leur intervalle de confiance à 95 % (bootstrap sur les cas).

## Version de référence

| Métrique | Valeur [IC 95 %] | Cas | Ce que ça mesure |
|---|---|---|---|
| routage | 100 % [100 % ; 100 %] | 6 | Part des cas où l'intention détectée (recherche ou conversation) est la bonne. |
| outil | 100 % [100 % ; 100 %] | 6 | Part des cas où l'outil attendu a été appelé (ou aucun outil, quand aucun n'est attendu). |
| precision | 100 % [100 % ; 100 %] | 3 | Part des contacts proposés qui sont pertinents (note 1 ou 2). |
| precision_stricte | 78 % [67 % ; 100 %] | 3 | Part des contacts proposés qui répondent exactement à la demande (note 2). |
| ndcg | 0.65 [0.24 ; 0.98] | 4 | nDCG@8 : qualité du choix et de l'ordre, de 0 à 1, rapportée au meilleur résultat possible. |
| reponse_utile | 75 % [25 % ; 100 %] | 4 | Part des cas où au moins un contact pertinent est proposé, quand il en existe. |
| france | 94 % [83 % ; 100 %] | 3 | Part des contacts proposés basés en France, hors demande d'un autre pays. |
| vide_attendu | 100 % [100 % ; 100 %] | 2 | Part des cas sans réponse possible où aucun contact n'est présenté. |
| nombre_respecte | 100 % [100 % ; 100 %] | 1 | Part des cas où le nombre de contacts demandé est exactement respecté. |
| sans_doublon | 100 % [100 % ; 100 %] | 1 | Part des demandes de suite qui ne répètent aucun contact déjà montré. |
| cabinets | 100 % [100 % ; 100 %] | 1 | Part des demandes de chasseurs de tête qui présentent au moins un cabinet. |
| texte_conforme | 100 % [100 % ; 100 %] | 2 | Part des cas dont le texte respecte les interdits (email, nom, consigne détournée). |
| ids_inventes_par_le_modele | 0 % [0 % ; 0 %] | 4 | Part des identifiants proposés par le modèle que le validateur a écartés. |
| message_fidele | 80 % [40 % ; 100 %] | 5 | Part des messages d'introduction jugés fidèles aux fiches par le juge LLM. |
| echec_technique | 14 % [0 % ; 43 %] | 7 | Part des exécutions terminées par une réponse de secours (délai, limite d'appels). |
| latence_s | 4.4 s [2.7 s ; 6.0 s] | 7 | Durée moyenne d'une réponse, en secondes. |
| tokens | 2664 [1146 ; 3885] | 7 | Nombre moyen de tokens consommés par réponse (entrée et sortie). |
| cout_usd | 0.00056 $ [0.00038 $ ; 0.00066 $] | 7 | Coût moyen d'une réponse, en dollars. |

Latence : médiane 5.3 s, 95e centile 7.2 s.

## Par famille de cas

| Famille | Cas | routage | precision | ndcg | texte_conforme |
|---|---|---|---|---|---|
| chasseurs | 1 | 100 % | n/d | n/d | 100 % |
| entreprise_poste | 1 | 100 % | 100 % | 1.00 | n/d |
| injection | 1 | n/d | n/d | n/d | 100 % |
| pagination | 1 | 100 % | 100 % | 0.96 | n/d |
| piege_nombre | 1 | 100 % | 100 % | 0.65 | n/d |
| piege_sans_resultat | 1 | 100 % | n/d | 0.00 | n/d |
| salutation | 1 | 100 % | n/d | n/d | n/d |

## Expérience 1 : sélection d'identifiants ou fiches rédigées par le modèle

| Métrique | reference | fiches_libres |
|---|---|---|
| ids_inventes_par_le_modele | 0 % [0 % ; 0 %] | n/d |
| fiches_inventees | n/d | 0 % [0 % ; 0 %] |
| fiches_alterees | n/d | 0 % [0 % ; 0 %] |
| precision | 100 % [100 % ; 100 %] | 100 % [100 % ; 100 %] |
| ndcg | 0.65 [0.24 ; 0.98] | 0.49 [0.00 ; 0.99] |
| latence_s | 4.4 s [2.7 s ; 6.0 s] | 4.6 s [3.9 s ; 5.3 s] |
| tokens | 2664 [1146 ; 3885] | 1498 [0 ; 2997] |

## Avant et après les corrections

| Métrique | Cas | Avant | Après | Différence [IC 95 %] | p (test apparié) |
|---|---|---|---|---|---|
| precision | 3 | 100 % | 100 % | +0.000 [+0.000 ; +0.000] | 1.000 |
| precision_stricte | 3 | 80 % | 78 % | -0.022 [-0.333 ; +0.267] | 1.000 |
| ndcg | 4 | 0.63 | 0.65 | +0.023 [+0.000 ; +0.066] | 0.508 |
| message_fidele | 4 | 75 % | 75 % | +0.000 [-0.750 ; +0.750] | 1.000 |
| reponse_utile | 4 | 75 % | 75 % | +0.000 [+0.000 ; +0.000] | 1.000 |
| echec_technique | 4 | 25 % | 25 % | +0.000 [+0.000 ; +0.000] | 1.000 |
| latence_s | 4 | 4.1 s | 5.8 s | +1.686 [+0.557 ; +3.298] | 0.134 |

## Validation du juge LLM

Annotation humaine en attente : remplir `eval/annotations/a_annoter.csv` puis relancer.
