# Spécification figée : test du résultat principal et de la prévision sur les récoltes futures

*Ce fichier ne doit plus être modifié ; tout écart futur sera signalé comme tel. Son empreinte SHA-256 est vérifiée par `tests/test_complements.py`. Pour un horodatage indépendant de l'auteur, il est à déposer tel quel sur un service tiers (OSF ou Zenodo).*

## Pourquoi

62 % de l'échantillon de H1 vient des années qui ont suggéré l'hypothèse. Les récoltes à venir sont les seules données qui n'ont pas pu orienter l'analyse : c'est le test le plus propre du résultat.

## 1. Maïs grain : H1 sur les nouvelles années

- **Données :** SAA, maïs grain irrigué (code 14) et non irrigué (code 15), chiffres **définitifs** de chaque récolte ≥ 2026 ; même population (38 départements) et même échantillon principal (les 17 départements de statut qualité 1 retenus aujourd'hui, liste fixe : 01, 03, 18, 26, 28, 36, 37, 38, 39, 41, 45, 58, 63, 67, 68, 69, 89).
- **Météo :** SIM2, degrés-jours > 32 °C (double sinus) et SWI de juillet-août, masque maïs RPG 2015-2017 inchangé.
- **Modèle :** A1 inchangé : log rendement irrigué − log rendement non irrigué ~ `dd_32_ja` + `swi_ja` | département + année, poids = surface de maïs grain 2010-2012.
- **(i) Chaque année :** A1 réestimé sur 2000 à la dernière récolte définitive, rapporté avec le WCR unilatéral ; aucune autre spécification n'est ajoutée à ce rapport annuel.
- **(ii) Test sur les seules nouvelles années**, dès que **5 récoltes définitives** (2026-2030) sont disponibles : A1 estimé sur ces 5 années ; WCR par année unilatéral à droite (5 grappes, poids de Webb, 9 999 tirages) ; taille mesurée par le même placebo (années permutées). **Règle :** H1 est confirmée sur les nouvelles années si β > 0, p < 0,05 et taille ≤ 10 % ; sinon elle n'est pas confirmée. Avec 5 grappes, la puissance sera faible : un résultat non confirmé ne réfute pas H1, et cela est dit d'avance. Si aucun été chaud (moyenne de `dd_32_ja` < 2 degrés-jours) ne survient sur ces 5 années, le test est déclaré non informatif et reporté à 10 récoltes.

## 2. Prévision du blé : modèles corrigeant la moyenne du département

- **Modèles :** RF_B0 et GBM_B0 tels que définis dans `scripts/28_complements_python.py` (fonction `b0_corrected`), variante principale (entraînement depuis 2010), date du **1er juillet**, mêmes 36 variables météo et mêmes réglages ; graine de la forêt : `SEED_FIGEE` (`src/atlas/forecast.py`) ; référence B0 (moyenne du département sur les années d'entraînement).
- **Chaque année t ≥ 2026 :** entraînement sur 2010 à t − 1, prévision de t avant la publication du rendement provisoire, puis comparaison des MSE (log rendement, pondérés par la surface) au rendement définitif. La prévision de 2026 (`reports/tables/phase7_p4_prevision_ble_2026_preenregistree.csv`) a été calculée dans la même exécution que la lecture des estimations de conjoncture 2026, qui contiennent les rendements provisoires du blé ; ces rendements n'entrent pas dans le calcul, mais elle n'est pas aveugle au sens strict. **2027 est la première année prospective :** prévision calculée début juillet (météo jusqu'au 30 juin), avant toute estimation Agreste du blé de l'année, et déposée sur un service horodaté.
- **Conclusion après 5 années :** écart de MSE moyen par rapport à B0 et intervalle de Student à 95 % (4 degrés de liberté). **Règle :** un modèle « bat B0 sur des années nouvelles » si cet intervalle exclut zéro du bon côté ; sinon non. Le bootstrap des années (trop étroit avec 5 années) et le test des signes (qui ne peut pas descendre sous p = 0,0625 en bilatéral avec 5 années) sont rapportés à titre indicatif. La puissance sur 5 années est faible ; le test sera répété à 10 années avec le même critère.

## 3. Ce qui n'est pas permis

Changer le masque, la fenêtre, le seuil, l'échantillon, les poids, les modèles ou leurs réglages pour ces tests. Toute analyse supplémentaire sur les nouvelles années sera présentée comme exploratoire.
