# ATLAS — Extensions exploratoires : résultats (phase 6)


***Tout est exploratoire** : aucun résultat de cette phase ne modifie les conclusions principales (phases 4 et 5).*

**Reproduction :**

```bash
uv run python scripts/01_download_raw.py --prix
uv run python scripts/16_phase6_build.py
Rscript R/13_maize_gap.R
```

## A. Maïs irrigué et non irrigué

**Données :**

- **Population :** 38 départements dont les surfaces moyennes 2010-2012 de maïs grain irrigué **et** non irrigué dépassent chacune 1 000 ha.
- **Échantillon principal :** les 17 départements dont le maïs irrigué est en statut qualité 1 (270 observations) : 01, 03, 18, 26, 28, 36, 37, 38, 39, 41, 45, 58, 63, 67, 68, 69, 89.
- **Observations retirées :** 2, Jura 2016 et 2018, où la surface irriguée est nulle (artefact probable de la SAA).
- **Météo :** juillet-août, pondération surfacique, faute de masque maïs.

**Observé (descriptif) :**

- l'écart médian irrigué / non irrigué est de +38 % ;
- il varie selon l'année de +16 % (2014, 2021) à +76 % (2020).

**Exposition à la chaleur extrême en juillet-août, plus forte et mieux répartie que pour le blé :**

| Culture et fenêtre | Écart-type résiduel de `dd_32` | N_eff | Principales années |
|---|---|---|---|
| Maïs, juillet-août | 1,00 | 6,9 | 2023, 2019, 2025 |
| Blé, mai-juin | 0,55 | 4,1 | 2019, 2025, 2022 |

**Estimations** (effets fixes département et année, pondérées ; `reports/tables/phase6_mais.csv`) :

| Échantillon | Variable expliquée | Terme | Estimation | p, WCR par année | p, cluster département | p, Conley 200 km |
|---|---|---|---|---|---|---|
| Principal (17) | **écart log irrigué − non irrigué** | `dd_32_ja` | **+0,038** | **0,029** | 0,001 | < 0,001 |
| Principal (17) | écart | `swi_ja` | −0,242 | 0,183 | < 0,001 | < 0,001 |
| Principal (17) | log rendement non irrigué | `dd_32_ja` | **−0,061** (−5,9 %) | **0,001** | < 0,001 | < 0,001 |
| Principal (17) | log rendement non irrigué | `swi_ja` | +0,225 | 0,342 | 0,015 | 0,028 |
| Principal (17) | log rendement irrigué | `dd_32_ja` | −0,023 | 0,013 | 0,002 | 0,010 |
| Principal (17) | log rendement irrigué | `swi_ja` | −0,017 | 0,849 | 0,69 | 0,74 |
| Tous statuts (38) | écart | `dd_32_ja` | +0,029 | 0,064 | < 0,001 | < 0,001 |
| Tous statuts (38) | écart | `swi_ja` | −0,435 | **< 0,001** | < 0,001 | < 0,001 |


**Taille des inférences sur ces données** (placebo = champ réel `dd_32_ja` à années permutées, R = 200 ; `phase6_mais_taille.csv`) :

| Variable expliquée | Cluster département | Conley 200 km | WCR par année |
|---|---|---|---|
| Écart | 23,5 % | 35,0 % | **4,0 %** |
| Non irrigué | 27,0 % | 33,5 % | **8,0 %** |

Comme pour le blé, cluster et Conley sont fortement surdimensionnés, et seul le WCR est jugé fiable. Sa taille (4,0 % pour l'écart, 8,0 % pour le non irrigué, avec une erreur Monte-Carlo d'environ 1,5 point) reste sous 10 % ; pour le non irrigué, elle est environ deux erreurs-types au-dessus de 5 % : le WCR y rejette peut-être un peu trop souvent, comme le suggérait déjà le premier calcul (7,0 %).



**Interprétation (prudente) :**

