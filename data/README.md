# Données ATLAS

Seuls ces fichiers README sont versionnés. Prérequis : `uv sync`, `Rscript -e 'renv::restore()'`, R ≥ 4.5, l'outil système `7z` (archives RPG), un compte NASA Earthdata pour le NDVI (voir `README.md`, § 7).

Les fichiers sources sont révisés par leurs producteurs (SAA provisoire 2025, SIM récents, VigiEau) : une reproduction **bit à bit**, contrôlée par `docs/manifest_raw.csv`, n'est garantie qu'avec les fichiers dont le manifeste donne l'empreinte. Les données se retrouvent ainsi :

**Fichiers de `data/raw/` hors manifeste** (contrôlés par `tests/test_manifest.py`) : les notices `README.md`, le cache des métadonnées Crossref et DataCite de la vérification bibliographique (`bib_metadata/`, script 47, inutilisé par la chaîne), et trois journaux écrits par les scripts de commande : `drias/commandes.csv`, `drias/fenetres_tracc.csv` (fenêtres TRACC relevées sur le portail, lues par l'étape 38 et copiées dans `reports/tables/phase7_drias_fenetres_tracc.csv`) et `drias_eau/commandes.csv`.

```bash
# 1. Téléchargements (~18 Go ; RPG 2008 et NDVI plus bas, ~5,6 Go)
uv run python scripts/01_download_raw.py --sim-years 1958-2025 --rpg 2015-2017 --schauberger --prix --saa-ancienne --vigieau
# extraction des couches RPG : voir data/raw/ign_rpg/README.md (≈ 13 Go, à conserver jusqu'à `07_build_wheat_mask.py --culture MIE`, dernière étape qui la relit)
uv run python scripts/02_check_sim.py --all-years                 # contrôles SIM (1958 partiel : attendu)
uv run python scripts/03_build_saa_long.py                        # -> data/interim/
# 2. Météo, masques, fenêtres, panels
uv run python scripts/04_build_spatial_weights.py                 # poids maille -> département (~15 s)
uv run python scripts/05_build_weather_monthly.py                 # indicateurs météo mensuels 1958-2025 (~20 min)
uv run python scripts/07_build_wheat_mask.py                      # masque blé RPG + météo pondérée (~1,5 min)
uv run python scripts/07_build_wheat_mask.py --culture MIS        # masque maïs grain RPG (~1,5 min)
uv run python scripts/06_exposure_check.py --weights wheat        # fenêtres + règle de repli (référence)
uv run python scripts/06_exposure_check.py --weights area
uv run python scripts/06_exposure_check.py --weights wheat --first-year 1990
uv run python scripts/06_exposure_check.py --weights wheat --first-year 1959
uv run python scripts/08_check_schauberger.py                     # compatibilité Schauberger / SAA
uv run python scripts/09_build_panel.py                           # panels blé (2010, 1990 et 1959-2025)
uv run python scripts/10_descriptives.py                          # tableaux et figures descriptifs
uv run python scripts/11_extra_windows.py                         # fenêtre mai-juillet (R10)
uv run python scripts/12_build_semimonthly.py                     # demi-mois et classes de température (R11, R12, R14, ~5 min)
uv run python scripts/13_cell_altitude.py                         # altitude des mailles via le service IGN (R13, ~3 min)
uv run python scripts/23_vigieau_indicators.py                    # restrictions d'eau juillet-août 2012-2025
uv run python scripts/22_build_panel_mais.py                      # panel maïs irrigué / non irrigué 2000-2025
# 3. Économétrie (R, renv ; depuis la racine)
Rscript R/10_fe_models.R && Rscript R/11_robustness.R && Rscript R/12_diagnostics.R   # blé 2010-2025 (phase 4)
# 4. Prévision
uv run python scripts/14_forecast_features.py                     # variables de prévision (1er juin, 1er juillet)
uv run python scripts/15_forecast_cv.py                           # évaluation chronologique (~10 min)
# 5. Phase 6 (exploratoire)
uv run python scripts/16_phase6_build.py                          # prix, pertes valorisées, panel maïs 2010-2025
Rscript R/13_maize_gap.R                                          # maïs irrigué / non irrigué (exploratoire)
# NDVI : APPEEARS_TOKEN dans .env (voir .env.example), puis :
uv run python scripts/17_ndvi_appeears.py soumettre --annees 2010-2025   # puis « statut », puis « telecharger --tache <id> »
#   (exécution réelle : 2 commandes, test 2022 puis 2010-2021,2023-2025 ; 18_ndvi_aggregate lit TOUS les
#    dossiers de data/raw/nasa_appeears/ : ne pas télécharger deux fois la même année, sinon il s'arrête)
uv run python scripts/18_ndvi_aggregate.py                        # NDVI par département (~15 min)
uv run python scripts/19_forecast_ndvi.py                         # apport du NDVI à la prévision (~30 min)
# 6. Phase 4 bis
Rscript R/14_q1_maize.R                                           # Q1 maïs 2000-2025 (~1 min)
Rscript R/21_q1_verifications.R                                           # intervalle de β, départements, humidité du sol, décennies (~15 min ; avant 24)
uv run python scripts/24_valorisation_mais.py                     # valorisation descriptive de Q1
Rscript R/15_q2_wheat.R                                           # Q2 blé 1959-2025 (~3 min)
Rscript R/16_q1_exploratoire.R                                    # diagnostics exploratoires de Q1
uv run python scripts/01_download_raw.py --rpg1 2008              # phase 0 ter : îlots RPG 2008, 4 régions (~0,6 Go)
uv run python scripts/25_build_maize_mask_2008.py                 # masque maïs 2008 + météo (Q1-R9)
Rscript R/17_q1_mask2008.R                                        # robustesse Q1-R9
Rscript R/18_residual_autocorr.R                                  # diagnostic : autocorrélation des résidus
Rscript R/19_q1_power_size.R                                      # puissance de H1, taille de la réplication
uv run python scripts/01_download_raw.py --eobs                    # E-OBS Tmin/Tmax 0,1°, 1995-2025 (~4 Go)
uv run python scripts/27_eobs_heat.py                             # degrés-jours > 32 °C de juillet-août avec E-OBS
Rscript R/20_q1_eobs.R                                            # vérification E-OBS (source de température)
uv run python scripts/28_complements_python.py preparer           # covariables, fourrage, DML (50 découpages : ~12 min)
Rscript R/22_q1_complements.R                                     # analyses complémentaires (~5 min)
uv run python scripts/28_complements_python.py prevision          # prévision : modèles corrigeant B0 (~5 min)
Rscript R/wcr/exemple.R                                           # exemple simulé du module wcr (Monte-Carlo)
# 7. Figures, mémoire et tests
uv run python scripts/20_figures_rapport.py                       # figures du README (PNG) et du mémoire (PDF)
uv run python scripts/07_build_wheat_mask.py --culture MIE         # masque maïs ensilage (réplication fourrage ; RPG extrait)
uv run python scripts/33_mais_fourrage.py                         # panel maïs fourrage irrigué / non irrigué 2010-2025
uv run python scripts/30_lst_appeears.py soumettre                # LST MODIS juillet-août 2000-2025 (APPEEARS_TOKEN), puis « statut »
uv run python scripts/30_lst_appeears.py telecharger --tache <id> #   fichiers dans data/raw/nasa_appeears_lst/<id>/
uv run python scripts/31_lst_aggregate.py                         # LST par département sur le masque maïs
Rscript R/23_q1_lst.R                                             # écart irrigué / pluvial et LST de juillet-août
Rscript R/24_q1_fourrage_calendrier_iv.R                                     # fourrage, calendrier, IV (~5 min)
uv run python scripts/34_vpd.py                                   # déficit de pression de vapeur de juillet-août (~3 min)
Rscript R/25_q1_forme_vpd.R                                     # forme, sol sec, VPD
Rscript R/26_q1_annees_multivers.R                                     # VPD fourrage, années, corrélation sérielle, multivers (~2 min)
uv run python scripts/01_download_raw.py --ra2020 --bnpe          # RA2020, volumes Hub'Eau (34 extractions)
uv run python scripts/36_volumes_irrigation.py                    # volumes BNPE, parts irriguées du RA, prix du maïs
Rscript R/27_q1_sol_eau.R                                         # volumes, valeur du m³
Rscript R/28_q1_cv3_saa.R                                          # taille du CV3, signatures d'imputation SAA
uv run python scripts/01_download_raw.py --sim-years 2026 --conjoncture-2026   # météo 2026, estimations Agreste au 1er octobre 2026
uv run python scripts/40_recolte_2026.py                          # panel 2026 (provisoire), prévision figée du blé 2026
# reports/tables/phase7_p4_prevision_ble_2026_preenregistree.csv n'est produit par aucun script : c'est l'archive de la
# prévision enregistrée la première (graine d'origine), à conserver telle quelle pour le test figé.
Rscript R/29_q1_chaleur_statut_2026.R                                     # chaleur moyenne, statut, récolte 2026
uv run --with playwright==1.63.0 python scripts/41_drias_eau.py commander    # 68 commandes DRIAS-Eau (compte personnel)
uv run --with playwright==1.63.0 python scripts/41_drias_eau.py telecharger
Rscript R/30_q1_inference.R                                       # levier, bootstrap du CV3, sans rapports reconduits (~1 min)
uv run python scripts/48_partage_saa.py                           # rendements dérivés de la production dans le partage SAA
Rscript R/32_q1_partage.R                                         # A1 selon le mode de calcul, rendement total, fourrage (~10 s)
Rscript R/33_tailles_temporelles.R                                # taille du cluster par année, à deux dimensions et de Driscoll-Kraay (~1 min)
# projections DRIAS (compte personnel ; DRIAS_LOGIN et DRIAS_PASSWORD dans .env ; Chromium : playwright install chromium)
uv run --with playwright==1.63.0 python scripts/37_drias_telechargement.py commander     # 34 commandes (~1 h 15)
uv run --with playwright==1.63.0 python scripts/37_drias_telechargement.py fenetres      # fenêtres TRACC par modèle
uv run --with playwright==1.63.0 python scripts/37_drias_telechargement.py telecharger   # 34 archives, 21 Go (~1 h 15)
uv run python scripts/38_drias_indicateurs.py                     # degrés-jours et VPD par horizon (~15 min)
uv run python scripts/42_drias_eau_swi.py                         # SWI projeté et projection de l'écart avec le sol (lit phase7_drias_horizons.csv de l'étape 38)
uv run python scripts/39_figures_complements.py                  # figures 1, 2, 4 et 7 du mémoire (carte, résidus, courbe de spécification, projections)
uv run python scripts/32_diagrammes_readme.py                   # diagrammes du README (chaîne de données, règle de décision, frise ; SVG)
uv run python scripts/26_tables_memoire.py                        # chiffres et tableaux du mémoire (memoire/tables/)
uv run python scripts/46_verifier_chiffres_memoire.py              # contrôle des chiffres du mémoire (macros et chiffres en dur)
(cd memoire && latexmk -pdf main.tex)                             # compilation du mémoire
uv run pytest
```

| Dossier | Contenu | Règle |
|---|---|---|
| `raw/` | Fichiers tels que téléchargés | Jamais modifiés ; empreintes dans `docs/manifest_raw.csv` |
| `interim/` | Transformations intermédiaires (ex. SAA au format long) | Toujours régénérables depuis `raw/` |
| `processed/` | Poids spatiaux, météo département × mois et × récolte ; panel (phase 3) | Régénérables |

Provenance, licences, révisions : `docs/sources.md`.
