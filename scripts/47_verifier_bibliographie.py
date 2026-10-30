"""Étape 47 : vérification de la bibliographie du mémoire (clés citées, notices DOI).

Usage : uv run python scripts/47_verifier_bibliographie.py [--hors-ligne]
Entrées : memoire/references.bib ; memoire/main.tex, memoire/chapters/*.tex, memoire/tables/*.tex.
Sorties : data/raw/bib_metadata/<doi>.json (réponse brute de Crossref ou de DataCite, conservée telle quelle) ;
          reports/tables/verification_bibliographie.csv (une ligne par entrée et par champ : valeur du .bib,
          valeur du registre, statut).

Principe. (1) Toute clé citée (\\cite, \\parencite, \\textcite, \\nocite...) doit exister dans le .bib, et toute entrée
du .bib doit être citée au moins une fois (biblatex n'imprime pas les entrées non citées : une orpheline signale un
oubli ou une référence retirée du texte). (2) Pour chaque DOI, on interroge Crossref, puis DataCite si Crossref ne
connaît pas le DOI (jeux de données NASA, GFZ, thèses), et on compare auteurs (noms de famille, dans l'ordre), année,
titre, revue, volume, numéro et pages. Les comparaisons ignorent la casse, les accents, la ponctuation et les accolades
BibTeX ; un écart n'est donc jamais cosmétique. L'année du .bib est comparée à l'année de publication du numéro
(published-print) et, à défaut, à la première date connue : les deux sont rapportées.
Avec --hors-ligne, les réponses déjà enregistrées dans data/raw/bib_metadata sont relues sans nouvelle requête.
Le script ne modifie aucun fichier du mémoire.
"""

import csv
import json
import re
import sys
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request

from atlas.download import ROOT, USER_AGENT, tls_context

MEM = ROOT / "memoire"
CACHE = ROOT / "data" / "raw" / "bib_metadata"
OUT = ROOT / "reports" / "tables" / "verification_bibliographie.csv"
OFFLINE = "--hors-ligne" in sys.argv


# --- Lecture du .bib ------------------------------------------------------------------------------------------------

def read_bib(text: str) -> dict:
    """Entrées du .bib : {clé: {'type': ..., champ: valeur}}.

    Lecteur minimal, suffisant pour ce fichier : champs `nom={...}` ou `nom = {...}`, accolades imbriquées autorisées.
    """
    entries = {}
    for m in re.finditer(r"@(\w+)\s*\{\s*([^,\s]+)\s*,", text):
        kind, key = m.group(1).lower(), m.group(2)
        i, depth = m.end(), 1
        start = i
        while depth > 0:                       # fin de l'entrée : accolade fermante de même niveau
            depth += {"{": 1, "}": -1}.get(text[i], 0)
            i += 1
        body = text[start:i - 1]
        fields = {"type": kind}
        j = 0
        while True:
            f = re.compile(r"\s*,?\s*(\w+)\s*=\s*\{").match(body, j)
            if f is None:
                break
            k, depth = f.end(), 1
            while depth > 0:
                depth += {"{": 1, "}": -1}.get(body[k], 0)
                k += 1
            fields[f.group(1).lower()] = body[f.end():k - 1].strip()
            j = k
        if key in entries:
            print(f"Clé en double dans le .bib : {key}")
        entries[key] = fields
    return entries


def cited_keys() -> dict:
    """Clés citées dans le mémoire : {clé: [fichiers]}."""
    files = [MEM / "main.tex", *sorted((MEM / "chapters").glob("*.tex")), *sorted((MEM / "tables").glob("*.tex"))]
    keys = {}
    for p in files:
        text = re.sub(r"(?<!\\)%.*", "", p.read_text())          # commentaires LaTeX retirés
        for m in re.finditer(r"\\(?:[a-zA-Z]*cite[a-zA-Z]*)\*?(?:\[[^\]]*\]){0,2}\{([^}]*)\}", text):
            for k in m.group(1).split(","):
                keys.setdefault(k.strip(), []).append(p.name)
    return keys


