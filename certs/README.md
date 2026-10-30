# Certificat intermédiaire pour agreste.agriculture.gouv.fr

Le serveur d'Agreste n'envoie que son certificat final (constat : `openssl s_client` → `Verify return code: 21`). Il omet le certificat intermédiaire qui l'a signé. Les navigateurs le récupèrent automatiquement, mais `curl` et Python échouent.

Plutôt que de désactiver la vérification TLS, on fournit cet intermédiaire **en plus** du magasin de certificats du système :

| Champ | Valeur |
|---|---|
| Fichier | `harica_geant_tls_rsa_1.pem` |
| Sujet | `C=GR, O=Hellenic Academic and Research Institutions CA, CN=GEANT TLS RSA 1` |
| Émetteur | `HARICA TLS RSA Root CA 2021` (racine présente dans le magasin système Ubuntu) |
| Validité | 2025-01-03 → 2039-12-31 |
| Empreinte SHA-256 du certificat | `5B:67:8D:C4:40:95:A5:28:95:B6:3B:31:F2:72:27:F4:B3:6C:3E:34:74:91:BF:2B:FA:69:18:37:A5:FB:8C:79` |
| Source | URL « CA Issuers » (AIA) du certificat du serveur : http://crt.harica.gr/HARICA-GEANT-TLS-R1.cer (format DER converti en PEM) |

Contrôles :

- `openssl verify -CAfile /etc/ssl/certs/ca-certificates.crt harica_geant_tls_rsa_1.pem` renvoie `OK` : l'intermédiaire remonte bien à une racine de confiance.
- `src/atlas/download.py` revérifie l'empreinte avant chaque usage.

Ce certificat est public ; le versionner ne pose pas de problème de sécurité. Si Agreste corrige sa configuration, ce fichier deviendra inutile mais restera sans effet néfaste.
