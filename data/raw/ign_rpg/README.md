# IGN / ASP — RPG 2.0 (parcelles 2015-2017) et RPG 1.0 (îlots 2008) : masques blé et maïs

- Source : https://data.geopf.fr/telechargement/resource/RPG (Licence Ouverte 2.0)
- Fichiers : `RPG_2-0__SHP_LAMB93_FR-<année>_<année>-01-01.7z` (≈ 2,8 Go chacun), France métropolitaine, Lambert 93.
- Téléchargement : `uv run python scripts/01_download_raw.py --rpg 2015-2017`
- Extraction de la seule couche utile (fichiers dérivés, hors `raw/`, ≈ 4,4 Go par millésime) :

```bash
for y in 2015 2016 2017; do
  mkdir -p data/interim/rpg/$y
  7z e -y data/raw/ign_rpg/RPG_2-0__SHP_LAMB93_FR-${y}_${y}-01-01.7z -odata/interim/rpg/$y "*/PARCELLES_GRAPHIQUES.*" -r
done
```

Le RPG 2.0 sert au masque blé (`BTH`, script 07) et au masque maïs (`MIS`, `scripts/07_build_wheat_mask.py --culture MIS`).

## RPG 1.0, 2008 (robustesse Q1-R9)

- Fichiers : `RPG_1-0__SHP_LAMB93_R{24,27,44,84}_2008-01-01.7z`, quatre régions (Centre-Val de Loire, Bourgogne-Franche-Comté, Grand Est, Auvergne-Rhône-Alpes), ≈ 0,63 Go en tout ; même source et même licence.
- Téléchargement : `uv run python scripts/01_download_raw.py --rpg1 2008`.
- Extraction et masque : `scripts/25_build_maize_mask_2008.py` (îlots du groupe 02, « maïs grain et ensilage »), qui appelle `7z` lui-même.

Outil système requis : `7zip` (paquet Ubuntu 26.04, version 26.00).