# --- Registres DOI --------------------------------------------------------------------------------------------------

def fetch(doi: str) -> tuple[str, dict | None]:
    """Notice du DOI : ('crossref', message) ou ('datacite', attributes) ; réponse brute mise en cache."""
    path = CACHE / (re.sub(r"[^A-Za-z0-9._-]", "_", doi.lower()) + ".json")
    if path.exists():
        saved = json.loads(path.read_text())
        return saved["registre"], saved["notice"]
    if OFFLINE:
        return "absent du cache", None
    for registry, url in [("crossref", "https://api.crossref.org/works/"),
                          ("datacite", "https://api.datacite.org/dois/")]:
        req = urllib.request.Request(url + urllib.parse.quote(doi, safe="/"), headers={"User-Agent": USER_AGENT})
        try:
            with urllib.request.urlopen(req, context=tls_context(), timeout=60) as r:
                data = json.load(r)
        except urllib.error.HTTPError as e:
            if e.code == 404:
                continue
            raise
        notice = data["message"] if registry == "crossref" else data["data"]["attributes"]
        CACHE.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps({"registre": registry, "doi": doi, "notice": notice}, ensure_ascii=False, indent=1))
        time.sleep(1)                          # politesse envers les API publiques
        return registry, notice
    return "introuvable", None


def registry_fields(registry: str, n: dict) -> dict:
    """Champs comparables extraits de la notice, au même format que ceux du .bib."""
    if registry == "crossref":
        def year(part):
            d = n.get(part, {}).get("date-parts", [[None]])[0]
            return str(d[0]) if d and d[0] else ""
        authors = [a.get("family", a.get("name", "")) for a in n.get("author", [])]
        return {
            "author": authors,
            "year": year("published-print") or year("issued"),
            "year_first": year("published-online") or year("issued"),
            "title": " ".join(n.get("title", [""])),
            "journal": " ".join(n.get("container-title", [""])),
            "volume": n.get("volume", ""),
            "number": n.get("issue", ""),
            "pages": n.get("page", "") or n.get("article-number", ""),
        }
    authors = [c.get("familyName", c.get("name", "")) for c in n.get("creators", [])]
    return {
        "author": authors,
        "year": str(n.get("publicationYear", "")),
        "year_first": str(n.get("publicationYear", "")),
        "title": n.get("titles", [{}])[0].get("title", ""),
        "journal": n.get("publisher", {}).get("name", "") if isinstance(n.get("publisher"), dict)
        else str(n.get("publisher", "")),
        "volume": "", "number": "", "pages": "",
    }


# --- Normalisation et comparaison -----------------------------------------------------------------------------------

def norm(s: str) -> str:
    """Casse, accents, accolades, commandes LaTeX simples et ponctuation retirés."""
    s = s.replace("\\&", "&").replace("&amp;", "&").replace("&", " and ")
    s = re.sub(r"<[^>]+>", " ", s)                                # balises JATS dans certains titres Crossref
    s = re.sub(r"\\[a-zA-Z]+", " ", s).replace("{", "").replace("}", "")
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c)).casefold()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def bib_authors(s: str) -> list[str]:
    """Noms de famille du champ author (format « Nom, Prénom » ou « Prénom Nom »)."""
    out = []
    for a in re.split(r"\s+and\s+", s):
        a = a.strip()
        if a == "others":
            out.append("others")
        elif "," in a:
            out.append(a.split(",")[0].strip())
        else:
            out.append(a.split()[-1] if a else a)
    return out


def pages_norm(s: str) -> str:
    return re.sub(r"\s*(--|–|—|-)\s*", "-", s.strip())


