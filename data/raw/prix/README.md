# Prix agricoles — INSEE IPPAP et Eurostat (valorisation descriptive)

| Fichier | Source | Contenu |
|---|---|---|
| `insee_ippap_ble_tendre_010776425.xml` | INSEE BDM, SDMX, idbank 010776425 | Indice annuel des prix à la production, blé tendre (base 2020) |
| `insee_ippap_mais_010776430.xml` | INSEE BDM, SDMX, idbank 010776430 | Idem pour le maïs (1970-2025) |
| `eurostat_apri_ap_crpouta_FR_ble_tendre.json` | Eurostat `apri_ap_crpouta`, `prod_veg=01110000` | Prix absolu du blé tendre en France, €/100 kg (jusqu'en 2016) |
| `eurostat_apri_ap_crpouta_FR_mais.json` | Eurostat `apri_ap_crpouta`, `prod_veg=01500000` | Prix absolu du maïs, €/100 kg (2000-2016) |

- Téléchargement : `uv run python scripts/01_download_raw.py --prix`.
- Utilisation : l'indice IPPAP est converti en €/q par son rapport à Eurostat sur 2012-2016. Ce rapport doit être stable (écart < 0,002 €/q par point), sinon la valorisation est abandonnée :
  - blé : 0,2504 €/q par point, `scripts/16_phase6_build.py` ;
  - maïs : 0,2192 €/q par point, `scripts/24_valorisation_mais.py`.
- Licences (vérifiées sur les sites des producteurs) : INSEE, Licence Ouverte 2.0 avec la mention « Source : Insee » ; Eurostat, réutilisation autorisée avec mention de la source (voir `NOTICE.md`).
