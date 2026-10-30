# ATLAS — Résultats de la phase 4 bis


*Graine du bootstrap : 123. Les p-valeurs bootstrap ont une erreur de Monte-Carlo d'environ 0,002 pour p ≈ 0,05 avec 9 999 tirages, ce qui suffit à faire passer la réplication d'un côté ou de l'autre de 0,05 selon la graine (0,049 à 0,051).*

**Scripts et sorties :**

- `Rscript R/14_q1_maize.R` puis `uv run python scripts/24_valorisation_mais.py` (Q1) ;
- `Rscript R/15_q2_wheat.R` (Q2) ;
- tables : `reports/tables/phase4bis_*.csv`.

**Inférence :** seule la p-valeur du wild cluster bootstrap restreint par année (WCR, 9 999 tirages) fonde les conclusions. Le cluster par département et Conley sont donnés pour information ; leurs tailles empiriques, mesurées ci-dessous sur ces mêmes données, sont de 15 à 26 %.

---

## Q1 : irrigation et chaleur, maïs grain

**Échantillon :** 17 départements (statut qualité 1), 2000-2025, 435 paires département-année.

**Taille du test principal** (placebo à années permutées, R = 300, B = 399, unilatéral à 5 %) :

| Inférence | Taille empirique |
|---|---|
| Cluster département | 14,7 % |
| Conley 200 km | 21,3 % |
| **WCR par année** | **3,7 %** |


Le test WCR respecte son niveau nominal ; les deux autres sont fortement surdimensionnés.

### Hypothèse principale et réplication

| | β (`dd_32_ja`, écart log irrigué − non irrigué) | Effet par °C·jour | IC 90 % (CR1 année) | p WCR unilatérale | n |
|---|---|---|---|---|---|
| **H1, 2000-2025** | **+0,0158** | **+1,6 %** | [0,0030 ; 0,0286] | **0,007** | 435 |
| Réplication 2000-2009 (années jamais utilisées) | +0,0108 | +1,1 % | non rapporté (CR1 non fiable à 10 grappes) | 0,051 | 165 |

**Résultat observé :**

- **H1 est établie selon la règle de décision** (p = 0,007 < 0,05 et taille de 3,7 % ≤ 10 %), au sens de cette règle seulement : 270 des 435 paires (62 %) appartiennent à 2010-2025, la période dont l'analyse exploratoire (phase 6) a suggéré l'hypothèse. La seule preuve nouvelle est la décennie 2000-2009, ci-dessous.
- Chaque degré-jour au-dessus de 32 °C en juillet-août est associé, **à humidité du sol (SWI) donnée**, à un écart de rendement plus large d'environ 1,6 % en faveur du maïs irrigué. Le SWI dépend en partie de la chaleur (médiateur) : sans lui, l'estimation vaut 1,7 % (p = 0,001).
- Sur les dix années 2000-2009, que l'analyse exploratoire de la phase 6 n'avait pas vues, l'estimation garde **le même signe avec le masque maïs, pour un effet environ deux fois plus faible** (+1,1 % contre +2,5 % sur 2010-2025 avec le même masque).
- **Cette réplication dépend de la mesure de la chaleur.** Avec la pondération surfacique utilisée en phase 6, l'estimation sur 2000-2009 est nulle (−0,0009 ; § « Diagnostics exploratoires »). Elle n'est donc pas convergente avec la mesure de la phase 6.
- Avec 10 grappes, la taille du WCR, mesurée ensuite, est de 4,7 % ; mais sa puissance contre un vrai effet de 0,011 n'est que de 8 % : une p de 0,051 est une preuve faible. La p bilatérale vaut 0,10.

**Interprétation :** une association significative selon la règle de décision, mais **sensible à la mesure de la chaleur**. Ce n'est pas un effet causal de l'irrigation. Les parcelles irriguées diffèrent des autres (sols, exploitations, variétés). Les effets fixes département et année absorbent ces différences seulement si elles sont stables, et non si elles varient avec la chaleur de l'année.

### Hypothèses secondaires (Holm, 4 tests)

