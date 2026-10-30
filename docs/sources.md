# ATLAS — Sources de données : provenance, licences, empreintes

*Les licences des producteurs ont été vérifiées en ligne ; les mentions d'attribution utilisées sont dans `NOTICE.md`.*

- **Manifeste machine :** `docs/manifest_raw.csv`, mis à jour automatiquement par `scripts/01_download_raw.py`.
- **Données brutes :** dans `data/raw/<source>/`. Elles ne sont jamais modifiées ni versionnées ; les commandes de téléchargement complètes sont dans `data/README.md` (SIM 1958-2025, SAA, RPG, VigiEau, prix, NDVI).
- **Comparaison :** `tests/test_manifest.py` compare la taille et le SHA-256 de **chaque** fichier brut présent au manifeste. Par ailleurs, `01_download_raw.py` refuse de réécrire le manifeste si un fichier local a changé sans nouveau téléchargement.

---

## 1. Statistique agricole annuelle (SAA) : séries longues départementales

| Champ | Valeur |
|---|---|
| Producteur | SSP, ministère chargé de l'agriculture (Agreste), avec les services régionaux (SRISE) |
| Page officielle | https://agreste.agriculture.gouv.fr/agreste-web/disaron/SAA-SeriesLongues/detail/ |
| Fichier | `SAA-SeriesLongues-2010-2025_DonneesProvisoires-DepartementalesRegionales.zip` (2 xlsx : départemental et régional) |
| Méthodologie | https://agreste.agriculture.gouv.fr/agreste-web/methodon/S-SAA/methodon/ (PDF « Méthodologie » de 37 pages et note « Statut qualité », lus) |
| Licence | Réutilisation libre, y compris commerciale, sous réserve de citer la source (mentions légales d'agreste.agriculture.gouv.fr, vérifiées) ; les jeux Agreste publiés sur data.gouv.fr sont sous Licence Ouverte 2.0. Attribution : « Source : Agreste, Statistique agricole annuelle » |
| Accès | Téléchargement direct HTTPS. **Le serveur n'envoie pas son certificat intermédiaire** : voir `certs/README.md`. On ajoute l'intermédiaire au magasin système, en retirant le drapeau Python `VERIFY_X509_PARTIAL_CHAIN` : la chaîne doit remonter à la racine HARICA, et le nom d'hôte est vérifié. |
| Couverture | Récoltes 2010-2025 ; 95 départements métropolitains (Paris absent) + 5 DROM ; annuelle |
| Unités | Surface en ha ; production en quintaux (q) ; rendement en q/ha (1 q = 100 kg) |
| Utilisé | Feuille `COP` (céréales, oléagineux, protéagineux) → `data/interim/saa_cop_departements_long.parquet` |

### Données provisoires, révisions, ruptures

- **2025 est provisoire** : données arrêtées au 30/03/2026. La version définitive est publiée en novembre. Selon la méthodologie, la version définitive de l'année précédente peut « très marginalement » être corrigée. Le fichier téléchargé correspond à la version provisoire 2025 ; **il faudra le retélécharger après novembre 2026** et comparer les empreintes et les valeurs.
- **Rétropolation 2010-2019** : les séries ont été mises en cohérence avec le recensement agricole 2020. D'après la méthodologie, le recalage a été fait en 2022, puis complété en 2025 pour les prairies et la SAU. Les séries ne sont donc **pas** celles publiées à l'époque : c'est une information postérieure, importante pour la validation prédictive.
- **Rupture avant 2010** : les données 2000-2010 (tableaux interactifs) n'ont pas été rétropolées ; elles ne sont pas comparables telles quelles.
- **Nature des chiffres** : opération de **synthèse multi-sources** (enquêtes, PAC, informations locales). Les rendements sont « plus difficiles à établir » que les surfaces. Pour certaines productions, les régions peu productrices sont estimées en appliquant l'évolution nationale.
- **Statut qualité** (1 = raisonnablement fiable ; 2 = fragile, à utiliser en totaux ; 3 = extrapolé) : il ne reflète que la **dernière année publiée**.
- **Rattachement géographique** : les terres sont rattachées au département du **siège de l'exploitation**, pas à celui de la parcelle.
- **Non-récolte** : une surface non récoltée (aléa sans resemis) est comptée avec un rendement nul.
- **Précision constatée** :
  - environ 66 % des rendements de la feuille COP sont des entiers (q/ha) ; pour le blé tendre d'hiver de la population, c'est 86,6 % ;
  - production ≈ surface × rendement à 0,5 % près pour 99,98 % des lignes.

  La production est donc essentiellement dérivée du rendement.
- **Valeurs particulières (feuille COP)** : 3 680 lignes ont le statut « NC » (presque toujours avec des valeurs nulles) et 1 600 lignes (culture 28, « PAILLES ») n'ont pas de surface. À traiter explicitement lors de la sélection du panel.

## 2. SIM2 quotidienne (SAFRAN-ISBA), Météo-France

| Champ | Valeur |
|---|---|
| Producteur | Météo-France |
| Page officielle | https://www.data.gouv.fr/datasets/donnees-changement-climatique-sim-quotidienne |
| Documentation | `sim-quotidienne-parametres-20260331.pdf` (paramètres, unités, fenêtres horaires) ; `climatologie-presentation-modele-sim-20260602.pdf` (modèle). Toutes deux téléchargées. |
| Licence | **Licence Ouverte / Open Licence 2.0** (`lov2` sur data.gouv). Mention : « Source : Météo-France » |
| Accès | HTTPS direct, un fichier csv.gz par an : `https://meteofrance.s3.sbg.io.cloud.ovh.net/data/REF_CC/SIM/QUOT_SIM2_<année>.csv.gz` |
| Fichiers | 1958 à 2025 (68 fichiers annuels, ≈ 9,3 Go compressés) + grille `coordonnees_grille_safran_lambert-2-etendu.csv` et deux notices PDF. Phase 1 : 1989-2025 ; 1958-1988 ajoutés en phase 0 bis pour la série longue du blé. Le fichier 1958 commence le 1er août 1958 (153 jours), début de la réanalyse |
| Couverture | France métropolitaine, 9 892 mailles de 8 km (0,072°), quotidien. Contrôlée en phase 1 pour **chacune des années 1989-2025** : 365 ou 366 jours × 9 892 mailles, sans doublon ni valeur manquante sur `T`, `TINF_H`, `TSUP_H`, `SWI` |
| Coordonnées | `LAMBX`, `LAMBY` en **hectomètres**, Lambert II étendu (centre de maille) ; la grille fournit aussi la latitude et la longitude en degrés décimaux (virgule décimale) |
| Séparateur, format | `;`, en-tête en première ligne, `DATE` au format AAAAMMJJ |

### Révisions et points d'attention

- **Mise à jour bimensuelle des quatre dernières années, quotidienne sur 60 jours glissants.** Les fichiers 2022-2025 peuvent encore changer. Le script ne retélécharge pas un fichier présent : pour intégrer une révision, il faut renommer l'ancien fichier, relancer le téléchargement, puis comparer. `tests/test_manifest.py` détecte toute modification locale non tracée.
- SIM est une **réanalyse** : interpolation optimale par massif et tranche d'altitude, à partir d'un réseau de stations variable dans le temps. Ce n'est pas une observation.
- **Fenêtres horaires différentes selon les variables** (notice) : `T` sur ]00-00 UTC] ; `TINF_H` sur ]18-18 UTC] ; `TSUP_H`, précipitations, `SWI` et `EVAP` sur ]06-06 UTC] ; `WG_RACINE` à 06 UTC.
  - La notice ne dit pas à quel jour civil se rattache une fenêtre à cheval sur deux dates.
  - Cette convention a été **déterminée empiriquement** (annexe F du mémoire).
