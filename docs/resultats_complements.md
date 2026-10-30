# Analyses complémentaires : résultats


**Analyses ajoutées après les estimations principales, exploratoires**. Aucune ne change le statut des hypothèses de la phase 4 bis. Scripts : `scripts/28_complements_python.py`, `R/22_q1_complements.R` ; tables : `reports/tables/phase7_*.csv` (le préfixe `phase7_` désigne ce lot d'analyses, pas une phase du plan initial).

Modèle de base : A1 (écart log irrigué − non irrigué ~ `dd_32_ja` + `swi_ja` | département + année, poids `surface_ref_ha`, 17 départements, 435 paires, β = 0,0158).

## Variables retenues et corrélations

Seules des variables complètes sur la période et l'échantillon ont été retenues : part irriguée du maïs grain (SAA, 2010-2012), et maïs fourrage (SAA, feuille FOU, 2010-2025). Corrélations entre les 17 départements (`phase7_correlations_variables.csv`) :

| | Part irriguée | Écart d'altitude | Relief |
|---|---|---|---|
| Part irriguée | 1 | −0,21 | −0,23 |
| Écart d'altitude (surface − masque) | | 1 | **0,86** |
| Relief (6 départements) | | | 1 |

L'écart d'altitude et l'indicatrice de relief dépassent le seuil retenu de 0,7 : ils ne sont jamais mis dans le même modèle.

## Hétérogénéité de la pente

| Analyse | Estimation | p WCR bilatérale | Lecture |
|---|---|---|---|
| Chaleur × relief | +0,0087 | 0,78 | **Différence non détectée** |
| Pente hors relief (11 départements) | +0,0103 | 0,24 | — |
| Chaleur × part irriguée (centrée) | −0,0212 par unité de part | 0,41 | Non détectée |


- **L'interaction avec le relief répond à la question laissée ouverte par le retrait des départements de relief :** sans les six départements de relief, l'estimation (1,0 %) n'est pas significative, mais la pente des deux groupes ne diffère pas de façon détectable. La perte de significativité est donc compatible avec une simple perte d'information (11 départements), pas nécessairement avec une pente plus faible hors relief.
- **Pentes départementales rétrécies (empirique bayésien, DerSimonian-Laird) :** moyenne 0,0163 ; écart-type entre départements τ = 0,0045 ; test Q d'homogénéité p = 0,20 (erreurs-types hétéroscédastiques, qui ignorent la dépendance entre départements une même année : le test est donc plutôt trop permissif). Les pentes rétrécies vont de 0,012 (Indre) à 0,021 (Isère). Elles sont corrélées à −0,44 avec la part irriguée et à +0,42 avec l'écart d'altitude (17 points, descriptif).
  - les 17 pentes sont fortement corrélées (corrélation médiane 0,80 avec une covariance regroupée par année ; 0,55 déjà en hétéroscédastique). Avec leur covariance complète regroupée par année : τ = 0,0061, mais moyenne commune 0,0221 (au-dessus de β̂(A1) = 0,0158) et Q = 372 pour 16 degrés de liberté (p < 0,001) ; pentes rétrécies de 0,010 à 0,033, corrélées à −0,43 avec la part irriguée et à +0,12 avec l'écart d'altitude. Une covariance estimée sur 26 années rend ce test peu fiable (limite) : sur 300 placebos, il rejette à tort dans 99 % des cas. Calibré par le bootstrap sauvage restreint par année, il donne p = 0,26 : **pas d'hétérogénéité détectable** (`phase7_pentes_homogeneite.csv`). Les pentes rétrécies avec la covariance complète restent descriptives.

## Menaces sur la mesure du rendement

- **Ensilage (2010-2025, 270 paires) :** la part du maïs non irrigué récolté en fourrage (27,7 % en moyenne pondérée) ne varie pas avec la chaleur : +0,0005 par °C·jour, p unilatérale = 0,43. **Passage grain → ensilage non détecté** au niveau départemental. Ce n'est pas une preuve d'absence : les surfaces de fourrage peuvent être déclarées avant la récolte, et 2003 est hors de la période.

## Inférence sur H1

| Méthode | p unilatérale | Remarque |
|---|---|---|
| WCR par année (référence, règle de décision) | 0,007 | — |
| Jackknife par année (CV3), t à 25 ddl | **0,074** | Recommandé par MacKinnon, Nielsen et Webb (2023) avec peu de grappes ; taille mesurée ensuite : 5,7 %, contre 3,7 % pour le WCR |
| Randomisation (5 000 dérangements des années, statistique β̂) | 0,002 | L'effet réel éventuel reste dans l'erreur du placebo |
| DML (forêts aléatoires sur SWI, P, ETP, GDD ; 5 plis formés d'années entières) + WCR | 0,016 (β = 0,0155) ; 0,022 (β = 0,0139, de 0,0092 à 0,0170 ; p < 0,05 dans 92 % des découpages) ; **p = 0,056 en combinant les découpages par deux fois la médiane** (médiane 0,028), β = 0,0134 (de 0,0107 à 0,0172 ; p < 0,05 dans 90 % des découpages) | Contrôles météo non linéaires : β 15,0 % plus bas que A1, **au-delà de la règle des 15 %** (12 % avec la graine d'origine) ; le DML ne confirme pas H1 seul ; lecture sensible à la graine |
| DML, variante Mundlak (moyennes annuelles retirées dans les plis, moyennes départementales des contrôles et de la chaleur en variables ; 50 découpages) | 0,070 (deux fois la médiane ; médiane 0,035) | β = 0,0123 (de 0,0096 à 0,0170), 22 % plus bas que A1 ; p < 0,05 dans 82 % des découpages : la transformation préalable des effets fixes pèse sur le résultat |

**Lecture :** le statut de H1 reste fixé par le WCR (règle de la phase 4 bis). Mais la significativité au seuil de 5 % **dépend de la méthode d'inférence** : le jackknife par grappes donne p = 0,074, avec une taille mesurée de 5,7 %, et le DML, plus petit d'un huitième à un cinquième, ne passe pas le seuil une fois ses découpages combinés correctement. C'est une réserve à citer.

## Taille et levier

| Diagnostic (R = 300) | Taux de rejet à 5 % |
|---|---|
| H1, placebo intra-année (chaleur permutée entre départements chaque année) | 4,0 % |
| H2b (non irrigué), dérangement des années | 3,3 % |
| H2c (irrigué), dérangement des années | 5,7 % |
| Rappel : H1, dérangement (R/14, rejoué à l'identique) | 3,7 % |
| Matrices de Conley corrigées par fixest dans ces placebos | 27 % des répétitions |



- Placebo intra-année ≤ 10 % : **la règle de décision est confortée**. Les tailles de H2b et H2c sont proches du nominal ; leurs p-valeurs peuvent être lues normalement.
- Selon l'année qui reçoit le champ de 2003, le taux de rejet varie de 0 à 25 %, sur 4 à 23 permutations par année : pas d'année anormale (`phase7_placebo_par_annee_2003.csv`).
- Levier partiel dans le modèle A1 pondéré : 2003 porte **41 %** de Σ w x̃² sur 2000-2025 (N_eff = 4,8) et **80 %** sur 2000-2009 (N_eff = 1,5). La réplication 2000-2009 repose donc presque entièrement sur un seul été. Ces chiffres diffèrent de ceux du § 4 du mémoire (26 % et N_eff = 7,1), calculés sur la variance résiduelle non pondérée, sans le SWI.

## Prévision

- **Modèles corrigeant B0 au lieu de B1 (variante 2010, exploratoire, années test déjà vues) :**

| Date | Modèle | Gain sur B0 | IC 95 % de l'écart de MSE, bootstrap | IC 95 %, Student (ajouté) | Années meilleures (test des signes) |
|---|---|---|---|---|---|
| 1er juin | Ridge | −9 % | [−0,0046 ; +0,0080] | [−0,0056 ; +0,0098] | 5/10 (p = 1) |
| 1er juin | Forêt aléatoire | +17 % | [−0,0090 ; −0,0002] | [−0,0094 ; +0,0016] | 8/10 (p = 0,11) |
| 1er juin | Gradient boosting | +11 % | [−0,0069 ; +0,0012] | [−0,0075 ; +0,0024] | 6/10 (p = 0,75) |
| 1er juillet | Ridge | −41 % | [−0,0046 ; +0,0273] | [−0,0101 ; +0,0296] | 4/10 (p = 0,75) |
| 1er juillet | Forêt aléatoire | +17 % | [−0,0083 ; −0,0011] | [−0,0087 ; +0,0008] | **9/10 (p = 0,021)** |
| 1er juillet | Gradient boosting | +18 % | [−0,0091 ; −0,00004] | [−0,0100 ; +0,0014] | 6/10 (p = 0,75) |


**Lecture :** c'est la piste la plus intéressante de ce lot pour la prévision. Construits sur B0, les modèles d'arbres font mieux que B0 en moyenne, de 11 à 18 %. Avec le bootstrap, l'intervalle excluait zéro dans 3 cas sur 4 (forêt aux deux dates, boosting au 1er juillet). Avec l'intervalle de Student, il ne l'exclut dans aucun cas ; sur 10 années, le gain ne se distingue pas du bruit. Avec la graine 123, la forêt au 1er juillet fait mieux que B0 9 années sur 10 (test des signes, p = 0,021, contre 0,11 avec la graine d'origine), mais l'intervalle de Student contient toujours zéro : lecture sensible à la graine, sans changement de conclusion. Cette variante a en outre été choisie après avoir vu que B1 était faible, sur les mêmes années test. Elle doit être **confirmée sur les récoltes 2026 et suivantes**, avec ce protocole figé.

## Température de surface MODIS

MOD11A2 v6.1, LST de jour, composites de 8 jours commençant entre le 1er juillet et le 31 août, masque maïs ; 2 413 département-années sur 2 418 (5 manquantes) ; 434 paires sur 435 dans l'échantillon principal. Script `R/23_q1_lst.R` ; table `reports/tables/phase7_lst.csv`.

| Analyse | Résultat |
|---|---|
| (a) Corrélation de la LST avec `dd_32_ja` | 0,63 (0,63 en intra-département) |
| (b) A1 avec la LST à la place des degrés-jours | +4,2 % d'écart par °C de LST (β = 0,0413), p unilatérale = 0,002 |
| (c) Pente de la LST sur `dd_32_ja` (38 départements), à part irriguée moyenne | 0,21 °C par degré-jour, p bilatérale < 0,001 |
| (c) Interaction avec la part irriguée (centrée) | −0,149, p bilatérale = 0,053 ; pente de 0,23 °C au premier quartile de la part irriguée, 0,19 au troisième |

**Lecture (descriptive) :** l'association tient avec une mesure satellitaire de la chaleur, indépendante de SAFRAN et d'E-OBS (mais prise vers 10 h 30 et sur ciel clair). La surface se réchauffe un peu moins par degré-jour d'air là où la part irriguée est forte, dans le sens d'un refroidissement par l'irrigation (Zhu et Burney 2022), sans que la différence soit significative au seuil de 5 % ; la part irriguée varie aussi avec d'autres caractéristiques des départements. Utile pour la robustesse de la mesure ; le canal du refroidissement reste non établi.

## Réplication, calendrier, variables instrumentales

Script `R/24_q1_fourrage_calendrier_iv.R` ; tables `reports/tables/phase7_fourrage.csv`, `phase7_calendrier.csv`, `phase7_iv.csv`.

| Test | Résultat | Lecture |
|---|---|---|
| Même modèle sur le maïs fourrage irrigué / non irrigué (28 départements, 2010-2025, masque `MIE`) | +1,6 % par °C·jour, p = 0,005, taille 2,7 % : **se réplique** | **Oui** : autre culture, autre récolte, autre masque, estimation presque identique ; mais les statistiques du fourrage reprennent en partie celles du grain (sans les 50 couples concernés, +1,6 %, p = 0,007) |
| Chaleur de l'été suivant (placebo pur) | p = 0,35 : pas d'alerte | Oui : écarte un facteur persistant |
| Juin + juillet-août + septembre | juillet-août +1,3 % (p = 0,024) ; juin +4,7 % (p = 0,13), exposition faible ; septembre sans chaleur (0,04 degré-jour) | Partiellement : septembre n'est pas un test |
| IV par E-OBS | β = 0,0208, 1,3 fois les MCO, F = 65 | Oui : l'atténuation par l'erreur de mesure est d'environ un tiers ; correction plutôt trop faible (stations communes) |
| IV par la LST | β = 0,0386, 2,5 fois les MCO, F = 13 | Peu : exclusion douteuse (refroidissement par l'irrigation) |

## Forme de la relation, extrêmes combinés, déficit de pression de vapeur

Script `R/25_q1_forme_vpd.R` ; tables `reports/tables/phase7_forme.csv`, `phase7_forme_2003.csv`, `phase7_chaleur_sol.csv`, `phase7_vpd.csv` ; VPD construit par `scripts/34_vpd.py`.

| Test | Résultat | Lecture |
|---|---|---|
| Terme quadratique ; tranches 30-32, 32-34, > 34 °C | Courbure non détectée (p = 0,13) ; elle ne corrige pas 2003 ; tranches trop imprécises | Peu : les données ne disent pas où la réponse s'accentue |
| Chaleur × humidité du sol | −0,109, p = 0,20 : signe attendu, non détecté | Peu : étés chauds et secs confondus |
| VPD à la place des degrés-jours | +60 % par kPa, p < 0,001 ; un écart-type : +17,5 % (contre +5,9 % pour les degrés-jours) | **Oui, fortement** |
| VPD et degrés-jours ensemble | VPD +64 % par kPa (p = 0,002) ; degrés-jours −0,2 % (p = 0,76) ; corrélation 0,76 | **Oui** : l'association porte sur la sécheresse de l'air plutôt que sur la chaleur seule (Lobell et al. 2013) ; non séparables |

## VPD sur le fourrage, influence des années, corrélation sérielle, multivers

Script `R/26_q1_annees_multivers.R` ; tables `reports/tables/phase7_vpd_fourrage.csv` à `phase7_multivers.csv`.

| Test | Résultat | Lecture |
|---|---|---|
| VPD sur le maïs fourrage | Seul : p = 0,010 ; avec les degrés-jours, ni l'un ni l'autre significatif (p = 0,12 et 0,30) | Oui, comme limite : la lecture « air sec » n'est pas confirmée sur une seconde culture |
| Retrait de chaque année | β de 0,0134 à 0,0243, significatif 26 fois sur 26 ; 2003 est l'année la plus influente (son retrait augmente β) | Oui : aucune année ne porte seule la significativité |
| Corrélation sérielle simulée | Taille 5,3 %, 5,0 % et 8,0 % pour ρ = 0, 0,3 et 0,6 | Oui : la règle de décision tient, à la limite pour une forte autocorrélation |
| 76 spécifications (multivers) | Toutes positives, 68 significatives ; les 8 autres utilisent la pondération surfacique | **Oui** : seule la mesure de la chaleur compte vraiment |

## Eau d'irrigation

Données : volumes BNPE (Hub'Eau), RA2020_0052 (Agreste). Scripts `scripts/36_volumes_irrigation.py`, `R/27_q1_sol_eau.R` ; tables `reports/tables/phase7_volumes.csv`, `phase7_valeur_m3*.csv`.

| Test | Résultat | Lecture |
|---|---|---|
| Log volume prélevé ~ chaleur (202 département-années, 2012-2023) | +0,4 % par degré-jour, p unilatérale = 0,28 ; VPD p = 0,12 ; SWI −1,60, p = 0,0008 | **Oui** : les volumes suivent la sécheresse du sol, pas la chaleur extrême |
| Valeur apparente du m³ (01, 03, 18, 63, 67, 68) | Dose médiane 1 524 m³/ha ; 2,2 kg de grain et 0,55 € bruts par m³ (0,17 à 0,96 selon le département) ; 8 département-années sur 72 exclus par la règle de dose | Oui, comme ordre de grandeur : au-dessus de la marge de 0,20-0,28 €/m³ estimée par la DRAAF Occitanie sur 2012-2014 (Analyses & Études n° 3, 2017, hors amortissement du matériel ; la même étude donne 1 900 m³/ha et 1,4 kg de maïs par m³), ce qui est attendu pour une valeur brute |
| Valeur du m³, étés chauds | Dose +74 m³/ha par degré-jour (p = 0,04) ; écart +0,36 q/ha (p = 0,86) | Non : le m³ supplémentaire des étés chauds n'est pas mesurable ainsi |

Lecture : la valeur par m³ est **descriptive**. L'écart de rendement observé mêle l'effet de l'eau et les différences entre parcelles irriguées et non irriguées ; la dose repose sur une clé de surface (part du maïs dans la surface irriguée en 2020), ce qui suppose que le maïs reçoit autant d'eau par hectare que les autres cultures irriguées du département ; s'il en reçoit plus, la dose est sous-estimée et la valeur par m³ surestimée. Elle ne compte ni l'énergie, ni le matériel, ni la main-d'œuvre.

## Projections DRIAS

17 simulations Explore2-Climat 2022 corrigées par ADAMONT (historique et RCP 8.5), 1 582 mailles du masque maïs des 17 départements ; scripts `scripts/37_drias_telechargement.py`, `scripts/38_drias_indicateurs.py` ; tables `reports/tables/phase7_drias_*.csv`. Moyennes des 17 départements pondérées comme A1 ; médiane des modèles [étendue].

| Horizon | Degrés-jours > 32 °C (juillet-août) | VPD (kPa) | Écart irrigué − non irrigué impliqué par β × Δ (IC 90 % de β) |
|---|---|---|---|
| 1976-2005 (modèles ; SIM2 : 1,02) | 1,28 [1,00 ; 1,51] | 1,55 | référence |
| France +2,0 °C | 3,8 [0,8 ; 10,5] | 1,78 | +4 % (1-12 %) |
| France +2,7 °C | 7,2 [1,5 ; 12,1] | 1,94 | +10 % (3-29 %) |
| France +4,0 °C | 17,9 [8,9 ; 31,0] | 2,35 | +30 % (10-107 %) |


Repères observés : moyenne 2000-2025 1,9 ; 2019 et 2022 environ 4 ; 2003 14,7. **Lecture :** descriptive ; pratiques, variétés et règles d'eau tenues fixes ; à +4 °C, l'été moyen dépasse 2003 et l'extrapolation sort du support de β. Les fenêtres +2,0 °C de plusieurs modèles sont raccourcies au début (2021).

## Non fait

- **Méthode SAA (partage irrigué / non irrigué) :** les sources publiques consultées décrivent la SAA comme une synthèse des services régionaux, combinant enquêtes (structure, Terres, vergers) et données administratives (ASP, PAC). Elles ne définissent pas « irrigué » : surface irriguée l'année, ou équipée pour l'irrigation. Les PDF méthodologiques d'Agreste demandent désormais une session. La question reste à poser directement au SSP ou à un SRISE. L'enquête Pratiques culturales grandes cultures (2017, 2021, 2025) relève l'irrigation et le rendement à la parcelle : ce serait une source de validation possible, au niveau régional.

## Partage irrigué / non irrigué de la SAA

Scripts `scripts/48_partage_saa.py` et `R/32_q1_partage.R` ; table `reports/tables/phase7_partage_saa.csv`. Exploratoire.

- **Rendement non irrigué calculé à partir de la production :** c'est le cas de 53 % des paires sur 2000-2009 et de 57 % sur 2010-2025. Si le rendement irrigué saisi réagissait trop peu à la chaleur, un rendement non irrigué obtenu par différence élargirait l'écart les étés chauds : ce biais irait dans le sens du résultat.
- **Sans ces paires :** +4,1 % par degré-jour (p = 0,006, 191 paires) ; sur ces seules paires : +1,4 % (p = 0,063) ; les deux pentes ne diffèrent pas de façon détectable (interaction, p bilatérale = 0,24).
- **Rendement total des deux modes,** qui n'utilise pas le partage : les départements plus irrigués ont un rendement moins sensible à la chaleur (interaction +0,038, p unilatérale = 0,022), ce qui va dans le sens de H1 mais repose sur des écarts entre départements.
- **Maïs fourrage :** 50 couples sur 400 ont le même rapport irrigué / non irrigué que le grain, contre 8 attendus par permutation (95ᵉ centile 13) ; sans eux, la réplication donne +1,6 % (p = 0,007).
- **Lecture :** aucun artefact détecté ; un partage fixé à dire d'expert sur les deux modes à la fois resterait indétectable.

## Taille des inférences à composante temporelle

Script `R/33_tailles_temporelles.R` ; table `reports/tables/phase7_tailles_temporelles.csv`. Mêmes tirages placebo que le tableau des tailles.

- **Taille à 5 % sur les cinq tests :** cluster par année 5,0 à 10,0 %, cluster à deux dimensions 6,0 à 10,0 %, Driscoll-Kraay 7,7 à 11,7 % (contre 14,7 à 58,3 % pour le cluster par département).
- **Sur les données :** blé M1 2010-2025, p bilatérale = 0,35 / 0,31 / 0,31 ; H1, p unilatérale = 0,023 / 0,023 / 0,029.
- **Lecture :** le défaut vient des inférences sans composante temporelle ; avec elles, le faux positif du blé disparaît et H1 reste sous 5 %. Le bootstrap par année reste le plus proche de 5 %.

## Taille du jackknife et reconduction des rapports SAA

- **Taille du CV3** : 5,7 %, contre 3,7 % pour le WCR sur les mêmes permutations ; puissance 34 % et 71 % (β = 0,008 et 0,016), contre 28 % et 72 %. Calibré (≤ 8 %) ; le désaccord avec le WCR reste une réserve.
- **Ventilation SAA** : rapport Y_I/Y_R identique à celui de l'année précédente dans 4,3 % des transitions (référence par permutation : 1,0 %, 95ᵉ centile 1,9 %), dont 15 sur 18 dans l'ancienne série (2000-2009) et 2 en 2003 ; pas d'excès de rapports ronds (p = 0,49), pas de rupture en 2010, pas de lien avec la chaleur (p = 0,19). Signature retenue ; sans les 7 départements signalés (au moins un quart de leurs années), β = 1,0 % par degré-jour, p = 0,070 : la menace est à prendre au sérieux.
- Tables `reports/tables/phase7_taille_cv3.csv`, `phase7_signatures_saa.csv` ; script `R/28_q1_cv3_saa.R`.

## Autres vérifications (exploratoires)

Scripts `R/29_q1_chaleur_statut_2026.R`, `scripts/40_recolte_2026.py`, `scripts/41_drias_eau.py` et `scripts/42_drias_eau_swi.py`.

- **Chaleur moyenne SIM2/E-OBS** : 1,6 % par degré-jour, p = 0,004, taille 5,7 % : soutenue avec cette mesure.
- **Statut de qualité** : pente des 21 départements de statut 2 : 2,2 % (p = 0,017) ; écart avec le statut 1 non détectable (p = 0,47).
- **Humidité du sol projetée (DRIAS-Eau)** : ΔSWI de juillet-août −0,04, −0,06, −0,10 ; écart projeté 5 %, 11 %, 34 % avec le sol, contre 4 %, 10 %, 30 % avec la chaleur seule : pas de changement d'ordre de grandeur.
- **Récolte 2026 (estimations au 1er octobre 2026)** : 10,6 degrés-jours, deuxième été le plus chaud après 2003 ; écart médian 150 % ; A1 sur 2000-2026 : 2,4 %, p = 0,001 (« cohérent avec H1 » sur des données provisoires très arrondies). Prévision figée du blé 2026 enregistrée avant comparaison, mais calculée dans la même exécution que la lecture des estimations de conjoncture 2026, qui contiennent les rendements provisoires du blé : ces rendements n'entrent pas dans le calcul, mais la prévision n'est pas aveugle au sens strict, et 2027 sera la première année vraiment prospective. Une version recalculée avec la graine 123 existe à côté ; la prévision enregistrée la première reste celle du test figé.

## Pistes d'amélioration (exploratoires)

- **Inférence avec une année dominante** : 2003 porte 41 % du levier partiel (10,6 fois la part moyenne d'une année), 2023 17 %. La statistique du CV3 (t = 1,49), rapportée à sa distribution par bootstrap restreint par année, donne p = 0,019 avec une taille mesurée de 3,7 % ; rapportée à une Student à 25 ddl, p = 0,074. Le désaccord WCR / CV3 se résout en faveur de H1. SCPC non calculé (choc annuel commun à tout le pays : hors du domaine de la méthode).
- **Variable de résultat** : sans les 18 départements-années dont le rapport Y_I/Y_R est reconduit, β = 1,8 % par degré-jour, p = 0,011 (417 couples). Une lettre au service statistique pose la question ; microdonnées : RICA au CASD (rendement du maïs par mode non confirmé), Pratiques culturales à demander au SSP.
- **Intégration continue** : `.github/workflows/tests.yml` (uv 0.12.18, `uv sync --frozen`, pytest) ; sur une copie neuve, 56 tests passent et ceux qui demandent des données sont sautés.
- Tables `reports/tables/phase7_levier_par_annee.csv`, `phase7_wcr_cv3.csv`, `phase7_sans_reconduits.csv` ; script `R/30_q1_inference.R`.