| Code | Estimation | p WCR unilatérale | p Holm | Conclusion |
|---|---|---|---|---|
| H2a : un sol plus humide est associé à un écart plus faible (`swi_ja`) | −0,352 par unité de SWI | 0,013 | 0,026 | Soutenue |
| H2b : la chaleur est associée à un rendement non irrigué plus faible | −2,5 % par °C·jour | < 1/9 999 (aucun tirage n'atteint t ; le CSV affiche 0) | ≤ 4/9 999 | Soutenue |
| H2c : la chaleur pénalise aussi le maïs irrigué | −1,0 % par °C·jour | 0,001 | 0,004 | Soutenue |
| H3 : les jours de crise VigiEau réduisent la protection (2016-2025) | Interaction **positive** (+0,0008) | 0,956 | 0,956 | **Non soutenue**, signe opposé |


- **Lecture d'ensemble :** le maïs irrigué présente une sensibilité à la chaleur plus faible, mais non nulle. Son rendement est associé à −1 % par °C·jour, contre −2,5 % pour le non irrigué.
- **H3 :** le signe opposé n'est pas interprétable causalement. Une conjecture, **non testée**, est que les arrêtés de crise sont pris lors des étés les plus secs, où l'écart est le plus grand. L'indicateur de crise est grossier (« au moins une zone du département »), il n'y a que 10 années (taille du WCR non vérifiée à 10 grappes), et l'IC CR1 de la table n'est pas fiable.

### Robustesses de A1 (terme `dd_32_ja`, p WCR unilatérale)

| Spécification | β | p | n |
|---|---|---|---|
| Principal | 0,0158 | 0,007 | 435 |
| R1 : 38 départements | 0,0217 | 0,005 | 981 |
| R2 : 2010-2025 | 0,0242 | 0,027 | 270 |
| **R3 : météo pondérée par la surface** | **0,0104** | **0,219** | 435 |
| R4 : seuil de 30 °C | 0,0104 | 0,006 | 435 |
| R5 : juillet seul | 0,0575 | 0,013 | 435 |
| R6 : sans pondération | 0,0185 | 0,025 | 435 |
| R7 : sans 2025 | 0,0157 | 0,015 | 418 |
| R8 : sans 2003 | 0,0243 | 0,029 | 418 |


- **Signe :** positif dans les 9 spécifications.
- **Significativité :** 8 sur 9 au seuil de 5 %.
- **Exception :** avec la météo pondérée par la surface (R3), le coefficient n'est pas significatif (p = 0,22).
  - Ce n'est **pas** une simple atténuation par erreur de mesure. Avec cette pondération, l'estimation sur 2010-2025 est même **plus forte** (0,038 contre 0,024). L'écart vient de 2000-2009 (−0,0009 contre +0,011), une période dominée par 2003.
  - Le résultat de Q1 dépend donc de la mesure de la chaleur pour les années 2000-2009. **Le qualificatif « robuste » n'est pas justifié.**
- **2003 :** le résultat ne repose pas uniquement sur la canicule de 2003 (R8 : 0,024 sans 2003, taille non vérifiée pour cette variante). Sur 2000-2009 sans 2003, les deux mesures de la chaleur divergent toujours (0,038 avec le masque, 0,009 avec la pondération surfacique ; `phase4bis_q1_exploratoire.csv`, exploratoire).

### Valorisation descriptive (17 départements, conditionnelle à β̂)

**Prix :** IPPAP maïs × 0,2192 €/q par point ; raccord stable sur 2012-2016 (écart maximal 0,0009 < 0,002).

| Été | Écart moyen à la normale de `dd_32_ja` (°C·jour, pondéré) | Quintaux associés à l'irrigation | Valeur (M€) | Fourchette (M€), IC 90 % par inversion du WCR |
|---|---|---|---|---|
| 2003 | +13,7 | 2,98 millions | **49** | 16 à 172 |
| 2019 | +2,5 | 0,43 million | 9 | 3 à 27 |
| 2022 | +1,9 | 0,33 million | 14 | 5 à 40 |


- **Ce que mesurent ces chiffres :** des **quintaux associés** à l'irrigation lors d'un été plus chaud que la normale de chaque département, pour les 17 départements de l'échantillon (160 847 à 212 786 ha irrigués selon l'année).
- **Convention de calcul :** la formule s'applique au rendement non irrigué, ce qui est prudent. Appliquée au rendement irrigué, Y_I × (1 − exp(−βΔ)), elle donnerait environ 29 % de plus en 2003 (`\ValAltPct` du mémoire, script 26).
- **Euros courants :** 2022 vaut plus que 2019 malgré moins de quintaux, parce que le prix passe de 21 à 41 €/q. Ce n'est **pas** la valeur totale de l'irrigation, qui inclut aussi l'avantage moyen de l'irrigué, ni un gain causal.
- **Pourquoi 2022 pèse peu :** sa sécheresse est mal captée par la seule chaleur au-dessus de 32 °C dans ces départements.
- **Fourchette :** elle repose sur l'intervalle à 90 % de β obtenu par inversion du WCR ; un premier calcul utilisait l'IC du cluster par année (CR1) prévu par la spécification (8 à 98 M€ en 2003), dont la taille n'était pas vérifiée. C'est une indication seulement.
- **Extrapolation :** la formule applique à tout l'excès de chaleur de l'été, part nationale comprise, une pente identifiée par les écarts entre départements une même année ; dans la régression, la part nationale est absorbée par les effets année.
- **Fourchette de mesure de 2003 (ajoutée ensuite) :** aux poids de la valorisation, la formule dépasse de 89 % la valeur obtenue avec l'écart observé (26 M€), et de 28 % hors des deux paires reconduites de 2002 (Loiret, Eure-et-Loir) ; au prix Eurostat observé de 2003 (13,2 €/q contre 16,4 €/q raccordé), la formule donne 39 M€. La valorisation de 2003 est donc rapportée comme une fourchette de **21 à 49 M€**. En 2019 et 2022, l'écart observé donne au contraire plus que la formule (40 et 65 M€).

