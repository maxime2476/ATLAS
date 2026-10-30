# Agreste — SAA « anciennes séries », tableau « Cultures développées » (SAANR_DEVELOPPE_2)

- Source : site Agreste, publication `SAANR_DEVELOPPE_2`, fichier `FDS_DEVELOPPE_2.zip` (8,8 Mo, un CSV par année 2000-2020). Comme la SAA : réutilisation libre, y compris commerciale, avec la mention « Source : Agreste » (mentions légales du site).
- Téléchargement : `uv run python scripts/01_download_raw.py --saa-ancienne`. Le serveur Agreste ne fournit pas sa chaîne de certificats complète : le certificat intermédiaire est dans `certs/`.
- Colonnes : NOM;ANNREF;FRANCE;FRDOM;REGION;DEP;N306;N306_MOD;N306_LIB;N027;N027_MOD;N027_LIB;VALEUR;QUALITE.
- Utilisation :
  - « Maïs grain irrigué » et « Maïs grain non irrigué » (superficie en ha, rendement en q/ha) sur **2000-2009** ;
  - 60 à 65 départements par an ;
  - script `scripts/22_build_panel_mais.py`.
- Limites :
  - séries non recalées sur le recensement agricole 2020 ;
  - identiques aux séries actuelles pour 94-95 % des valeurs sur 2010-2020 ;
  - pas de statut qualité par département (QUALITE vaut toujours « OUI »).
