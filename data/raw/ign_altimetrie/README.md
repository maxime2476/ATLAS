# IGN — altitudes des mailles SIM (service de calcul altimétrique de la Géoplateforme)

- Service : https://data.geopf.fr/altimetrie/1.0/calcul/alti/rest/elevation.json (POST), ressource `ign_rge_alti_wld` (RGE ALTI®), licence Etalab 2.0.
- Fichier : `sim_cells_subgrid_altitude.parquet`, réponse brute (16 points par maille SIM française, sous-grille 4 × 4 de pas 2 km), produite par `scripts/13_cell_altitude.py`.
- Le script ne réinterroge pas le service si le fichier existe (données brutes non modifiées). Limites d'usage : 5 000 points par requête, 5 requêtes par seconde.
