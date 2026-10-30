# MTE — VigiEau « Donnée Sécheresse » (arrêtés de restriction d'eau)

- Source : https://www.data.gouv.fr/datasets/donnee-secheresse-vigieau, Licence Ouverte 2.0.
- Fichiers :
  - `arretes-2012.csv` à `arretes-2024.csv` : arrêtés par année ;
  - `arretes.csv` : fichier global, tous les arrêtés depuis 2010 ; c'est le seul lu par le projet ;
  - `arretes-cadre.csv`.
- Version : ressources datées du 2026-09-15 (chemins horodatés `static.data.gouv.fr`).
- Téléchargement : `uv run python scripts/01_download_raw.py --vigieau`.
- Utilisation : `scripts/23_vigieau_indicators.py` (jours de juillet-août à chaque niveau de gravité, par département).
- Limites :
  - niveau de gravité manquant pour 99,6-100 % des arrêtés en 2010-2011 (années exclues) et pour 13-21 % en 2012-2015 ;
  - indicateur « au moins une zone du département ».