---

## Q2 : sensibilité du blé à la chaleur, 1959-2025

**Échantillon :** 83 départements, 5 543 observations, 67 récoltes (18 rendements manquants retirés, tous en 1959-1967).

**Taille de Q2-H1 :** WCR 4,7 % ; cluster département 25,7 % ; Conley 19,3 %.


| | β₂ (`dd_32_remplissage`) | Effet par °C·jour | p WCR unilatérale | p cluster département (information) |
|---|---|---|---|---|
| **Q2-H1, 1959-2025** | **−0,0108** | **−1,1 %** | **0,125** | 0,014 |

**Résultat observé :** **Q2-H1 n'est pas établie.** Le signe est négatif et l'ordre de grandeur proche de la phase 4 (−1,5 %). Mais un résultat aussi négatif n'est pas rare sous l'hypothèse nulle (environ une fois sur huit) quand on tient compte de la dépendance par année. L'échantillon inclut celui de la phase 4 : ce n'est donc pas une réplication indépendante.

Quadrupler le nombre d'années (67 contre 16) n'a augmenté N_eff que de 4,1 à 6,2 : l'exposition reste concentrée sur quelques étés.

### Q2-H2 : la sensibilité a-t-elle changé ? (descriptif)

| Période | Pente | p WCR bilatérale |
|---|---|---|
| 1959-1981 | −0,0014 | 0,80 |
| 1982-2003 | −0,0279 | 0,17 |
| 2004-2025 | −0,0113 | 0,50 |

Test WCR joint d'égalité des pentes : Wald = 1,80, **p = 0,48**. Aucune évolution de la sensibilité n'est détectable. L'absence de preuve n'est pas une preuve de stabilité : la puissance est faible.

### Robustesses de B1 (p WCR unilatérale à gauche)

| Spécification | β₂ | p |
|---|---|---|
| Principal | −0,0108 | 0,125 |
| R1 : + tendances régionales | −0,0119 | 0,098 |
| R2 : sans 2025 | −0,0165 | 0,024 |
| R3 : 1968-2025 | −0,0113 | 0,104 |
| R4 : effet fixe département unique | −0,0113 | 0,117 |
| R5 : seuil de 30 °C | −0,0062 | 0,094 |


- **Signe :** négatif partout.
- **Significativité :** une seule robustesse est significative, sans 2025 (données provisoires). Ce n'est **pas** une raison de modifier la conclusion principale : retenir la spécification qui « marche » serait de la recherche de spécification.

---

## Diagnostics exploratoires (ajoutés ensuite)

Script `R/16_q1_exploratoire.R` ; table `reports/tables/phase4bis_q1_exploratoire.csv`. Ce sont des estimations ponctuelles, **sans inférence**.

| β de A1 | Masque maïs | Pondération surfacique |
|---|---|---|
| 2000-2025 | 0,0158 | 0,0104 |
| 2000-2009 | 0,0108 | −0,0009 |
| 2010-2025 | 0,0242 | 0,0381 |
| Sans 2003 | 0,0243 | 0,0365 |
| 2000-2009 sans 2003 | 0,0380 | 0,0091 |

Les deux mesures concordent hors 2000-2009. La divergence se concentre sur cette décennie, et en particulier sur la façon dont chaque mesure traite 2003.

## Robustesse Q1-R9 : masque maïs d'époque (2008)

Cette robustesse a été ajoutée après les premières estimations.

**Méthode :**

- îlots RPG 1.0 de 2008, groupe « maïs grain et ensilage », régions des 17 départements ;
- scripts `scripts/25_build_maize_mask_2008.py` et `R/17_q1_mask2008.R`.

