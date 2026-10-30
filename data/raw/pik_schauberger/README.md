# Schauberger et al. (2022) — rendements départementaux 1900-2018

- Source : GFZ Data Services, DOI 10.5880/PIK.2021.001, CC-BY 4.0 (citer Schauberger et al. 2022, *Scientific Data* 9:38).
- Fichiers : `2021-001_Schauberger-et-al_Data.zip` (versions FILTERED et RAW), notice PDF.
- **ATLAS utilise la version RAW** : la version FILTERED masque surtout des années de pertes réelles.
- Rendements en t/ha, indexés par nom de département (appariement aux codes INSEE dans `src/atlas/schauberger.py`).
- Les années 1989-2018 viennent de l'ancienne base Agreste (non recalée sur le RA 2020) ; compatibilité vérifiée sur 2010-2018 (`scripts/08_check_schauberger.py`).
