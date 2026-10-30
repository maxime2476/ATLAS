"""Téléchargement de fichiers bruts avec vérification TLS et empreinte SHA-256.

Choix : bibliothèque standard uniquement (urllib, ssl, hashlib). Les fichiers
sont écrits d'abord sous un nom temporaire, puis renommés une fois complets,
pour ne jamais laisser un fichier brut tronqué sous son nom définitif.
"""

import hashlib
import ssl
import urllib.request
from pathlib import Path

# Racine du dépôt. Suppose l'installation éditable faite par `uv sync`
# (le paquet est importé depuis src/atlas/, pas depuis site-packages).
ROOT = Path(__file__).resolve().parents[2]

# Agreste n'envoie pas son certificat intermédiaire (voir certs/README.md).
AGRESTE_INTERMEDIATE = ROOT / "certs" / "harica_geant_tls_rsa_1.pem"
AGRESTE_INTERMEDIATE_SHA256 = (
    "5b678dc44095a52895b63b31f27227f4b36c3e347491bf2bfa691837a5fb8c79"
)

USER_AGENT = "atlas-research-pipeline (projet académique)"


def sha256_of_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def tls_context(extra_intermediate: bool = False) -> ssl.SSLContext:
    """Contexte TLS par défaut (vérification complète).

    Avec extra_intermediate=True, on ajoute l'intermédiaire HARICA/GEANT au
    magasin système après avoir vérifié son empreinte. Python ≥ 3.13 active par
    défaut VERIFY_X509_PARTIAL_CHAIN, qui ferait de cet intermédiaire une ancre
    de confiance : on retire ce drapeau pour que la chaîne doive remonter
    jusqu'à la racine HARICA du magasin système. Nom d'hôte et validité restent vérifiés.
    """
    context = ssl.create_default_context()
    if extra_intermediate:
        der = ssl.PEM_cert_to_DER_cert(AGRESTE_INTERMEDIATE.read_text())
        fingerprint = hashlib.sha256(der).hexdigest()
        if fingerprint != AGRESTE_INTERMEDIATE_SHA256:
            raise RuntimeError(
                f"Empreinte inattendue pour {AGRESTE_INTERMEDIATE}: {fingerprint}"
            )
        context.load_verify_locations(cafile=str(AGRESTE_INTERMEDIATE))
        context.verify_flags &= ~ssl.VERIFY_X509_PARTIAL_CHAIN
    return context


def remote_size(url: str, context: ssl.SSLContext | None = None) -> int | None:
    """Taille annoncée par le serveur (requête HEAD), ou None si absente."""
    request = urllib.request.Request(url, method="HEAD", headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, context=context or tls_context(), timeout=60) as r:
        length = r.headers.get("Content-Length")
    return int(length) if length is not None else None


def download(url: str, dest: Path, context: ssl.SSLContext | None = None,
             overwrite: bool = False) -> dict:
    """Télécharge `url` vers `dest` et renvoie une ligne de manifeste.

    Un fichier déjà présent n'est pas retéléchargé (sauf overwrite=True) :
    les données brutes ne doivent pas être modifiées une fois obtenues.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    downloaded = False
    if dest.exists() and not overwrite:
        print(f"déjà présent, non retéléchargé : {dest.relative_to(ROOT)}")
    else:
        tmp = dest.with_name(dest.name + ".part")
        request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(request, context=context or tls_context(), timeout=120) as r:
                expected = r.headers.get("Content-Length")
                with open(tmp, "wb") as f:
                    for block in iter(lambda: r.read(1024 * 1024), b""):
                        f.write(block)
            if expected is not None and tmp.stat().st_size != int(expected):
                raise RuntimeError(f"Téléchargement incomplet : {url}")
        except BaseException:
            tmp.unlink(missing_ok=True)  # ne jamais laisser de fichier partiel
            raise
        tmp.replace(dest)
        downloaded = True
        print(f"téléchargé : {dest.relative_to(ROOT)} ({dest.stat().st_size / 1e6:.1f} Mo)")
    return {
        "file": str(dest.relative_to(ROOT)),
        "url": url,
        "size_bytes": dest.stat().st_size,
        "sha256": sha256_of_file(dest),
        "downloaded": downloaded,
    }