| | β (`dd_32_ja`) | Effet par °C·jour | p WCR unilatérale | n |
|---|---|---|---|---|
| A1, masque 2015-2017 (principal) | 0,0158 | +1,6 % | 0,007 | 435 |
| **Q1-R9, masque 2008** | **0,0153** | **+1,5 %** | **0,006** | 435 |

- **Corrélation des expositions (toutes années) :** 0,997 entre les deux masques maïs, contre 0,955 entre le masque 2015-2017 et la pondération surfacique.
- **Lecture fixée d'avance :** l'anachronisme du masque ne menace pas H1.
- **Origine de la divergence avec R3** (table `phase4bis_q1_mesures_departement.csv`) : elle est concentrée dans les départements de relief. En 2003, la pondération surfacique donne beaucoup moins de chaleur que le masque maïs : −10,3 °C·jour pour le Puy-de-Dôme, −8,5 pour l'Isère, −8,0 pour la Drôme, −7,5 pour le Jura, −4,2 pour le Rhône et −4,0 pour l'Ain. Dans les départements de plaine (Centre-Val de Loire, Bourgogne), l'écart est inférieur à 1,2 °C·jour.
- **Interprétation (a posteriori) :** dans ces départements, le maïs est cultivé dans les plaines et les vallées chaudes. La pondération surfacique y mesure surtout la chaleur des reliefs, sans maïs. Le masque maïs, désigné comme mesure principale, mesure vraisemblablement mieux la chaleur subie par les surfaces en maïs ; aucune vérité terrain ne permet de le démontrer.
- **Ce qui reste inexpliqué :** pourquoi la pondération surfacique donne un coefficient plus fort sur 2010-2025.

## Synthèse

| Question | Conclusion principale | Statut |
|---|---|---|
| Q1-H1 : la chaleur creuse l'écart irrigué / non irrigué | p = 0,007, taille 3,7 % ; réplication 2000-2009 de même signe avec le masque maïs seulement ; inchangé avec un masque d'époque (R9 : p = 0,006) | **Établie** selon la règle, sur un échantillon qui inclut à 62 % les années exploratoires (association ; non significative avec la pondération surfacique, qui semble sous-mesurer la chaleur dans les départements de relief, explication a posteriori). Compléments ultérieurs : signe robuste, significativité fragile ; non significative sans les six départements de relief (p = 0,152) ni avec le jackknife CV3 lu sur une loi de Student (p = 0,074 ; bootstrappé, p = 0,019). Première preuve confirmatoire attendue du test figé sur les récoltes 2026-2030 |
| Q2-H1 : la chaleur en fin de cycle réduit le rendement du blé | p = 0,125, taille 4,7 % | **Non établie** |
| Q2-H2 : la sensibilité du blé a changé depuis 1959 | p = 0,48 | Non détectée, et peu informatif : la pente de chaque période repose sur un ou quelques étés très chauds (1976, 2003, puis surtout 2019, 2022 et 2025) |

**Limites principales :**

- **Composition et sélection :** lors des sécheresses, une partie du maïs non irrigué semé pour le grain peut être récoltée en ensilage, ce qui modifie le rendement observé du maïs grain non irrigué. L'abandon, lui, reste dans les statistiques : la SAA compte les surfaces non récoltées avec un rendement nul. Si ce sont les pires parcelles non irriguées qui partent en ensilage, le rendement non irrigué observé est surestimé les années chaudes et l'écart est biaisé vers le bas, contre le résultat ; sans cette hypothèse, le sens du biais n'est pas connu.
  - Contrôle descriptif : la part irriguée de l'année n'est pas liée de façon détectable à `dd_32_ja` (−0,0025 par °C·jour, p = 0,58 en cluster année, information seulement).
  - Ce contrôle ne couvre pas le passage du grain à l'ensilage, décidé après le semis.

- **Interprétation :** associative pour l'irrigation.
- **Statut qualité :** celui de 2025 est appliqué à 2000-2009.
- **Sensibilité à la mesure :** Q1 n'est pas significatif avec la météo pondérée par la surface, et la réplication 2000-2009 n'existe qu'avec le masque maïs, choisi après la phase 6.
- **Masques :** le masque maïs est fixe (2015-2017) ; le masque blé est appliqué à 1959, ce qui est anachronique.
- **Ruptures de source :** en 1989 et 2010, absorbées en niveau mais pas en pente.
- **VigiEau :** indicateur grossier.

## Diagnostics ajoutés dans un second temps : puissance et taille de Q1