- **Unité de `SWI`** : la notice indique « % », mais les valeurs observées en 2009 vont de −0,035 à 2,075 (maximum 1,686 en 1958), avec un ordre de grandeur de 1. C'est un indice sans dimension. Écart à signaler et à garder à l'esprit pour tout seuil.

## 3. ADMIN EXPRESS COG CARTO (IGN) : contours départementaux

| Champ | Valeur |
|---|---|
| Producteur | IGN |
| Page officielle | https://www.data.gouv.fr/datasets/admin-express-admin-express-cog-admin-express-cog-carto-admin-express-cog-carto-pe-admin-express-cog-carto-plus-pe ; flux : https://data.geopf.fr/telechargement/resource/ADMIN-EXPRESS-COG-CARTO |
| Édition | `ADMIN-EXPRESS-COG-CARTO_4-0__GEOPARQUET_WGS84G_FRA_2026-01-01`, couche `departement.parquet` |
| Licence | **Licence Ouverte 2.0** (`lov2`). Attribution : « IGN — ADMIN EXPRESS » |
| Format | GeoParquet 1.1, géométrie WKB `MultiPolygon` en WGS84 (CRS par défaut OGC:CRS84) ; 101 départements, DROM compris |
| Clé | `code_insee` (« 01 », « 2A », « 971 »), compatible avec les codes SAA normalisés. Test : `tests/test_saa.py::test_codes_match_admin_express` |
| Pourquoi ce format | Le GeoPackage n'existe qu'en archive `.7z`, et l'outil 7z n'était pas installé lors de ce choix (phase 1 ; il l'a été ensuite pour le RPG). Le GeoParquet se lit avec `pyarrow`, déjà présent. |
| Limite | Version cartographique **généralisée** (CARTO) : précision suffisante pour des mailles de 8 km, à vérifier en phase 2 pour les mailles côtières et frontalières. Les contours 2026 sont appliqués à toute la période : aucun code départemental métropolitain n'a changé sur 2010-2025 (la Collectivité européenne d'Alsace, créée en 2021, conserve les codes 67 et 68), ni sur la série 1959-2025. |

## 4. RPG version 2.0 (IGN/ASP) : masques blé et maïs, millésimes 2015-2017

