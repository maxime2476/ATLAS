# E-OBS v33.0e (ECA&D / Copernicus) : Tmin et Tmax journalières, grille 0,1°

- Source : https://surfobs.climate.copernicus.eu/dataaccess/access_eobs.php (moyenne d'ensemble, grille régulière 0,1°).
- Fichiers : `tn_ens_mean_0.1deg_reg_{1995-2010,2011-2025}_v33.0e.nc` et `tx_…` (≈ 4 Go au total).
- Licence : politique de données ECA&D/E-OBS, usage non commercial (recherche et enseignement) ; citer Cornes et al. (2018), DOI 10.1029/2017JD028200. Ces fichiers ne sont pas redistribués.
- Téléchargement : `uv run python scripts/01_download_raw.py --eobs`.
- Utilisation : `scripts/27_eobs_heat.py` (degrés-jours > 32 °C de juillet-août, masque maïs), vérification E-OBS (`R/20_q1_eobs.R`).
- Détails et limites : `docs/sources.md`, § 8 bis.