Script `R/19_q1_power_size.R`, table `reports/tables/phase4bis_q1_puissance.csv`. Placebo de `R/14` (champ réel `dd_32_ja` à années permutées), WCR unilatéral à droite, 5 %, R = 300, B = 399.

| Diagnostic | Vrai effet ajouté | Rejets à 5 % | Erreur Monte-Carlo |
|---|---|---|---|
| H1, 2000-2025 (26 grappes) | 0 (contrôle de la taille) | 3,7 % | 1,1 point |
| | 0,008 (moitié de l'estimation) | 28,3 % | 2,6 points |
| | 0,016 (environ l'estimation) | 71,7 % | 2,6 points |
| Réplication 2000-2009 (10 grappes) | 0 (taille) | 4,7 % | 1,2 point |
| | 0,011 (environ l'estimation) | 8,3 % | 1,6 point |


**Lecture :**

- La puissance est descriptive. Le test de H1 avait près de trois chances sur quatre de détecter un effet de la taille estimée, et un peu plus d'une sur quatre pour un effet moitié moindre. Le contrôle sous H0 (3,7 %) est identique à la taille de `R/14` : depuis que le WCR tire sous une graine locale, les deux scripts utilisent les mêmes permutations.
- Réplication : la taille (4,7 %) est au plus de 10 %, donc la p de la réplication (0,051) est rapportée avec cette taille. Sa puissance est très faible (8 %) : un résultat « significatif » avec une telle puissance est peu informatif et peut surestimer l'effet. La réplication reste lue comme « de même signe », sans confirmation de l'ampleur.


## Vérification ajoutée dans un second temps : chaleur E-OBS au lieu de SIM

Scripts `scripts/27_eobs_heat.py` et `R/20_q1_eobs.R` ; tables `reports/tables/phase4bis_q1_eobs.csv` et `phase4bis_q1_eobs_departement.csv`.

| | SIM (A1) | E-OBS |
|---|---|---|
| β (par °C·jour > 32 °C, juillet-août) | 0,0158 | 0,0148 |
| p WCR unilatérale à droite | 0,007 | 0,0039 |
| Écart-type intra-département de la chaleur | 3,63 | 4,87 |
| Effet d'un écart-type intra-département | ≈ 5,9 % | ≈ 7,5 % |

Corrélation des deux mesures : 0,952 (0,953 en intra-département). Moyennes départementales 2000-2025 : 1,0 à 3,9 °C·jour avec SIM, 2,6 à 7,3 avec E-OBS.

**Lecture :** β > 0 et p < 0,05, donc H1 ne dépend pas de la source de température. Réserves : E-OBS et SAFRAN partagent une partie des stations françaises ; seul A1 est réestimé ; `swi_ja` reste celui de SIM ; l'hypothèse de départ supposait à tort qu'E-OBS donnerait moins de degrés-jours que SIM.

## Intervalle de β, départements, humidité du sol, décennies (ajoutés ensuite)

Script `R/21_q1_verifications.R` ; tables `reports/tables/phase4bis_q1_verif_*.csv`. WCR par année, 9 999 tirages.

| Analyse | Résultat | Lecture |
|---|---|---|
| Intervalle de β (A1, inversion du WCR) | 90 % : [0,0055 ; 0,0441] ; 95 % : [0,0045 ; 0,0497] | Descriptive : signe soutenu, ampleur imprécise (facteur 8) |
| Intervalle, blé phase 4 (M1, H1) | β = −0,0149 ; 95 % : [−0,0792 ; +0,0243] | Intervalle prévu par la spécification de la phase 4, enfin calculé |
| Sans chaque département | β de 0,0117 à 0,0185 ; p < 0,05 dans 17 cas sur 17 | Descriptive |
| Sans les six départements de relief (01, 26, 38, 39, 63, 69) | β = 0,0098, p unilatérale = 0,152, 11 départements | **H1 dépend de ces départements** |
| Sans SWI | β = 0,0173, p = 0,001 | — |
| P − ETP à la place du SWI | β = 0,0124, p = 0,039 ; corrélation intra DD>32 / bilan : −0,47 | **L'association ne dépend pas du contrôle d'humidité retenu** ; chaleur et sécheresse restent mêlées |
| Interaction × 2000-2009 | −0,0113, p bilatérale = 0,49 ; sans 2003 : +0,0106, p = 0,76 | Descriptive : aucune différence détectée entre décennies |

La fourchette de valorisation de 2003 est recalculée aux bornes de l'intervalle à 90 % de β : 16 à 172 M€ (au lieu de 8 à 98 M€ avec l'intervalle groupé par année).
