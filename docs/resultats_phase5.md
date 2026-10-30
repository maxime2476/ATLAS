# ATLAS — Module prédictif : résultats (phase 5)


*Objectif **prédictif** uniquement.*

**Reproduction :**

```bash
uv run python scripts/14_forecast_features.py
uv run python scripts/15_forecast_cv.py   # environ 10 min
```

Tableaux dans `reports/tables/phase5_*` ; tests de fuite dans `tests/test_forecast.py`.

## 1. Cadre

- **Échantillon :** 83 départements ; années test 2016 à 2025, avec origine glissante.
- **Entraînement :**
  - variante principale : 2010…*t*−1, soit 6 à 15 années ;
  - variante longue : 1990…*t*−1.
- **Deux dates de prévision :** le 1er juin (météo jusqu'au 31 mai) et le 1er juillet (jusqu'au 30 juin).
- **Références :**
  - **B0**, la moyenne du département ;
  - **B1**, B0 plus une tendance linéaire commune.
- **Modèles météo :** L1 (MCO sur les variables de M1), RIDGE, RF et GBM, chacun ajoutant à B1 une correction tirée des 36 variables météo.
- **Contrôle des fuites** (tests automatiques) :
  - modifier les rendements de l'année test ne change aucune prévision ;
  - modifier la météo de juin ne change aucune prévision au 1er juin ;
  - les moyennes, la tendance, la standardisation et les α de RIDGE sont estimés sur l'entraînement seulement.

## 2. Résultats observés

### 2.1 Comparaison à B1 (critère principal)

Écart de MSE (log) à B1, moyenne sur 10 années test, avec un intervalle à 95 % par bootstrap des années test, chaque année (83 départements) tirée comme un tout (`phase5_synthese.csv`) :

| Variante | Date | B0 | L1 | RIDGE | RF | GBM |
|---|---|---|---|---|---|---|
| Principale | 1er juin | **−0,0085** [−0,020 ; −0,001] | +0,0040 | −0,0021 | **−0,0049** [−0,010 ; −0,001] | −0,0028 |
| Principale | 1er juillet | **−0,0085** [−0,020 ; −0,001] | +0,0084 | +0,0055 | **−0,0051** [−0,010 ; −0,002] | −0,0034 |
| Longue | 1er juin | −0,0040 | −0,0004 | −0,0059 | −0,0058 | −0,0054 |
| Longue | 1er juillet | −0,0040 | +0,0006 | −0,0083 | −0,0061 | −0,0067 |

Une valeur négative signifie une prévision meilleure que B1. Les intervalles entre crochets excluent 0.


Avec l'intervalle de Student sur les 10 années, RF reste meilleur que B1 au 1er juillet ([−0,0100 ; −0,0003]) mais plus au 1er juin ([−0,0102 ; +0,0004] ; 8 années sur 10, test des signes p = 0,11). Avec une autre graine, il l'était aux deux dates ([−0,0099 ; −0,0003] et [−0,0100 ; −0,00001] ; 9 années sur 10 au 1er juin, p = 0,021) : cette lecture est sensible à la graine ; l'écart de B0 à B1 n'exclut plus 0 ([−0,021 ; +0,004]), mais B0 bat B1 les 10 années (test des signes, p = 0,002).

### 2.2 Comparaison à B0 (ajoutée après les premiers résultats ; B0 figurait dans le protocole)

Écart de MSE à B0 (`phase5_synthese_vs_B0.csv`) :

| Variante | Date | B1 | L1 | RIDGE | RF | GBM |
|---|---|---|---|---|---|---|
| Principale | 1er juin | +0,0085 * | +0,0125 * | +0,0064 | +0,0036 | +0,0057 |
| Principale | 1er juillet | +0,0085 * | +0,0169 * | +0,0140 | +0,0034 | +0,0051 |
| Longue | 1er juin | +0,0040 | +0,0036 | −0,0019 | −0,0018 | −0,0014 |
| Longue | 1er juillet | +0,0040 | +0,0046 | −0,0044 | −0,0022 | −0,0028 |

\* L'intervalle à 95 % exclut 0 (moins bon que B0). Aucun modèle n'est significativement **meilleur** que B0.