- Les **signes vont dans le sens de H4** : davantage de chaleur extrême en juillet-août s'accompagne d'un écart irrigué / non irrigué plus grand, et un sol plus humide d'un écart plus petit.
- Le coefficient de chaleur sur l'écart passe le WCR (p = 0,03) dans l'échantillon principal, mais pas avec tous les statuts (p = 0,06). Pour le SWI, c'est l'inverse.
- Le résultat le plus net est l'**association négative entre chaleur de juillet-août et rendement du maïs non irrigué** : −6 % par °C·jour au-delà de 32 °C, avec p = 0,001 au WCR (taille 8,0 %). Pour le maïs irrigué, elle est environ 2,5 fois plus faible (−2,3 %).
- La comparaison avec le blé est cohérente avec une **différence d'exposition**, pas forcément de sensibilité : le maïs subit la chaleur de juillet-août, plus intense et plus variable d'une année à l'autre, alors que le blé est récolté avant le cœur de l'été.

**Limites, qui interdisent une lecture causale de l'irrigation :**

- 12 tests rapportés sans correction pour tests multiples ;
- partage irrigué / non irrigué en partie construit par la SAA (statut 2 ou 3 pour 21 des 38 départements) ;
- composition des surfaces irriguées endogène ;
- restrictions d'eau les années sèches ;
- absence de masque maïs ;
- 17 départements seulement dans l'échantillon principal.

## B. Valorisation des écarts de production de blé tendre d'hiver (descriptif)

**Prix :**

- IPPAP du blé tendre (INSEE, idbank 010776425), raccordé à Eurostat par **0,2504 €/q par point d'indice**, avec un écart maximal de 0,0008 sur 2012-2016. Le raccord est vérifié par un test.
- Eurostat 2010-2011 (rapport 0,19) : rupture de série, non utilisé.
- La valeur unitaire implicite des comptes de l'agriculture avait été écartée : son rapport au prix Eurostat variait de 0,65 à 1,14.

**Écart à une année normale**, c'est-à-dire au rendement moyen du département sur 2010-2025 hors année *t* (`reports/tables/phase6_pertes_valeur.csv`) :

| Année | Production (Mq) | Écart en volume (Mq) | En % de la production normale | Prix (€/q) | Écart en valeur |
|---|---|---|---|---|---|
| **2016** | 275,5 | **93,6** | **25,3 %** | 20,1 | **≈ 1,9 Md€** |
| **2024** | 254,5 | **46,7** | **15,5 %** | 28,1 | **≈ 1,3 Md€** |
| 2020 | 289,5 | 13,8 | 4,6 % | 25,0 | ≈ 0,35 Md€ |
| 2011 | 339,2 | 16,5 | 4,6 % | 28,3 | ≈ 0,47 Md€ |
| 2015 (meilleure année) | 408,9 | −46,6 | −12,8 % | 22,3 | ≈ −1,0 Md€ |
| 2019 | 394,1 | −43,2 | −12,3 % | 23,4 | ≈ −1,0 Md€ |

**Lecture :** ce sont des écarts de production valorisés au prix de l'année. Ce ne sont **ni des pertes attribuées à la météo, ni des pertes de revenu** :

- le prix réagit lui-même aux récoltes françaises et mondiales ;
- l'assurance et les aides ne sont pas prises en compte ;
- les surfaces de l'année sont observées, et non contrefactuelles.

## C. NDVI (MOD13Q1 v6.1, via AppEEARS)

**Accès.**

- Compte NASA Earthdata de l'auteur ; jeton AppEEARS rangé dans `.env`, jamais affiché ni versionné.
- Deux commandes AppEEARS : un test sur 2022, puis 2010-2021 et 2023-2025.
- 354 fichiers au total, 5,0 Go, dans `data/raw/nasa_appeears/`, empreintes au manifeste. Le SHA-256 annoncé par AppEEARS est vérifié pour chaque fichier.

**Protocole :**

- pixels de fiabilité 0 ou 1 ;
- pixel → maille SIM → département avec les poids du masque blé ;
- composites utilisables seulement s'ils sont **terminés avant** la date de prévision (test `tests/test_phase6.py`) ;
- valeurs manquantes imputées par la moyenne du département sur les années d'entraînement du pli.

**Contrôles.**

