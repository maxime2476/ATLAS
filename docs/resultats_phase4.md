# ATLAS — Résultats économétriques (phase 4)


*Objectif explicatif : association de court terme entre chocs météo et rendement du blé, 2010-2025.*

**Reproduction :**

```bash
Rscript R/10_fe_models.R
Rscript R/11_robustness.R
```

Environnement R figé par `renv.lock` : R 4.5.2, fixest 0.14.2, nanoparquet 0.5.2, image datée de Posit Package Manager (`.Rprofile`).

## 1. Résultats observés

**Échantillon :**

- 83 départements (statut qualité 1) × récoltes 2010-2025 = 1 328 observations ;
- poids : surface de blé 2010-2012 ;
- effets fixes département et année ;
- météo pondérée par le masque blé.

### Modèles principaux

| Modèle | Terme | Estimation | p, cluster département (83) | p, Conley 200 km | p, bootstrap WCR par année (16) | Effet |
|---|---|---|---|---|---|---|
| M1 | `dd_32_remplissage` | −0,0149 | 0,004 | 0,047 | 0,378 | −1,5 % par °C·jour ; −1,7 % pour l'exposition moyenne de 2019 (1,18 °C·jour) |
| M1 | `gdd_0_32_remplissage` | −0,00051 | 0,001 | 0,041 | 0,265 | −0,05 % par °C·jour |
| M1 | `prec_printemps` | −0,00045 | < 0,001 | 0,026 | 0,095 | −0,045 % par mm |
| M1 | `dd_0_automne` | +0,00023 | 0,007 | 0,189 | 0,507 | +0,02 % par °C·jour |
| M1 | `prec_automne` | −0,00030 | < 0,001 | < 0,001 | 0,185 | −0,03 % par mm |
| M2 | `dd_32_remplissage` | −0,0152 | 0,007 | 0,111 | 0,331 | −1,5 % par °C·jour |
| M2 | `swi_remplissage` | +0,79 | < 0,001 | < 0,001 | 0,211 | — |
| M2 | `swi_remplissage`² | −0,96 | < 0,001 | < 0,001 | 0,152 | — |


R² *within* : 0,084 (M1), 0,203 (M2). Les p-valeurs de Conley utilisent les degrés de liberté par défaut de `fixest` (noyau uniforme, sans dimension temporelle).

**H2, test joint des termes SWI dans M2 :**

| Inférence | Statistique | p |
|---|---|---|
| Cluster département | F = 24,7 | 4 × 10⁻⁹ |
| Conley 200 km | F = 10,1 | 4 × 10⁻⁵ |
| Cluster année, analytique (ajouté ensuite) | F = 1,91 | **0,18** |
| WCR joint par année, Wald, poids de Webb, 9 999 tirages (ajouté ensuite) | W = 4,36 | **0,32** |

Forme de la relation SWI (description) : le sommet est à SWI ≈ 0,41. Seuls 16,6 % de l'échantillon sont en dessous (minimum 0,20, médiane 0,57). Sur la majorité de l'échantillon, un SWI de mai-juin plus élevé est donc **associé** à un rendement plus faible. Le WCR individuel sur δ₁ (p = 0,21) figure dans les tableaux pour conformité à la spécification, mais il n'est **pas interprétable** : δ₁ est la pente à SWI = 0, hors du support observé.

**p-valeur unilatérale pour H1** (WCR, P(t* ≤ t)) : 0,19 dans M1, 0,17 dans M2.


**Placebo** (chaleur extrême de *t*+1, récoltes 2010-2024, 1 245 observations, 15 grappes année) : −0,0018, p = 0,72 / 0,78 / 0,91. L'échantillon diffère de M1, et un placebo nul ne valide pas l'identification.

### Robustesses pour le coefficient de chaleur extrême (spécification M1)