| Champ | Valeur |
|---|---|
| Producteur | IGN, à partir des déclarations PAC gérées par l'ASP |
| Page officielle | https://www.data.gouv.fr/datasets/rpg ; flux : https://data.geopf.fr/telechargement/resource/RPG |
| Licence | **Licence Ouverte 2.0** (`lov2`) |
| Fichiers | `RPG_2-0__SHP_LAMB93_FR-<année>_<année>-01-01.7z`, 2015, 2016 et 2017 (≈ 2,8 Go chacun) ; seule la couche `PARCELLES_GRAPHIQUES` est extraite, vers `data/interim/rpg/` |
| Contenu utilisé | Parcelles `CODE_CULTU = 'BTH'` (blé tendre d'hiver ; environ 1 million de parcelles et 4,9 à 5,1 Mha par millésime) et `CODE_CULTU = 'MIS'` (maïs grain, hors ensilage ; 1,53 à 1,79 Mha par millésime, phase 0 bis), `SURF_PARC` (ha), Lambert 93 (EPSG:2154) |
| Contrôle | Maïs : corrélation départementale de 0,993 entre la surface `MIS` et la surface SAA de maïs grain (phase 0 bis). Blé : surface BTH du RPG / surface SAA (code 01) : 0,996, 0,996, 0,994 (2015-2017) ; corrélation départementale 0,9999 ; ratio médian 0,992 ; écarts les plus forts dans de petits départements du Sud (Vaucluse 0,74) |
| Limites | Déclarants PAC seulement ; localisation à la parcelle, alors que la SAA rattache les terres au siège de l'exploitation ; masque fixe (2015-2017) appliqué à toute la période |

## 4 bis. RPG version 1.0 (IGN/ASP), 2008 : masque maïs d'époque (robustesse Q1-R9)

| Champ | Valeur |
|---|---|
| Producteur | IGN, à partir des déclarations PAC gérées par l'ASP |
| Page officielle | https://www.data.gouv.fr/datasets/rpg (la fiche liste les ressources RPG 1.0 2008 par région) |
| Licence | **Licence Ouverte 2.0** (`lov2`, fiche data.gouv consultée) |
| Fichiers | `RPG_1-0__SHP_LAMB93_R{24,27,44,84}_2008-01-01.7z`, quatre régions du découpage 2016 (Centre-Val de Loire, Bourgogne-Franche-Comté, Grand Est, Auvergne-Rhône-Alpes), 81 à 284 Mo chacune (≈ 0,63 Go) ; extraction par `scripts/25_build_maize_mask_2008.py` (outil système `7z`) |
| Contenu utilisé | Îlots dont le groupe de cultures majoritaire (`CODE_CULTU`) est 02, « maïs grain et ensilage » ; l'îlot entier est attribué à ce groupe. Le RPG 1.0 ne localise pas la parcelle, seulement l'îlot |
| Limites | Mélange maïs grain et ensilage (surfaces supérieures de 20 à 50 % à la SAA maïs grain 2008) ; îlot et non parcelle ; quatre régions seulement, celles de l'échantillon principal. Comparaison au masque 2015-2017 : corrélation des expositions de 0,997 (`docs/resultats_phase4bis.md`). |

## 5. Schauberger et al. (2022) : rendements départementaux 1900-2018 (robustesse sur période longue)

| Champ | Valeur |
|---|---|
| Producteurs | Schauberger, Kato, Kato, Watanabe & Ciais ; GFZ Data Services |
| Page officielle | https://doi.org/10.5880/PIK.2021.001 ; fichiers : https://datapub.gfz.de/download/10.5880.PIK.2021.001najvndf/ ; article : DOI 10.1038/s41597-022-01145-4 |
| Licence | **CC BY 4.0** : citer le jeu de données (Schauberger et al. 2021, GFZ, DOI 10.5880/PIK.2021.001) et l'article ; modifications à signaler (voir `NOTICE.md`) |
| Version utilisée | **RAW** (pas FILTERED, qui masque surtout des années de pertes réelles) ; blé tendre d'hiver ; t/ha converties en q/ha |
| Provenance | 1989-2018 : ancienne base numérique Agreste, **non recalée** sur le RA 2020 |
| Compatibilité avec la SAA (2010-2018) | 761 paires sur 765 ; écart relatif médian 0,0 % ; 97,5 % des paires identiques à ±0,5 q/ha ; corrélation des résidus (effets fixes) 0,994 (`scripts/08_check_schauberger.py`) |

## 6. Altitude : service de calcul altimétrique de la Géoplateforme IGN (robustesse R13)

| Champ | Valeur |
|---|---|
| Producteur | IGN, RGE ALTI® (ressource `ign_rge_alti_wld`) |
| Service | `https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json` (POST) ; documentation : https://cartes.gouv.fr/aide/fr/guides-utilisateur/utiliser-les-services-de-la-geoplateforme/calcul-altimetrique/ |
| Licence | Licence Etalab 2.0 (contenus de la Géoplateforme, d'après la page de documentation) |
| Limites d'usage | 5 000 points par requête ; 5 requêtes par seconde et par adresse IP |
| Requête | 143 744 points (16 par maille SIM française, sous-grille 4 × 4 de pas 2 km) ; réponse brute conservée dans `data/raw/ign_altimetrie/` et inscrite au manifeste |
| Contrôles | Paris 34,8 m, mont Blanc 4 757 m (requête ponctuelle de contrôle, non conservée ; le fichier brut, à 2 km de pas, culmine à 4 141,85 m). Hors couverture, le service renvoie −99 999, et des valeurs interpolées aberrantes sur les côtes (jusqu'à −6 080 361) : seules les altitudes de −50 à 4 810 m sont gardées (3 099 points exclus). 2 mailles côtières de blé (16 ha) sans point valide sont fixées à 0 m |
| Pourquoi ce choix | La BD ALTI (téléchargement) n'existe qu'au pas de 25 m et par département (≈ 15 Go). La grille SIM ne contient pas d'altitude |

## 7. Prix du blé tendre et du maïs (valorisation descriptive, phases 6 et 4 bis)

| Source | Détail | Licence | Contrôle |
|---|---|---|---|
| INSEE, IPPAP annuel « Blé tendre » | idbank 010776425, base 2020, 1949-2025 ; https://bdm.insee.fr/series/sdmx/data/SERIES_BDM/010776425 | Licence Ouverte 2.0, mention « Source : Insee » (mentions légales de l'INSEE, vérifiées) | — |
| Eurostat `apri_ap_crpouta` | Prix absolu (€/100 kg), France, blé tendre ; **valeurs disponibles seulement jusqu'en 2016** | Réutilisation autorisée sous réserve de citer la source ; contenus de l'UE sous CC BY 4.0 (avis de droit d'auteur d'Eurostat, vérifié) | Rapport à l'IPPAP de 0,2504 ± 0,0004 sur 2012-2016 ; 0,19 en 2010-2011 (rupture probable) |
| INSEE, IPPAP annuel « Maïs » et Eurostat `apri_ap_crpouta`, maïs (`prod_veg=01500000`) | idbank 010776430, base 2020, 1970-2025 ; Eurostat 2000-2016 | Mêmes licences que pour le blé | Rapport Eurostat/IPPAP de 0,219-0,220 sur 2012-2016 (raccord retenu), mais de 0,117 à 0,176 sur 2000-2011 : le prix raccordé de 2003 (16,4 €/q) dépasse le prix Eurostat observé (13,2 €/q) ; la valorisation de 2003 utilise les deux |

## 8. NDVI MODIS MOD13Q1 v6.1 (NASA LP DAAC, via AppEEARS)

| Champ | Valeur |
|---|---|
| Producteur | NASA LP DAAC ; produit MOD13Q1 v6.1 (Terra MODIS, 250 m, composites de 16 jours) |
| Accès | API AppEEARS, https://appeears.earthdatacloud.nasa.gov/api/ (commande par zone ; GeoTIFF, EPSG:4326). Compte NASA Earthdata requis ; jeton AppEEARS (48 h) obtenu par l'auteur, rangé dans `.env` |
| Commandes | `ebe86b6f-8e1f-497a-a811-f92e5f4e2a22` (2022) ; `5a8a9750-f9e6-4b03-9fd3-619d84331cbd` (2010-2021, 2023-2025) ; contour simplifié de la France métropolitaine ; composites d'avril à juin (le premier commence fin mars) |
| Couches | `_250m_16_days_NDVI` (int16, facteur d'échelle 0,0001, -3000 = pas de donnée) ; `_250m_16_days_pixel_reliability` (0 bon, 1 marginal, 2 neige, 3 nuage) ; `VI_Quality` ajoutée d'office par AppEEARS, non utilisée |
| Licence | Données de mission NASA sous Creative Commons Zero (CC0), citation demandée (consignes d'usage de NASA Earthdata, vérifiées). Citation : Didan, K. (2021), MOD13Q1 MODIS/Terra Vegetation Indices 16-Day L3 Global 250m SIN Grid V061, DOI 10.5067/MODIS/MOD13Q1.061 |
| Limites | Terra/MODIS en fin de mission (continuité après 2025 incertaine) ; NDVI de maille, et non de parcelle |

## 8 bis. E-OBS v33.0e (ECA&D, Copernicus) : vérification de la mesure de chaleur de Q1

| Champ | Valeur |
|---|---|
| Producteur | KNMI, projet ECA&D, pour le Copernicus Climate Change Service ; grille construite à partir des stations des services météorologiques nationaux |
| Page officielle | https://surfobs.climate.copernicus.eu/dataaccess/access_eobs.php ; fichiers : `https://knmi-ecad-assets-prd.s3.amazonaws.com/ensembles/data/Grid_0.1deg_reg_ensemble/` (accès direct, sans compte) |
| Licence | Politique de données ECA&D/E-OBS (PDF `ECAD_datapolicy.pdf`, lu) : usage **réservé à la recherche et à l'enseignement non commerciaux** ; résultats à soumettre sans délai à une publication ouverte ; citation obligatoire de Cornes et al. (2018), DOI 10.1029/2017JD028200, et remerciement « We acknowledge the E-OBS dataset and the data providers in the ECA&D project (https://www.ecad.eu) ». Les fichiers bruts ne sont pas redistribués |
| Fichiers | `tn` et `tx` (Tmin et Tmax journalières), moyenne d'ensemble, grille régulière de 0,1°, blocs 1995-2010 et 2011-2025 (≈ 4 Go) ; version publiée en mai 2026 |
| Format | netCDF-4 (lu avec `h5py`) ; entiers int16 en centièmes de °C (`scale_factor` 0,01), valeur manquante −9 999 ; temps en jours depuis le 1950-01-01 |
| Correspondance avec SIM | Point E-OBS le plus proche du centre de chaque maille SIM (au plus 0,07°). 106 mailles littorales du masque maïs tombent sur un point en mer (manquant toutes les années) ; aucune dans les 17 départements de l'échantillon principal |
| Limites | Interpolation de stations, de niveau différent de SAFRAN : sur le masque maïs, E-OBS donne plus de degrés-jours > 32 °C en juillet-août que SIM (corrélation 0,95) ; les fenêtres horaires de Tmin et Tmax suivent les conventions des fournisseurs nationaux et n'ont pas été vérifiées pour la France (SIM : `TINF_H` sur ]18-18 UTC], `TSUP_H` sur ]06-06 UTC]) ; une partie des stations françaises est commune à SAFRAN : ce n'est pas une mesure entièrement indépendante |

## 8 ter. SAA, feuille FOU (même fichier que le § 1) : variables des analyses complémentaires

- **FOU :** maïs fourrage et ensilage (plante entière) irrigué (ligne 04) et non irrigué (ligne 05), surfaces et rendements 2010-2025 par département ; utilisé pour la part du maïs non irrigué récolté en fourrage (ensilage) et pour la réplication sur le maïs fourrage (avec le masque RPG `MIE`).
- **Méthode du partage irrigué / non irrigué :** les publications publiques consultées (SAA 2016-2024, « Chiffres et données » ; « Infos rapides » grandes cultures) décrivent la SAA comme une synthèse établie par les services régionaux (SRISE), combinant des enquêtes (Structure, Terres, vergers) et des données administratives (ASP, aides PAC). Les rendements en cours de campagne sont estimés par ces services. **Aucune ne définit « irrigué »** (surface irriguée l'année, ou équipée pour l'irrigation). Les PDF méthodologiques renvoient désormais une page de connexion. Question à poser au SSP ; l'enquête Pratiques culturales grandes cultures (2017, 2021, 2025), qui relève l'irrigation et le rendement à la parcelle, pourrait valider le partage au niveau régional.

## 8 quater. Température de surface MODIS MOD11A2 v6.1 (NASA LP DAAC, via AppEEARS)

| Champ | Valeur |
|---|---|
| Producteur | NASA LP DAAC ; produit MOD11A2 v6.1 (Terra MODIS, LST de jour et de nuit, 1 km, composites de 8 jours) ; Wan, Hook et Hulley (2021), DOI 10.5067/MODIS/MOD11A2.061 |
| Accès | API AppEEARS, comme le NDVI (§ 8) ; commande `0b1bbe88-8fbf-47c5-b36c-a27fb91934f9`, couches `LST_Day_1km` et `QC_Day`, composites de juillet-août 2000-2025 (et quelques composites voisins, non utilisés) ; 474 fichiers dans `data/raw/nasa_appeears_lst/` (≈ 0,46 Go), inscrits au manifeste |
| Licence | Données de mission NASA sous CC0, citation demandée (comme le § 8) |
| Format | GeoTIFF EPSG:4326 ; LST en kelvins × 0,02, valeur manquante 0 ; bits de qualité dans `QC_Day` |
| Limites | Passage de Terra vers 10 h 30 (pas le maximum journalier) ; pixel de 1 km mêlant parcelles irriguées et non irriguées ; ciel clair seulement (composites de 8 jours) ; un composite de 2001 (jour 177) n'a pas de fichier LST, hors fenêtre |

## 8 quinquies. Sources pour l'eau d'irrigation et les projections climatiques

*Le RA2020 et les volumes BNPE ont été téléchargés (`scripts/01_download_raw.py --ra2020 --bnpe`) et utilisés pour les volumes et la valeur du m³. Les volumes Hub'Eau proviennent d'une API vivante : une extraction ultérieure peut différer ; les fichiers du manifeste font foi (manifeste). DRIAS a été téléchargé (34 commandes, 21 Go ; `scripts/37_drias_telechargement.py`) et utilisé pour D1.*

| Source | Accès testé | Licence | Couverture et format | Intérêt pour ATLAS | Statut |
|---|---|---|---|---|---|
| DRIAS, EXPLORE2-Climat 2022 corrigé ADAMONT (17 modèles), TRACC-2023 | Compte gratuit de l'auteur ; formulaire « données quotidiennes corrigées par ADAMONT [NetCDF] » rempli par un script Playwright (identifiants lus dans `.env`, jamais affichés) ; commande test : grille identique à SIM2 (coordonnées égales à 10⁻⁴ ° près) | **Licence Etalab** (conditions d'utilisation du portail, lues), mention « Drias, données Météo-France, CERFACS, IPSL » ; compte personnel incessible | Quotidien, grille SAFRAN 8 km, 1951-2100 ; paramètres disponibles : `tasmin`, `tasmax`, `tas`, `prtot`, `prsn`, `huss`, `rsds`, `rlds`, `sfcWind`, `evspsblpot` (**pas d'humidité relative** dans ce produit) ; fenêtres TRACC de 20 ans par modèle fournies par le formulaire ; pas de filtre par mois ; une archive couvre le rectangle englobant les points demandés | Degrés-jours > 32 °C et VPD futurs calculés comme les observés (projections) | **Validée, téléchargée et utilisée (projections)** : historique 1976-2005 et RCP 8.5, 1 582 mailles, `tasmin`, `tasmax`, `huss` |
| Hub'Eau, API « Prélèvements en eau » (BNPE) | API interrogée sans compte : volumes annuels par ouvrage, usage `IRR`, 2008-2024 (2012-2023 commun ; agence Rhône-Méditerranée-Corse sans 2008-2011 ni 2024) | Licence Ouverte Etalab, citation de l'auteur des données | Ouvrage (point), commune, année ; toutes cultures ; prélèvements < 10 000 m³ non déclarés | Volumes d'irrigation par département et par an ; valeur descriptive par m³ dans les départements où le maïs domine l'irrigation | **Validée, téléchargée et utilisée (W1, W2)** |
| Agreste, RA2020_0052 « Surfaces irriguées par culture, OTEX et département » (2010 et 2020) | Téléchargé en test (hors dépôt) : part du maïs grain dans les surfaces irriguées en 2020 de 17 % (28) à 73 % (68) | Comme la SAA (réutilisation libre, source citée) | Département, 2010 et 2020, 18 cultures | Clé de répartition des volumes BNPE entre cultures | **Validée, téléchargée et utilisée (W2)** |
| Agreste, enquêtes Pratiques culturales grandes cultures 2017 et 2021 | Publications régionales lues (ex. Occitanie : 1 410 m³/ha, 5 tours d'eau pour le maïs grain en 2021) | Comme la SAA | Région, deux années | Dose d'irrigation du maïs, contrôle de la répartition | Utilisée comme repère (1 410 m³/ha, Occitanie 2021), sans extraction systématique |

## 8 sexies. Sources pour l'humidité du sol projetée et la récolte 2026

| Source | URL officielle | Variables utiles | Unité et couverture | Format et accès | Licence | Identifiants | Limites | Test effectué | Statut | Décision |
|---|---|---|---|---|---|---|---|---|---|---|
| DRIAS-Climat, catalogue | https://www.drias-climat.fr | Humidité du sol future ? | — | Portail, compte | Etalab | — | Aucun produit d'humidité du sol : la rubrique « Agriculture » ne contient que des indicateurs DRIAS-2020 | Arbre du catalogue parcouru avec Playwright (session de l'auteur) | Écartée pour P3 | Voir DRIAS-Eau |
| DRIAS-Eau, « Indicateurs mensuels 'Eau' par niveau de réchauffement, modèles individuels Explore2 / SIM2 » (produit `3EXPL24EAU-SIM2-IMM`) | https://www.drias-eau.fr | `NORSWIAV` (SWI moyen, sans unité), `ASWIAV` (écart au SWI de référence) ; aussi évapotranspiration, pluie efficace | Mois sélectionnables (juillet, août) ; période de référence et niveaux TRACC France +2,0, +2,7, +4,0 °C ; grille SAFRAN, points en Lambert 93 | Formulaire de commande, compte personnel (le compte DRIAS de l'auteur fonctionne) ; NetCDF ou CSV livré | Licence Etalab (conditions d'utilisation des portails DRIAS-Climat et DRIAS-Eau, lues) | 17 simulations EXPLORE2 2024 GCM/RCM corrigées par ADAMONT, mêmes couples que pour la chaleur projetée ; points de grille SAFRAN | SWI du modèle SIM2-2024 forcé par les projections, pas la réanalysis SIM2 : les niveaux peuvent différer, on n'utilise que les écarts ; période de référence à lire sur les fichiers livrés | Formulaire ouvert et lu (indicateurs, niveaux, mois) ; aucune commande passée pendant l'audit ; puis 68 commandes livrées (fichiers texte, 1 582 points × 2 mois) | Validée, téléchargée et utilisée (P3) | Source de P3 |
| SIM2, fichier quotidien 2026 (`QUOT_SIM2_2026.csv.gz`) | https://meteofrance.s3.sbg.io.cloud.ovh.net/data/REF_CC/SIM/ | Mêmes variables que les autres années | 2026 jusqu'à la date de mise à jour (fichier, 103 Mo) | Fichier direct | Licence Ouverte 2.0 | Mailles SAFRAN | Données de l'année en cours, susceptibles d'être révisées | En-tête HTTP lu (200, 103 Mo) ; téléchargé | Validée, téléchargée et utilisée (récolte 2026) | Météo de l'été 2026 (P4) |
| Agreste, Conjoncture – Infos rapides Grandes cultures n° 2026-131, fichier `2026_131donnees_grandescultures_departements.xlsx` | https://agreste.agriculture.gouv.fr/agreste-web/download/publication/publie/IraGcu26131/2026_131donnees_grandescultures_departements.xlsx | Maïs grain irrigué et non irrigué par département : surface, rendement, production, 2021-2026 | 2021-2025 : SAA définitive ; 2026 : « estimations précoces arrêtées au 1er octobre 2026 » | Fichier direct (xlsx) | Comme la SAA | Codes et noms de départements | Estimations provisoires, « à utiliser avec précaution, en particulier au niveau départemental » ; rendements établis à dire d'experts puis à partir de l'enquête Terres labourables à partir de septembre ou octobre ; la récolte du maïs n'était pas terminée au 1er octobre | Téléchargé en test hors dépôt, feuilles et en-têtes lus ; lignes « Maïs grain irrigué » et « non irrigué » repérées ; téléchargé dans le dépôt | Validée, téléchargée et utilisée avec réserve (récolte 2026) | Pré-lecture exploratoire de 2026 ; le test figé attend la SAA 2026 définitive (automne 2027) |
| Agreste, SAA 2026 provisoire et définitive | https://agreste.agriculture.gouv.fr | Rendements par mode | Département, 2026 | Fichier direct | Comme la SAA | — | Non publiée : la SAA provisoire paraît au printemps N+1, la définitive à l'automne N+1 (note du fichier ci-dessus) | URL de la série longue 2010-2026 testée : 404 | Bloquée (calendrier) | Test de la spécification figée reporté |

**Recommandation.** L'humidité du sol projetée est faisable avec le produit mensuel de DRIAS-Eau (17 simulations, juillet et août, niveaux TRACC). La récolte 2026 n'est lisible que comme pré-lecture exploratoire : la spécification figée (`specification_recoltes_futures.md`) exige des chiffres définitifs, et la note d'Agreste elle-même met en garde contre l'usage départemental des estimations de conjoncture. La note de ce fichier documente aussi, pour la première fois, la façon dont les rendements sont produits : à dire d'experts, puis à partir de l'enquête Terres labourables (17 000 exploitants, rendements moyens constatés après récolte).

## 9. Sources examinées mais non utilisées

| Source | Statut | Raison |
|---|---|---|
| INRAE, réserve utile des sols à 90 m (Román Dobarco et al. 2019, doi:10.15454/9IRARJ) | Téléchargée et testée | Analyse retirée : interaction avec la chaleur non détectée, réserve utile peu variable entre les 17 départements |
| MIRCA-OS (surfaces irriguées et pluviales par culture, 5′, 2000-2020) | Repérée, non téléchargée | Licence CC BY-NC-ND ; la part irriguée de la SAA, complète pour l'échantillon, suffit |
| Assurance récolte, aides PAC couplées, dates de semis | Recherchées | Pas de série départementale publique trouvée |
| Open-Meteo, API d'archives (ERA5, ERA5-Land) | Auditée (documentation et conditions) | Limite gratuite de 10 000 appels par jour, chaque appel couvrant deux semaines pour un point : environ 200 000 appels pour les 1 784 mailles du masque, juillet-août 2000-2025 |
| NASA POWER | Repérée, non auditée | Grille d'environ 0,5°, trop grossière pour un masque de mailles de 8 km |
| NDVI VIIRS (successeur de MODIS) | Non téléchargé | Envisagé pour la continuité après Terra ; non nécessaire pour 2010-2025 |

## 10. Empreintes SHA-256 (générées depuis le manifeste)

Les 354 fichiers AppEEARS (5.02 Go) ne sont pas listés un par un : leurs empreintes sont dans `docs/manifest_raw.csv`, et `tests/test_manifest.py` les vérifie. Les 474 fichiers MOD11A2 (température de surface) ne sont pas listés non plus, ni les 34 extractions Hub'Eau (`data/raw/hubeau_bnpe/`), ni les 34 archives DRIAS (`data/raw/drias/`, 21 Go), ni les 68 fichiers DRIAS-Eau (`data/raw/drias_eau/`), ni les deux fichiers de la récolte 2026 (`agreste_conjoncture/`, `meteofrance_sim/QUOT_SIM2_2026.csv.gz`). Les 108 autres fichiers sont listés ci-dessous.

| Fichier (`data/raw/…`) | Taille | SHA-256 |
|---|---|---|
| `agreste_saa/SAA-SeriesLongues-2010-2025_DonneesProvisoires-DepartementalesRegionales.zip` | 7.08 Mo | `46e2ea9493ae34fac5d343e6cef51ac08a455d970ce78611c5d3b2365650d76f` |
| `agreste_ra2020/FDS_RA2020_0052.zip` | 2.84 Mo | `d5bf42559ebe6c365da6e975e039c3c634803418b989080f8dbd49a02e30995b` |
| `agreste_saa_ancienne/FDS_DEVELOPPE_2.zip` | 8.81 Mo | `b7bbb133fd96335312bfe6613d39bd3f5faacc927d90c6fc9182b66e03911efa` |
| `eobs/tn_ens_mean_0.1deg_reg_1995-2010_v33.0e.nc` | 1061.73 Mo | `66735f11fe61b98a76acc24d66ceda078579801dba13f8eabaeec2cfc0b95d31` |
| `eobs/tn_ens_mean_0.1deg_reg_2011-2025_v33.0e.nc` | 922.88 Mo | `10c44bf93e2b090a0c7cbaad07eedfa54aca0b92ece8a909067ef6d160ede2d4` |
| `eobs/tx_ens_mean_0.1deg_reg_1995-2010_v33.0e.nc` | 1067.57 Mo | `8a770f8a8c9d7d967d7241ec36e90d027b043d39b658a813d938c2c92834dfc7` |
| `eobs/tx_ens_mean_0.1deg_reg_2011-2025_v33.0e.nc` | 928.09 Mo | `489c26736c57ce73ea4d112a9cc2706bd59c694d5212a15a8d7252db920be22e` |
| `ign_admin_express/ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet` | 12.92 Mo | `ba44a327aaeb9df43b1f9fd52f13ca0ec67fe748c845131fedd6b3e6c1061bce` |
| `ign_altimetrie/sim_cells_subgrid_altitude.parquet` | 3.50 Mo | `602ea33845e95950ed3332f9e6eeb599f67c36c3b3525e2e62b6b47e942dcfbf` |
| `ign_rpg/RPG_1-0__SHP_LAMB93_R24_2008-01-01.7z` | 81.32 Mo | `4997835caeba8a86b63c044f81770652529dce241f820b20df1de9914940de4a` |
| `ign_rpg/RPG_1-0__SHP_LAMB93_R27_2008-01-01.7z` | 143.81 Mo | `783e09ca6ccf8c6d63af1dff24b4bbaa1ec32d410635f01c098bc7ce995690f4` |
| `ign_rpg/RPG_1-0__SHP_LAMB93_R44_2008-01-01.7z` | 117.86 Mo | `0b2d5731f81b41617df1ae07f04876f14d93256e55aeed334a4e222c26bd871c` |
| `ign_rpg/RPG_1-0__SHP_LAMB93_R84_2008-01-01.7z` | 283.62 Mo | `9e66655d2e220b01abe9ee8ff2fc000cd89416f2bd5817148358628501befce0` |
| `ign_rpg/RPG_2-0__SHP_LAMB93_FR-2015_2015-01-01.7z` | 2821.30 Mo | `c3e5960d7a7157dfab902ae7022e8ced6a080127cc6c9763ecc87e48c863fda8` |
| `ign_rpg/RPG_2-0__SHP_LAMB93_FR-2016_2016-01-01.7z` | 2840.98 Mo | `54a410bae071b566ccb4b8e6aa5d53ed77b6cc2d0836b68f8da27238e95166ae` |
| `ign_rpg/RPG_2-0__SHP_LAMB93_FR-2017_2017-01-01.7z` | 2873.22 Mo | `589420ae130314091f4ee9c9330cb22f5d232b0fde48e28aa6bae41f8edaba90` |
| `meteofrance_sim/QUOT_SIM2_1958.csv.gz` | 52.80 Mo | `c1f1d9271e153e6cead5837855f32a033bcbb1d543cd796ad09347cad666840b` |
| `meteofrance_sim/QUOT_SIM2_1959.csv.gz` | 137.20 Mo | `10ce9a70b1d58a61fd40814af3da7302cf2077386f1d7260e1ce3a5e3696dc5a` |
| `meteofrance_sim/QUOT_SIM2_1960.csv.gz` | 140.42 Mo | `d28bb32cc0bb8da56d11f93777c3abfcacb3629517f12a8805d8626f97b7eb11` |
| `meteofrance_sim/QUOT_SIM2_1961.csv.gz` | 136.89 Mo | `6df4cf00fa76746150b1562cc60930e43c6280fdbe25c548a2e242a51ff030e5` |
| `meteofrance_sim/QUOT_SIM2_1962.csv.gz` | 139.05 Mo | `7fd248c4cf2831fcdee8736a22c68293bb32dd83eb46491740533ba9a5426a87` |
| `meteofrance_sim/QUOT_SIM2_1963.csv.gz` | 140.67 Mo | `f9bfc455f5249a68b4e7e8799d33d538ebcebfd91eacadd8120103a5687fc541` |
| `meteofrance_sim/QUOT_SIM2_1964.csv.gz` | 137.67 Mo | `fac1a1ac995124899199f76b236490fa460dceb0a4336536f80616756a153018` |
| `meteofrance_sim/QUOT_SIM2_1965.csv.gz` | 140.36 Mo | `f1f8765d5fdbc3c3c6476ed40f4b906e11bdbacb7090d1ea1fe730ab6b97f129` |
| `meteofrance_sim/QUOT_SIM2_1966.csv.gz` | 139.32 Mo | `c3330ffea53a030de22fbbf40a8a8b7f4d87ef697f897538e15c188be0a641bc` |
| `meteofrance_sim/QUOT_SIM2_1967.csv.gz` | 137.97 Mo | `e5af5a7a1a17f70a623970f69f7b1c124180171031a1eed98a8eabe3fe04885e` |
| `meteofrance_sim/QUOT_SIM2_1968.csv.gz` | 139.40 Mo | `489d3cb39b79b9ab0a62aa3d80ce4ad28029131a5c9cec2e08199167ccef54ee` |
| `meteofrance_sim/QUOT_SIM2_1969.csv.gz` | 140.16 Mo | `c5c94061764fb8f2b5a5875ae66a8c7ccf5098785706007ed05d315bbc3b641f` |
| `meteofrance_sim/QUOT_SIM2_1970.csv.gz` | 140.13 Mo | `e4ffe7598598503d684481195bca796d863f929e84499bdb28e20094268c52ba` |
| `meteofrance_sim/QUOT_SIM2_1971.csv.gz` | 138.52 Mo | `941da4bf0547b44286cf2ffad99a90d85a0d1a9ce29e737b2ab5f8620c79df4a` |
| `meteofrance_sim/QUOT_SIM2_1972.csv.gz` | 136.68 Mo | `53f07250b819a765de7f73c56c193a02697fed9856064bbfd350b9774d4d0660` |
| `meteofrance_sim/QUOT_SIM2_1973.csv.gz` | 137.61 Mo | `a3dc85bfe8bc7b28baae043918793c7828aaeb2b7e6e20a7de74eb041367e11d` |
| `meteofrance_sim/QUOT_SIM2_1974.csv.gz` | 137.27 Mo | `4839870b4a7d05df79296001449c5d9356461eeb03cc863c7dc33a7ac7e20ea5` |
| `meteofrance_sim/QUOT_SIM2_1975.csv.gz` | 137.40 Mo | `5777c81375696bd5ef28ed2fbc66de76ece1ceeccc1223e520ce7ed2dfdc690e` |
| `meteofrance_sim/QUOT_SIM2_1976.csv.gz` | 138.01 Mo | `892752e98444c06bc65272603f7dcfca6a0d47efd0b6000ae77c5b9581da5965` |
| `meteofrance_sim/QUOT_SIM2_1977.csv.gz` | 138.60 Mo | `024f87abd9a8f761532527ff4ca79c0a47efb8c68d2745c51fc6ea1f4dd9c916` |
| `meteofrance_sim/QUOT_SIM2_1978.csv.gz` | 139.51 Mo | `3afa4bbf09ade8bc0889235c857439f6318bcc0ca331b3beab4615b5f884c12f` |
| `meteofrance_sim/QUOT_SIM2_1979.csv.gz` | 140.88 Mo | `a65a3d8459445cdbb597390a690104878055c51f928674e95a50ce51c6e33473` |
| `meteofrance_sim/QUOT_SIM2_1980.csv.gz` | 139.79 Mo | `4188fccf95d6203331d29642c086d0b5754b4159f05d78f5bbc09c6606a73f6f` |
| `meteofrance_sim/QUOT_SIM2_1981.csv.gz` | 140.35 Mo | `e1086a0de9238d592ec0749873fa3ae63c77f5f3fc0bbb0d2f2c70f0de8945a4` |
| `meteofrance_sim/QUOT_SIM2_1982.csv.gz` | 138.73 Mo | `4187fe5ba3d190202a3e9698a5c7954dc49049de8b530a9b5c4469df624ce78e` |
| `meteofrance_sim/QUOT_SIM2_1983.csv.gz` | 138.56 Mo | `784afcad22b0dc74b6891b949e4cd0764b676e3cf28c30796e4a5d47d287a411` |
| `meteofrance_sim/QUOT_SIM2_1984.csv.gz` | 139.31 Mo | `8947df46359b15ea3c698ab08da9712c6a2ca286033c23ba2da1478a45b318ec` |
| `meteofrance_sim/QUOT_SIM2_1985.csv.gz` | 140.11 Mo | `576223256a320479a79429ef50c3d4682b794657db6133bc266b18c26fac50f5` |
| `meteofrance_sim/QUOT_SIM2_1986.csv.gz` | 140.69 Mo | `4916f03d5a4653f8564fcf515359f48302dc8da0bfced95e83eecf33f7edb041` |
| `meteofrance_sim/QUOT_SIM2_1987.csv.gz` | 140.19 Mo | `b2bf7d35c6c20138035e6559a165d5e366b810a0c76a15d199191ce57dbc58b7` |
| `meteofrance_sim/QUOT_SIM2_1988.csv.gz` | 138.15 Mo | `98bc946277065cbc7a915e589354580a1fd6aee010285300981a96ba08aa0f3a` |
| `meteofrance_sim/QUOT_SIM2_1989.csv.gz` | 134.49 Mo | `6620c7c0bcb7a343aa6a5aea21f664fcf6793a74fd4d736eb696a99b76493538` |
| `meteofrance_sim/QUOT_SIM2_1990.csv.gz` | 137.08 Mo | `cc91bd7afbd18160a0035a70004a357274f1006baea285d0f02806121a19a84a` |
| `meteofrance_sim/QUOT_SIM2_1991.csv.gz` | 137.76 Mo | `dc325dc6b064986a2314c0bf02cf0081866c03120735fdd9458fccca8da18d60` |
| `meteofrance_sim/QUOT_SIM2_1992.csv.gz` | 137.76 Mo | `a9febaf44e513da182ea1611e2a1f0c3b058571d986a364be514d44aa1b7ec62` |
| `meteofrance_sim/QUOT_SIM2_1993.csv.gz` | 137.63 Mo | `0b1799790acb8b0c8c191f0ec41ffe0a9da42665035e11ee4c13d58e947e2bc1` |
| `meteofrance_sim/QUOT_SIM2_1994.csv.gz` | 138.20 Mo | `f019dcc34d281d449fe9125fb1da43fd4eb67fb2ed7b761b69eff45b06cc7d89` |
| `meteofrance_sim/QUOT_SIM2_1995.csv.gz` | 138.53 Mo | `4c346e72f8286959be56954d37a8fed5f37163ade5563773ea329c82f04dfaa5` |
| `meteofrance_sim/QUOT_SIM2_1996.csv.gz` | 138.75 Mo | `2ef6182512dcceb4fc7f96bb7ca7e9642c7ee8f7fba5f9293fb24476656b02d1` |
| `meteofrance_sim/QUOT_SIM2_1997.csv.gz` | 137.66 Mo | `5f52b35f12cc4504a21c010fd0653c308a53701f30155b0e21ece88f33b1cfab` |
| `meteofrance_sim/QUOT_SIM2_1998.csv.gz` | 137.93 Mo | `9db2106726b882f91264621234c2e0d6745bb93e28dfef5349deaf0f1f068c2b` |
| `meteofrance_sim/QUOT_SIM2_1999.csv.gz` | 139.75 Mo | `6fffb36868974e88fab5a63bdfcd91959b6a740191bda40cfe4927edd3bc9610` |
| `meteofrance_sim/QUOT_SIM2_2000.csv.gz` | 138.20 Mo | `103f26c2f36b79506a0790e3a3f8ae938100ffcd03a87d9a352843dcc4ed2861` |
| `meteofrance_sim/QUOT_SIM2_2001.csv.gz` | 139.06 Mo | `cc6e74dbc04f2d661d81e4fc7212e083ef4a81fc257616f1a83546561aa4fbb7` |
| `meteofrance_sim/QUOT_SIM2_2002.csv.gz` | 136.78 Mo | `e408a59d08d2d14c036867ab26216684b67d22d52a7ae0656170a11f669add55` |
| `meteofrance_sim/QUOT_SIM2_2003.csv.gz` | 138.45 Mo | `073973fdd88e48d66be299ce033b132345d15b5f44c1e939bfc9376c48ecd84f` |
| `meteofrance_sim/QUOT_SIM2_2004.csv.gz` | 138.71 Mo | `852e5f1e9d74fecf69c26b4834fd46e8c641859a8eeaecae7003029d0af567da` |
| `meteofrance_sim/QUOT_SIM2_2005.csv.gz` | 138.72 Mo | `f0e63539825fc39b76bce24074426a5eb661ed5923f73f9f0294a2a25934335b` |
| `meteofrance_sim/QUOT_SIM2_2006.csv.gz` | 138.33 Mo | `3ca1f229bd1094277cf1e6355a3cd7c483f828c66fcc14a18a56df47d4442b61` |
| `meteofrance_sim/QUOT_SIM2_2007.csv.gz` | 136.80 Mo | `4df38ad0fe37102f38b7f9336d30268f7ca8e58ed4fc3060147839144c56aadb` |
| `meteofrance_sim/QUOT_SIM2_2008.csv.gz` | 138.44 Mo | `1988f936bea693ed0dbeea64b3dc4cf08da898ec4c2955c026e4904621f09379` |
| `meteofrance_sim/QUOT_SIM2_2009.csv.gz` | 138.83 Mo | `9c035647615ebdfdfeb47e039e5a02a0b1331db1a410bd9181af593b4cc1bc76` |
| `meteofrance_sim/QUOT_SIM2_2010.csv.gz` | 141.68 Mo | `cae71381243051c59194283927ba7c15bb3c446f24d67fdc6999e46e359006df` |
| `meteofrance_sim/QUOT_SIM2_2011.csv.gz` | 135.38 Mo | `d31a02ff6095a5299b5357a41e1bfd8a2e844c03cb342227153299eebe458a5e` |
| `meteofrance_sim/QUOT_SIM2_2012.csv.gz` | 139.33 Mo | `851a00d67ccc8d51915caa38864a9b58a0394bcde479ed66decaa2d9b407fe64` |
| `meteofrance_sim/QUOT_SIM2_2013.csv.gz` | 140.65 Mo | `90f4253be4d2a59ae79003536aff248686a810381e01c8396210543febc0f501` |
| `meteofrance_sim/QUOT_SIM2_2014.csv.gz` | 136.89 Mo | `7e1f1e8d6e34cc13b93e30cf2dd39544c47e13bb85376063ed085a6ee07b19a4` |
| `meteofrance_sim/QUOT_SIM2_2015.csv.gz` | 136.90 Mo | `e6db9413aa711102162ab98eb49e0df5499ece2e6b93b6e50c11b2c9b5adb0ad` |
| `meteofrance_sim/QUOT_SIM2_2016.csv.gz` | 137.30 Mo | `46dc2de55a2d6f656f570579f343d37691b06d4016028461f083ac6598e88d79` |
| `meteofrance_sim/QUOT_SIM2_2017.csv.gz` | 137.06 Mo | `cb3386e53814f4b305bad3d584afd404c1cec45ed1132c8af5c0795bcd44e233` |
| `meteofrance_sim/QUOT_SIM2_2018.csv.gz` | 138.30 Mo | `fc3431f1a1308bfb1cde949fd7b027777d4d73895b11e0ea16148b9471d15a22` |
| `meteofrance_sim/QUOT_SIM2_2019.csv.gz` | 137.64 Mo | `872962dab2f794f205a537786ca7e94842324e0634006d91d9f45b397b25d3bb` |
| `meteofrance_sim/QUOT_SIM2_2020.csv.gz` | 136.84 Mo | `e87d437a733f942a81c4da787ded34a373d84f4c888768708752f2a59a8228d9` |
| `meteofrance_sim/QUOT_SIM2_2021.csv.gz` | 138.09 Mo | `c42880007adb0bc292767dff3c9aa6c1519202b31f5e5c36dfbc3ac34c2d3b1e` |
| `meteofrance_sim/QUOT_SIM2_2022.csv.gz` | 136.00 Mo | `f68410968d3afd7323d702fd296636c464c13aee782c3d774826ee44a701e9f1` |
| `meteofrance_sim/QUOT_SIM2_2023.csv.gz` | 137.39 Mo | `d63976e44a3d31c186c5ff2739e3b4400bc929f8caabe9d71d0ccb7015bd18e2` |
| `meteofrance_sim/QUOT_SIM2_2024.csv.gz` | 137.94 Mo | `7d1c9d4d1ab8b257cc856183f06c557badbace89074f412184174a5c125eb419` |
| `meteofrance_sim/QUOT_SIM2_2025.csv.gz` | 136.83 Mo | `5656fb4b44531a504ecc86c755fc998e18d05a470f33fd666577f5c648f5e221` |
| `meteofrance_sim/climatologie-presentation-modele-sim-20260602.pdf` | 0.30 Mo | `be46ea685eadd21d0e2c7f19e06389f9bdf24bf106dbea5fbc4242280b3bf97c` |
| `meteofrance_sim/coordonnees_grille_safran_lambert-2-etendu.csv` | 0.28 Mo | `b02181e808c384ff4d713d46c584977ef4feada4509e72d5351d6a2fc29d6379` |
| `meteofrance_sim/sim-quotidienne-parametres-20260331.pdf` | 0.34 Mo | `8f1ec72fbf765f0e480b768a54fe89338f29522172cd7b2c71045a7ae17c4f8b` |
| `pik_schauberger/2021-001_Schauberger-et-al_Data.zip` | 3.16 Mo | `184fb3ddb62f01b646070629d8fc3667bcd95729ad40ecb1a8247f7730dab119` |
| `pik_schauberger/2021-001_Schauberger_et-al_Data-Description.pdf` | 0.60 Mo | `b8e48e2a64b50f13cd1f031784938fe0bc5814001362670c3c40de01ebeca39f` |
| `prix/eurostat_apri_ap_crpouta_FR_ble_tendre.json` | 0.00 Mo | `9856846063315894a32f81cfb93b131e272b27dae7efceb97439e2b723f82974` |
| `prix/eurostat_apri_ap_crpouta_FR_mais.json` | 0.00 Mo | `355f4c0cab2e17ca4110e99ab7449f5f1934b106fa742426a1f22c6fffec729a` |
| `prix/insee_ippap_ble_tendre_010776425.xml` | 0.01 Mo | `3df1b652790c178cd4e027cf1520abbb499593614d2368d408c5ad79255709e5` |
| `prix/insee_ippap_mais_010776430.xml` | 0.01 Mo | `02ecbbca1e24ec50ab5fa1d73f062864c6e4a8779dab55e2ac2cd9b1e53ba2c6` |
| `vigieau/arretes-2012.csv` | 0.33 Mo | `4c0ece3c115926c701c3a97d631c8c6656b732cae099c525dbb50075b0e72697` |
| `vigieau/arretes-2013.csv` | 0.09 Mo | `e926e21288e2457ab686ceaa0b9025bf7466062415f6f100da076b5f349120d7` |
| `vigieau/arretes-2014.csv` | 0.07 Mo | `8d95d621eb54f37d6dcfe45b889f7f3d4aa523fdb8bf45cb4eeddf7a9e3e053f` |
| `vigieau/arretes-2015.csv` | 0.31 Mo | `05c80b3c2ff3df625997af76cc4d184e5260aa04b58a6f7caa58e92bc875c44b` |
| `vigieau/arretes-2016.csv` | 0.23 Mo | `a641b1a5b5daf48e82abeff4a00b9f5d77e0a41efce5cb3e32d97170e578a058` |
| `vigieau/arretes-2017.csv` | 0.52 Mo | `394bb3fe36d8cc3a09061f3f6d60108640bcba8144c0cdf87c66cd620825cbf3` |
| `vigieau/arretes-2018.csv` | 0.35 Mo | `2db269d983cfc5351df6eef347e67b43192f201b0a203071343ce835796a83b6` |
| `vigieau/arretes-2019.csv` | 0.65 Mo | `fad2e3d2bc924e2b0fd36f91d41e4b26ffe94a1c651af063d2afa9b0606cb6b8` |
| `vigieau/arretes-2020.csv` | 0.53 Mo | `85c8baf6959d1f841083be4ec7569c9ab1b6120faccf0599dfe5c45813cec0a1` |
| `vigieau/arretes-2021.csv` | 0.29 Mo | `6861945b6cc8ca1331618b05f4f60e7b73df06ed26e246bf48a2d81dd53afec8` |
| `vigieau/arretes-2022.csv` | 1.66 Mo | `db19eaf2a55e1839f6c8c5e5287ea5d7db8a2b8525c191eb09f66757bf0f0392` |
| `vigieau/arretes-2023.csv` | 2.06 Mo | `aa1aafb6cc7269e1073d8b726b4f0736f0fca4b7c55b2e02de5e29ea0971fade` |
| `vigieau/arretes-2024.csv` | 0.53 Mo | `a35e2481989e5acdeb2a1de207b1cf979befa18e9755b177324685382bd02c92` |
| `vigieau/arretes-cadre.csv` | 0.89 Mo | `d95e28aca9c90d61923cbcf3eaafff349243b6d866ca6081fa9aa41c4e02eaec` |
| `vigieau/arretes.csv` | 12.49 Mo | `e3b4b5590e81c135a384857928811c32210d5cdee6db62713fb2ba771e08b27a` |

## Sources ajoutées en phase 0 bis

Empreintes au manifeste.

| Source | Accès | Couverture | Licence | Points d'attention |
|---|---|---|---|---|
| Agreste, SAA « anciennes séries », tableau « Cultures développées » (`SAANR_DEVELOPPE_2/FDS_DEVELOPPE_2.zip`) | ZIP direct (8,8 Mo), un CSV par année | 2000-2020, départements ; maïs grain irrigué / non irrigué | Comme la SAA (§ 1) : réutilisation libre avec mention de la source | Non recalée sur le RA 2020 ; identique aux séries actuelles pour 94-95 % des paires sur 2010-2020 ; pas de statut qualité |
| Météo-France SIM2, 1958-1988 | Mêmes fichiers csv.gz que 1989-2025 | 1er août 1958 → 1988 | Licence Ouverte 2.0 | 1958 partiel (début de la réanalyse) |
| VigiEau « Donnée Sécheresse » (MTE), data.gouv.fr | CSV des arrêtés (2012-2024 annuels, `arretes.csv` global, arrêtés-cadres) | Arrêtés 2010-2026 ; indicateurs construits pour 2012-2025 (période principale 2016-2025) ; 96 départements métropolitains + 4 DROM | Licence Ouverte 2.0 | Niveau de gravité manquant à 99,6-100 % en 2010-2011 et à 13-21 % en 2012-2015 |
| INSEE, IPPAP maïs (idbank 010776430) | SDMX BDM | 1970-2025, base 2020 | Licence Ouverte 2.0 (§ 7) | Indice : raccordé à Eurostat pour obtenir des €/q |
| Eurostat `apri_ap_crpouta`, maïs (`prod_veg=01500000`), France | API JSON | 2000-2016 | Réutilisation avec mention de la source (§ 7) | Série arrêtée en 2016 ; rapport à l'IPPAP stable sur 2012-2016 (0,2192 €/q par point), instable avant 2012 (0,117 à 0,176) |
| RPG 2015-2017, code `MIS` | Archives déjà téléchargées (phase 2) | Parcelles de maïs grain | Licence Ouverte 2.0 | Ne distingue pas irrigué et non irrigué ; vérifié comme maïs grain (corrélation de 0,993 avec la SAA) ; voir § 4 |
| RPG 1.0 2008, quatre régions (phase 0 ter) | ZIP 7z direct (Géoplateforme) | Îlots 2008 | Licence Ouverte 2.0 | Voir § 4 bis |

Note : ce tableau résume les sources ajoutées en phase 0 bis ; les sections 1 à 9 en donnent le détail quand il existe. La liste exhaustive des fichiers téléchargés est le manifeste `docs/manifest_raw.csv`.