- 112 composites, soit 7 par an d'avril à juin.
- 98 % des composites ont une valeur pour les 95 départements, et au plus 1,0 % de valeurs manquantes pour une variable (1,13 % dans les 83 départements de l'échantillon principal, ceux de la prévision).
- Profil saisonnier plausible pour le blé (2022) : NDVI médian de 0,59 (fin mars) à 0,71 (début mai), puis 0,62 (fin juin, sénescence).

**Limite principale :** le NDVI est celui des **mailles de 8 km pondérées par le blé**, et non des seules parcelles de blé. Il mélange les couverts.

**Résultats** (variante principale, années test 2016-2025 ; `reports/tables/phase6_ndvi_synthese.csv`) :

| Date | Modèle | Gain par rapport au même modèle **sans** NDVI | IC à 95 % de l'écart de MSE, bootstrap (protocole) | IC à 95 %, Student (ajouté) | Années meilleures (test des signes) | *Skill* par rapport à **B0** (IC de l'écart à B0) |
|---|---|---|---|---|---|---|
| 1er juin | RIDGE | +1,6 % | [−0,0015 ; +0,0007] | [−0,0018 ; +0,0009] | 8/10 (p = 0,11) | −25 % (contient 0) |
| 1er juin | RF | +2,5 % | **[−0,0012 ; −0,0002]** | **[−0,0012 ; −0,0001]** | 9/10 (p = 0,021) | −12 % (contient 0) |
| 1er juin | GBM | +3,5 % | **[−0,0022 ; −0,00005]** | [−0,0024 ; +0,0003] | 8/10 (p = 0,11) | −20 % (contient 0) |
| 1er juillet | RIDGE | +27,7 % | **[−0,0222 ; −0,0011]** | [−0,0234 ; +0,0026] | 6/10 (p = 0,75) | −15 % (contient 0) |
| 1er juillet | RF | +2,7 % | **[−0,0014 ; −0,0002]** | [−0,0015 ; +0,00002] | 7/10 (p = 0,34) | −11 % (contient 0) |
| 1er juillet | GBM | +7,6 % | **[−0,0045 ; −0,0002]** | [−0,0048 ; +0,0004] | 8/10 (p = 0,11) | −12 % (contient 0) |

*Colonnes Student et test des signes ajoutées ensuite : avec 10 années, le bootstrap percentile est environ 18 % plus étroit que l'intervalle de Student et sous-estime l'incertitude.*


**Interprétation (prédictive uniquement) :**

1. **Le NDVI apporte peut-être une information supplémentaire faible** à la météo : le gain est positif dans les 6 combinaisons modèle × date, mais un seul est significatif avec l'intervalle de Student sur 10 années : RF au 1er juin (9 années sur 10), et seulement avec la graine 123 ; avec la graine d'origine, aucun ne l'était. Avec le bootstrap du protocole, 5 sur 6 le sont (4 avec la graine d'origine ; lecture initiale de cette phase). Ce gain reste donc fragile. C'est cohérent avec son rôle d'indicateur intégré de l'état du couvert. Le grand gain de RIDGE au 1er juillet reflète surtout la **stabilisation** d'un modèle instable (phase 5), notamment en 2024.
2. **Il ne suffit pas à battre la moyenne départementale (B0).** Les modèles ajoutent leur correction à B1, une référence à tendance, plus faible que B0 sur toutes les années test. Ce handicap structurel, déjà relevé en phase 5, domine le gain du NDVI.
3. **Piste, non testée ici pour ne pas multiplier les choix a posteriori (testée ensuite comme analyse exploratoire : modèles corrigeant B0, `docs/resultats_complements.md`) :** construire les corrections sur B0 plutôt que sur B1, à pré-spécifier et à évaluer sur de nouvelles années.
4. **2016 n'est pas anticipée avec le NDVI par RF et GBM** (RMSE de 0,41 à 0,43, contre 0,37 pour B0). RIDGE fait mieux que B0 cette année-là (0,31 au 1er juillet, 0,36 au 1er juin), mais il le faisait déjà sans NDVI (0,34 et 0,36), et sa prévision nationale rate la perte (phase 5). Au 1er juin, le couvert ne trahit pas encore la perte, ce qui est cohérent avec un mécanisme de fin de cycle (excès d'eau, maladies, faible rayonnement en juin).