| Code | Spécification | Estimation | p, cluster | p, Conley | p, WCR année |
|---|---|---|---|---|---|
| — | M1 (référence) | −0,0149 | 0,004 | 0,047 | 0,378 |
| R1 | Sans pondération | −0,0159 | 0,034 | *non fiable* † | 0,340 |
| R2 | Sans 84, 30, 48 | −0,0147 | 0,005 | 0,055 | 0,388 |
| R3 | Sans 2025 | **−0,0290** | < 0,001 | < 0,001 | 0,139 |
| R4 | 85 départements | −0,0151 | 0,003 | 0,042 | 0,370 |
| R5 | Seuil de 30 °C (`dd_30`) | −0,0070 | 0,004 | 0,076 | 0,400 |
| R6 | Météo pondérée par la surface | −0,0127 | 0,006 | 0,036 | 0,441 |
| R7 | + tendances régionales | −0,0125 | 0,038 | *non fiable* † | 0,444 |
| R8 | Panel long 1990-2025 (**36 grappes année**, l'inférence par année la mieux dotée) | −0,0100 | 0,038 | 0,171 | 0,419 |
| R9 | Conley 300 km | −0,0149 | 0,004 | *non fiable* † | 0,378 |
| R10 | Fenêtre mai-juillet | **+0,0036** | 0,243 | 0,499 | 0,658 |
| R11 | Fenêtre −2 semaines (16 avr. - 15 juin) ‡ | −0,158 | < 0,001 | 0,014 | 0,350 |
| R12 | Fenêtre +2 semaines (16 mai - 15 juil.) | −0,0065 | 0,167 | 0,354 | 0,571 |
| R13 | Sans montagne (04, 05, 12, 15, 43, 48, 73) | −0,0152 | 0,004 | 0,050 | 0,375 |
| R14 | Classes de température : jours à 30-33 °C | −0,017 | 0,291 | *non fiable* † | 0,738 |
| R14 | Classes de température : jours ≥ 33 °C | −0,021 | 0,298 | *non fiable* † | 0,701 |


† Matrice de Conley non définie positive, « corrigée » automatiquement par `fixest` : p-valeur non interprétée.

‡ Dans la fenêtre avancée, l'exposition au-delà de 32 °C est quasi nulle : moyenne 0,02 °C·jour, maximum 1,37, et seules 0,8 % des observations dépassent 0,5. Le coefficient par °C·jour n'est donc pas interprétable ; pour l'exposition moyenne de 2019, l'effet vaut −0,01 %.

**R11 à R14 ont été ajoutées après les premières estimations**. Elles viennent de `scripts/12_build_semimonthly.py` (demi-mois et classes) et de `scripts/13_cell_altitude.py` (altitude).

**Exposition selon la fenêtre** (83 départements, 2010-2025) :

| Fenêtre | Moyenne de `dd_32` | Maximum | Part > 0,5 °C·jour | Écart-type résiduel | N_eff |
|---|---|---|---|---|---|
| 16 avr. - 15 juin | 0,02 | 1,37 | 0,8 % | 0,08 | 4,68 |
| Mai-juin (référence) | 0,37 | 8,89 | 20,0 % | 0,55 | 4,13 |
| 16 mai - 15 juil. | 0,57 | 11,97 | 28,7 % | 0,73 | 5,54 |
| Mai-juillet | 1,14 | 16,37 | 46,7 % | 1,01 | 4,84 |

**R14, toutes les classes** (jours passés dans la classe en mai-juin, référence 15-18 °C, `reports/tables/phase4_classes_temperature.csv`) :

| Classe | < 9 | 9-12 | 12-15 | 18-21 | 21-24 | 24-27 | 27-30 | 30-33 | ≥ 33 |
|---|---|---|---|---|---|---|---|---|---|
| Coefficient (log-rendement par jour) | +0,008 | +0,010 | +0,000 | +0,006 | +0,002 | −0,001 | −0,020 | −0,017 | −0,021 |
| Erreur-type, cluster année | 0,008 | 0,004 | 0,009 | 0,006 | 0,012 | 0,015 | 0,030 | 0,043 | 0,046 |

### Diagnostics ajoutés ensuite

**Leave-one-year-out** (β de `dd_32_remplissage`, M1, `reports/tables/phase4_loyo.csv`) :

- l'estimation varie de **−0,0290** (sans 2025) à **−0,0059** (sans 2022) ;
- elle reste négative dans les 16 cas ;
- sans 2012, 2016 ou 2022, elle s'affaiblit (−0,006 à −0,011) ; sans 2020 ou 2025, elle se renforce.

C'est un estimateur qui dépend de quelques années, comme le laissait prévoir la concentration de l'exposition.

**Taille et puissance des inférences sur ces données** (`R/12_diagnostics.R`, `phase4_simulation_inference.csv`).

Le régresseur placebo est le champ réel `dd_32_remplissage` dont on **permute les années**, avec la même permutation pour tous les départements et sans année fixe. Il garde la structure spatiale et la concentration de l'exposition, mais n'a plus de lien avec les rendements. R = 300 tirages, B = 399 pour le WCR. L'erreur Monte-Carlo sur un taux de 5 % est de 1,3 point.

| Effet réel ajouté | Cluster département | Conley 200 km | WCR par année |
|---|---|---|---|
| 0 (**taille**, attendue à 5 %) | **58,3 %** | **42,7 %** | **3,0 %** |
| −0,015 (puissance) | 70,3 % | 52,3 % | 8,7 % |
| −0,03 (puissance) | 84,0 % | 75,7 % | 28,7 % |



**Validation de l'implémentation du WCR :**

- la statistique t du WCR (variance CR0, sans facteur de petit échantillon) est identique au t CR0 de `fixest` en cluster par année : −1,040 (recalcul indépendant ; le t CR1 de `fixest` vaut −0,973) ;
- un premier test de taille, avec un placebo iid, donnait 8,7 % de rejets à cause d'un **bug** : y* n'était pas re-projeté sur les effets fixes et les contrôles. Après correction, il donne 6,6 % (R = 500). Ce test était peu informatif, car son placebo, absorbé par l'effet fixe année, était un bruit iid ;
- la simulation ci-dessus le remplace. Un **second bug**, dans le script de simulation lui-même (priorité de l'opérateur `<`, qui donnait 0 % de rejets partout), a été corrigé avant toute lecture des résultats.

## 2. Interprétation

Compléments ajoutés après les premières estimations et intégrés ci-dessus : H2 sous inférence par année, valeurs NA, leave-one-year-out, simulation réaliste, p unilatérale.

### Observé

- **Chaleur extrême.** À département et année donnés, 1 °C·jour de plus au-delà de 32 °C en mai-juin est associé à un log-rendement plus faible d'environ 0,015 (≈ −1,5 %). Le signe est négatif dans la spécification principale, dans 8 des 9 robustesses prévues qui changent le coefficient (R9 ne change que le seuil de Conley) et dans les 16 estimations *leave-one-year-out*. Il s'inverse avec la fenêtre mai-juillet (R10 : +0,0036, non significatif).
- **Inférence.** La simulation montre que, sur ces données, seule l'inférence par année (WCR) a la bonne taille. Le cluster par département et Conley rejettent à tort dans 58 % et 43 % des cas sous H0. Avec le WCR, aucun coefficient météo n'est significatif : p bilatérale ≥ 0,14 pour la chaleur extrême, quelle que soit la spécification (H1 étant unilatérale, la plus petite p unilatérale est 0,070, sans 2025 en R3 ; 0,19 pour M1) ; p = 0,32 pour le test joint du SWI.
- **Puissance.** Le WCR ne détecte un vrai effet de −1,5 % par °C·jour que dans 9 % des cas, et de −3 % que dans 29 % (31 % avec une autre graine).

### Interprétation

1. **H1 (chaleur extrême) n'est pas établie** selon la règle de décision : le résultat ne résiste pas aux trois inférences. Il est **compatible** avec un effet négatif de la chaleur extrême, mais il n'est ni démontré ni exclu.
2. **H2 (effet propre de l'eau) n'est pas établie non plus.** La forte significativité en cluster département et en Conley n'est pas crédible, puisque ces inférences sont fortement sur-dimensionnées sur ces données. De plus, le SWI est un produit de modèle qui dépend en partie de la température (médiateur) : son coefficient est associatif.
3. **La raison est structurelle, pas technique.** Les chocs de rendement sont corrélés entre départements une même année, au-delà de 200 km. Une fois les effets fixes retirés, l'information effective se réduit à quelques années (N_eff ≈ 4,1 pour la chaleur extrême). **Seize récoltes ne suffisent pas** pour une inférence fiable sur des effets de cet ordre : c'est un résultat de puissance, pas une preuve d'absence d'effet.
4. **Un profil décroissant avec la fenêtre, non significatif.** Le coefficient de chaleur extrême s'affaiblit à mesure que la fenêtre avance dans l'été : −0,015 (mai-juin), −0,0065 (16 mai - 15 juillet), +0,004 (mai-juillet). Ce profil est **compatible** avec une sensibilité maximale autour de la floraison (fin mai - début juin, d'après Nóia Júnior et al. 2025) plutôt qu'en fin de remplissage, mais aucune de ces estimations n'est significative avec le WCR, et les fenêtres, de longueurs et d'expositions différentes, donnent des coefficients par °C·jour peu comparables. La fenêtre de référence n'est pas changée a posteriori. La fenêtre avancée (R11) n'est pas informative, faute d'exposition.
5. **Classes de température (R14).** La forme est celle attendue, avec une réponse négative à partir de 27-30 °C et des classes fraîches légèrement positives, mais elle est **très imprécise** : erreurs-types en cluster année de 0,03 à 0,05 pour les classes chaudes. Elle concorde qualitativement avec les seuils publiés (Schlenker & Roberts 2009 ; Gammans et al. 2017), sans les confirmer.
6. **Montagne (R13).** Exclure les 7 départements où au moins 25 % du blé est cultivé au-dessus de 600 m ne change pas l'estimation (−0,0152). La moindre fiabilité de SAFRAN en altitude ne semble pas expliquer le résultat.

### Formulations à proscrire

- « la chaleur extrême réduit le rendement de 1,5 % par °C·jour » ;
- « H1 confirmée » ;
- « l'eau a un effet propre robuste » ;
- « placebo nul, donc identification validée » ;
- toute extrapolation au changement climatique.

### Formulation retenue

« Les départements plus exposés à la chaleur extrême en mai-juin, une même année, ont en moyenne des rendements plus faibles (environ −1,5 % par °C·jour au-delà de 32 °C). Mais, avec seize récoltes et des chocs corrélés à l'échelle nationale, cette association n'est pas distinguable de zéro par une inférence de taille correcte. »

### Conséquences pour la suite

- Le panel long (R8, 36 grappes) est la seule voie pour gagner en puissance, mais ses limites ont été documentées.
- Le module prédictif (phase 5) doit s'attendre à un gain faible de la météo sur une référence naïve.
