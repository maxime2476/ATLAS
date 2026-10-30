# `wcr` — bootstrap par période et vérification de la taille des tests

Module R autonome (un seul fichier, `wcr.R` ; dépendance : `fixest`). Il sert à tester un coefficient de modèle à effets fixes quand les chocs sont **communs à toutes les unités une même période** : météo, prix ou politique nationale.

## Le problème

Dans ces panels, l'exposition et le résidu sont corrélés entre unités une même période, et les effets fixes de période n'en retirent que la moyenne. Les erreurs-types usuelles supposent à tort l'indépendance entre unités. Cela vaut pour le cluster par unité, et seulement en partie pour Conley. Elles rejettent alors l'hypothèse nulle bien plus souvent que le niveau annoncé.

**Exemple simulé** (`exemple.R`) : 40 régions × 25 années, vrai effet nul, 300 panels.

| Inférence | Rejets à tort au seuil de 5 % |
|---|---|
| Cluster par région | 20,3 % |
| Cluster par année (CR1) | 5,0 % |
| **Wild cluster bootstrap restreint par année (WCR)** | **5,0 %** |

*Valeurs de `reports/tables/wcr_exemple_montecarlo.csv`, graine 123.*

**Sur les données réelles d'ATLAS** (rendements départementaux, `docs/resultats_phase4.md` et `docs/resultats_phase4bis.md`) :

- le cluster par département rejette à tort dans 15 à 58 % des cas ;
- Conley à 200 km, dans 19 à 43 % ;
- le cluster par année, dans 5 à 10 %, le cluster à deux dimensions dans 6 à 10 %, Driscoll-Kraay dans 8 à 12 % ;
- le WCR par année, dans 3,0 à 8,0 % (tests bilatéraux en phases 4 et 6, unilatéraux en phase 4 bis).

Valeurs à jour : tableau des tailles du mémoire (`memoire/tables/sizes.tex`).

Dans l'exemple simulé, le CR1 par année a lui aussi la bonne taille : avec 25 périodes, il ne montre pas d'avantage du WCR sur le CR1. Sur les données d'ATLAS (16 à 67 années), le CR1 par année reste sous 10 %, mais au-dessus du WCR. Avec peu de périodes (une dizaine ou moins), le CR1 par période devient peu fiable. Le WCR avec poids de Webb est alors recommandé (Cameron, Gelbach & Miller 2008 ; Webb 2023), sans garantie : sa taille se vérifie avec `placebo_size`.

## Fonctions

| Fonction | Rôle | Retour |
|---|---|---|
| `wcr_pvalue(data, y, x, z, fe, cluster, weights, B, seed)` | Test de β_x = 0 | `t`, `p` (bilatérale), `p_left` (H1 : β < 0), `p_right` (H1 : β > 0), `G`, `B` |
| `wcr_wald_pvalue(data, y, xs, z, fe, cluster, weights, B, seed)` | Test joint de plusieurs coefficients | `wald`, `p`, `G`, `B` |
| `placebo_size(data, x, unit, period, tests, R, alpha, seed)` | Taille empirique de **vos** tests sur **vos** données : l'exposition `x` est remplacée par le champ réel d'une autre période (dérangement) | Taux de rejet à tort par test, nombre de permutations distinctes |

**Arguments :**

- `z` : autres régresseurs (`character(0)` s'il n'y en a pas) ;
- `fe` : noms des effets fixes ;
- `weights` : nom d'une colonne de poids (une colonne de 1 pour des MCO non pondérés).

**Exemple minimal :**

```r
library(fixest)
source("R/wcr/wcr.R")
df$poids <- 1
b <- wcr_pvalue(df, y = "log_rendement", x = "chaleur", z = c("pluie"),
                fe = c("departement", "annee"), cluster = "annee", weights = "poids")
b$p          # p bilatérale ; b$p_left / b$p_right pour un test unilatéral

tests <- list(
  cluster_dep = function(s) coeftable(feols(log_rendement ~ x_placebo + pluie | departement + annee, s),
                                      vcov = ~departement)["x_placebo", "Pr(>|t|)"],
  wcr_annee  = function(s) wcr_pvalue(s, "log_rendement", "x_placebo", "pluie",
                                      c("departement", "annee"), "annee", "poids", B = 399)$p
)
placebo_size(df, x = "chaleur", unit = "departement", period = "annee", tests = tests, R = 300)
```

## Méthode (résumé)

1. **Frisch-Waugh-Lovell :** on retire les effets fixes (`fixest::demean`, pondéré, tolérance 1e-12 au lieu de 1e-6 par défaut), puis on projette sur `z`.
2. **Tirages :** sous H0, chaque résidu restreint est multiplié par un poids de Webb tiré par grappe. Les poids prennent six valeurs : ±√(3/2), ±1, ±√(1/2).
3. **Re-projection :** à chaque tirage, la variable simulée est re-projetée sur les effets fixes et sur `z`. Sans cette étape, la taille est faussée : dans un premier diagnostic du projet, avec un placebo iid peu informatif, elle était de 8,7 % sans re-projection et de 6,6 % avec (R = 500). Ces deux chiffres comparent les versions ; ce ne sont pas des tailles de référence.
4. **Comparaison :** on compare la statistique t observée (erreurs-types par grappe, sans facteur de petit échantillon puisqu'il se simplifie) à celle des tirages.

**Validation :**

- la statistique t observée et chaque t* re-projeté sont identiques, à moins de 1e-12 près, à ceux d'une réestimation complète pondérée par `feols` (effets fixes en indicatrices, CR0 par grappe) ; à la tolérance par défaut de `fixest::demean` (1e-6), l'écart serait d'environ 1e-7 ;
- la taille est vérifiée par simulation, dans `exemple.R` et sur chaque jeu de données du projet.

Ces contrôles sont automatisés dans `tests/test_r_inference.R` (`Rscript tests/test_r_inference.R`), avec ceux du jackknife par année (CV3) de `R/30` et des graines.

## Limites

- `placebo_size` garde y fixe et ne permute que les périodes de x : avec T périodes, les placebos sont peu nombreux et non indépendants, et la dépendance temporelle de y au sein d'une unité n'est pas testée. La régression placebo retire la vraie exposition, dont l'effet éventuel reste dans l'erreur. C'est un diagnostic indicatif.
- La p-valeur est la part des tirages au moins aussi extrêmes, sans la convention (1 + #)/(B + 1) : une p de 0 se lit p < 1/B.
- **Graine :** `wcr_pvalue`, `wcr_wald_pvalue` et `placebo_size` tirent sous une graine locale (`with_seed`) et restaurent ensuite l'état du générateur de l'appelant. Dans une boucle de simulation, les tirages de la boucle ne sont donc pas perturbés. En revanche, avec une même `seed` à chaque tour, les poids de Webb sont les mêmes d'un tour à l'autre : passer `seed = r` pour des tirages différents.
- Le test porte sur un coefficient à la fois, ou sur un test joint, avec des grappes à une seule dimension.
- Le temps de calcul est proportionnel à n × B.

## Références

- Cameron, A. C., Gelbach, J. B. & Miller, D. L. (2008). Bootstrap-based improvements for inference with clustered errors. *Review of Economics and Statistics* 90(3), 414-427.
- Webb, M. D. (2023). Reworking wild bootstrap-based inference for clustered errors. *Canadian Journal of Economics* 56(3), 839-858. DOI 10.1111/caje.12661.