def compare(field: str, bib: str, reg) -> str:
    if field == "author":
        b = [norm(x) for x in bib_authors(bib)]
        r = [norm(x) for x in reg]
        if "others" in b:                      # liste tronquée volontairement : on compare le début
            b = b[:b.index("others")]
            r = r[:len(b)]
        return "OK" if b == r else "ÉCART"
    if not bib and not reg:
        return "—"
    if not reg:
        return "absent du registre"
    if not bib:
        return "absent du .bib"
    if field == "pages":
        return "OK" if pages_norm(bib).casefold() == pages_norm(reg).casefold() else "ÉCART"
    if field == "journal":
        # Crossref donne parfois la revue avec un sous-titre (« Canadian Journal of Economics/Revue canadienne... »)
        return "OK" if norm(bib) == norm(reg) else "ÉCART"
    return "OK" if norm(bib) == norm(reg) else "ÉCART"


# --- Déroulé --------------------------------------------------------------------------------------------------------

bib = read_bib((MEM / "references.bib").read_text())
cited = cited_keys()

print(f"{len(bib)} entrées dans le .bib, {len(cited)} clés distinctes citées.")
missing = sorted(set(cited) - set(bib))
orphans = sorted(set(bib) - set(cited))
print("Clés citées absentes du .bib :", missing or "aucune")
for k in missing:
    print(f"  {k} ({', '.join(sorted(set(cited[k])))})")
print("Entrées du .bib jamais citées :", orphans or "aucune")

rows = []
for k in missing:
    rows.append({"cle": k, "champ": "clé", "bib": "", "registre": "", "statut": "citée mais absente du .bib"})
for k in orphans:
    rows.append({"cle": k, "champ": "clé", "bib": "", "registre": "", "statut": "orpheline (jamais citée)"})

FIELDS = ["author", "year", "title", "journal", "volume", "number", "pages"]
for key, e in bib.items():
    doi = e.get("doi", "")
    if not doi:
        rows.append({"cle": key, "champ": "doi", "bib": "", "registre": "", "statut": "sans DOI : contrôle manuel"})
        continue
    registry, notice = fetch(doi)
    if notice is None:
        rows.append({"cle": key, "champ": "doi", "bib": doi, "registre": registry, "statut": "DOI " + registry})
        continue
    reg = registry_fields(registry, notice)
    # DOI renvoyé par le registre : vérifie qu'il s'agit bien du même objet (alias de DOI).
    reg_doi = notice.get("DOI", notice.get("doi", ""))
    rows.append({"cle": key, "champ": "doi", "bib": doi, "registre": f"{registry}:{reg_doi}",
                 "statut": "OK" if reg_doi.casefold() == doi.casefold() else "ÉCART"})
    bib_vals = {
        "author": e.get("author", ""),
        "year": e.get("year", ""),
        "title": e.get("title", ""),
        "journal": e.get("journal", e.get("booktitle", e.get("publisher", e.get("institution", "")))),
        "volume": e.get("volume", ""),
        "number": e.get("number", ""),
        "pages": e.get("pages", e.get("eid", "")),
    }
    for f in FIELDS:
        status = compare(f, bib_vals[f], reg[f])
        if f == "year" and status == "ÉCART" and norm(bib_vals[f]) == norm(reg["year_first"]):
            status = "OK (année de mise en ligne, pas du numéro)"
        shown = "; ".join(reg[f]) if f == "author" else reg[f]
        if f == "year" and reg["year_first"] != reg["year"]:
            shown = f"{reg['year']} (en ligne : {reg['year_first']})"
        rows.append({"cle": key, "champ": f, "bib": bib_vals[f], "registre": shown, "statut": status})

OUT.parent.mkdir(parents=True, exist_ok=True)
with open(OUT, "w", newline="", encoding="utf-8") as fh:
    w = csv.DictWriter(fh, fieldnames=["cle", "champ", "bib", "registre", "statut"])
    w.writeheader()
    w.writerows(rows)

problems = [r for r in rows if r["statut"] not in ("OK", "—")]
print(f"\n{len(rows)} contrôles, {len(problems)} à examiner (écrit dans {OUT.relative_to(ROOT)}) :")
for r in problems:
    print(f"  {r['cle']:<24} {r['champ']:<8} {r['statut']:<30} bib={r['bib'][:70]!r} | registre={str(r['registre'])[:70]!r}")