Avec l'intervalle de Student, seul L1 reste significativement moins bon que B0 (variante principale, deux dates) ; B1 ne l'est plus ([−0,0035 ; +0,0205]), mais il fait moins bien que B0 les 10 années (p = 0,002). La conclusion est inchangée : aucun modèle n'est significativement meilleur que B0.

*Skill* moyen par rapport à B0 : de −14 % à −72 % dans la variante principale ; de +7 % à +20 % pour RIDGE, RF et GBM dans la variante longue, sans que ce gain soit démontré.

### 2.3 Par année (variante principale, 1er juillet ; RMSE du log-rendement)

| Année | B0 | B1 | L1 | RIDGE | RF | GBM |
|---|---|---|---|---|---|---|
| 2016 | 0,372 | 0,439 | 0,400 | 0,340 | 0,429 | 0,424 |
| 2017 | 0,071 | 0,140 | 0,281 | 0,294 | 0,132 | 0,165 |
| 2018 | 0,069 | 0,073 | 0,199 | 0,071 | 0,062 | 0,078 |
| 2019 | 0,133 | 0,165 | 0,197 | 0,118 | 0,136 | 0,125 |
| 2020 | 0,134 | 0,137 | 0,122 | 0,121 | 0,115 | 0,118 |
| 2021 | 0,058 | 0,060 | 0,075 | 0,087 | 0,064 | 0,076 |
| 2022 | 0,099 | 0,099 | 0,104 | 0,118 | 0,093 | 0,090 |
| 2023 | 0,060 | 0,067 | 0,068 | 0,106 | 0,045 | 0,066 |
| 2024 | 0,176 | 0,176 | 0,216 | 0,322 | **0,096** | **0,111** |
| 2025 (provisoire) | 0,069 | 0,094 | 0,078 | 0,062 | 0,095 | 0,119 |


**Rendement national pondéré, 1er juillet** (q/ha ; observé / B0 / RF / GBM) :

- 2016 : 54,0 / 73,5 / 78,5 / 78,1 ;
- 2024 : 60,8 / 71,2 / **61,7** / **59,4** ;
- 2019 : 79,3 / 70,5 / 70,1 / 71,1.


**Détection des pertes** (rendement observé inférieur de plus de 10 % à B1 ; perte prédite si la prévision est inférieure de plus de 5 % à B1) : rappel de 40 à 55 % et précision de 35 à 59 % pour RIDGE, RF et GBM (`phase5_pertes.csv`). Comme ces seuils sont définis par rapport à B1, cette mesure hérite de sa faiblesse.

**RIDGE :** les α choisis par la validation interne varient de 0,1 à 1 000 selon les plis ; la borne haute de la grille (1 000) est choisie dans 27 plis sur 40 (10 sur 10 dans la variante longue au 1er juin ; `phase5_alpha_ridge.csv`). La ridge voudrait donc probablement une pénalité plus forte que ne le permet la grille prévue. Les variables thermiques sont fortement colinéaires (`gdd`, `tmin`, `tmax`), ce qui donne des prévisions instables : 81,4 q/ha au niveau national en 2024 et 56,0 en 2017. Ce n'est **pas** corrigé a posteriori, ce qui reviendrait à régler le modèle sur les années test.

**Importance par permutation** (1er juillet, variante principale ; contribution prédictive, **pas un effet**) :

- RIDGE : `gdd_0_32_automne`, `gdd_0_32_remplissage`, `tmax_automne` ;
- GBM : `tmin_remplissage`, `etp_printemps`, `prec_automne`, `swi_hiver`, `dd_32_remplissage` (importances très faibles).

## 3. Interprétation

1. **Selon le critère principal (comparaison à B1)**, RF satisfait formellement la condition de gain, avec un *skill* de 16 % et un intervalle excluant 0. **Mais B1 est une mauvaise référence** : prolonger une tendance linéaire dégrade la prévision, B0 battant B1 sur les 10 années test. Cela concorde avec le plafonnement des rendements français depuis le milieu des années 1990 (Gouache et al. 2015, citant Brisson et al. 2010). Conclure à un gain de la météo sur la seule base de B1 serait **trompeur**.
2. **Face à la référence la plus simple (B0), aucun gain de la météo n'est démontré.** Dans la variante principale (6 à 15 années d'entraînement), tous les modèles font moins bien que B0 en moyenne. Avec l'entraînement long (1990-), RIDGE, RF et GBM gagnent 7 à 20 %, mais ce n'est pas significatif sur 10 années test. C'est cohérent avec Morales & Villalobos (2023) et avec Gouache et al. (2015) : sur des années futures, l'erreur est environ deux fois celle de la validation croisée.
3. **Ce que la météo apporte, ponctuellement :** l'année humide 2024 est bien prévue au 1er juillet par les modèles non linéaires. 2016, l'événement composé décrit par Ben-Ari et al. (2018), n'est anticipée par aucun modèle au niveau national : la prévision la plus basse, RIDGE au 1er juillet, donne 71,1 q/ha contre 54,0 observés (`phase5_national.csv`). En RMSE départementale, RIDGE fait pourtant un peu mieux que B0 en 2016 (0,34 au 1er juillet et 0,36 au 1er juin, contre 0,37), contrairement à RF et GBM (0,42 à 0,43). C'est une observation sur deux années, pas une généralisation.
4. **Un résultat cohérent avec la phase 4 :** peu d'années informatives et des chocs nationaux font que ni l'inférence ni la prévision ne tirent un signal robuste de la météo départementale sur 2010-2025.

**Formulation retenue :** « Sur 2016-2025, des modèles fondés sur la météo connue au 1er juin ou au 1er juillet ne prévoient pas mieux le rendement départemental du blé que la moyenne historique du département. La forêt aléatoire et le gradient boosting améliorent nettement la prévision d'une année humide (2024), mais pas celle de 2016 ; la régression L1 et la ridge font moins bien que B0 en 2024. »

## 4. Points faibles et traitement

| Niveau | Constat | Pourquoi c'est important | Traitement / vérification |
|---|---|---|---|
| **Important** | La comparaison principale se fait par rapport à B1, une référence plus faible que B0 | Elle surestime le gain des modèles météo | Comparaison à B0 ajoutée et mise au premier plan (§ 2.2) ; écart au protocole |
| **Important** | Seulement 10 années test, et des années initiales entraînées sur 6 à 7 ans | Intervalles larges ; les résultats dépendent de quelques années (2016, 2024) | Bootstrap des années test (chaque année tirée comme un tout), résultats par année, variante longue |
| **Important** | Instabilité de RIDGE (α de 0,1 à 1 000, variables colinéaires) | Mauvaises performances qui ne reflètent pas le potentiel d'un modèle linéaire régularisé | Rapporté sans réglage a posteriori. Piste : fixer d'avance une grille d'α plus haute ou réduire les variables thermiques, à évaluer seulement sur de nouvelles années |
| Mineur | Le masque blé 2015-2017 est une information future pour les années test 2016-2017 | Fuite légère | Rapportée (§ 1 de la spécification) |
| Mineur | Séries SAA rétropolées (2022) et SIM révisée | Le test n'est pas un vrai test en temps réel | Rapporté |
| Mineur | Échantillon choisi avec le statut qualité publié en 2025 et les surfaces 2010-2012 | Information de sélection postérieure à certaines années test : pseudo-temps réel | Rapporté ; ne touche pas la cible |
| Mineur | Degrés-jours du 31 mai (prévision au 1er juin) et du 30 juin (1er juillet) calculés avec TINF_H du lendemain, qui couvre jusqu'à 18 h UTC le jour de la prévision | Quelques heures postérieures à la date de prévision | Effet négligeable, rapporté |
| Mineur | α de la ridge choisi en retirant une année d'entraînement à la fois, y compris des années postérieures à celle retirée ; résidus de B1 ajusté sur tout l'entraînement | Validation interne non chronologique | Aucune fuite vers l'année test ; rapporté |
| Mineur | La détection des pertes est définie par rapport à B1 | Mesure qui hérite d'un biais de tendance | Signalé ; à redéfinir par rapport à B0 dans une prochaine itération |
| — | Fuite de données | Aucune détectée | `tests/test_forecast.py` (5 tests, dont l'invariance à la cible de l'année test et à la météo postérieure) |

**Bilan :** les corrections de présentation (comparaison à B0, formulation) sont faites. Aucune correction n'a modifié les modèles ni les résultats principaux.
