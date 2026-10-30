"""Étape 41 : commande et téléchargement du SWI projeté de juillet-août (DRIAS-Eau, Explore2 / SIM2).

Usage (Playwright n'est pas une dépendance du projet, comme pour l'étape 37) :
    uv run --with playwright==1.63.0 python scripts/41_drias_eau.py commander [--test]   # passe les commandes
    uv run --with playwright==1.63.0 python scripts/41_drias_eau.py telecharger          # récupère les fichiers livrés
Prérequis : compte DRIAS personnel (le même que pour DRIAS-Climat) ; DRIAS_LOGIN et DRIAS_PASSWORD dans .env.
Sorties : data/raw/drias_eau/indices*.txt (68 fichiers texte livrés, non modifiés) ; data/raw/drias_eau/commandes.csv ; manifeste docs/manifest_raw.csv.

Produit « Indicateurs mensuels 'Eau' par niveau de réchauffement, modèles individuels Explore2 / SIM2 »
(3EXPL24EAU-SIM2-IMM) : une commande par simulation et par niveau (référence, France +2,0, +2,7, +4,0 °C),
mois de juillet et d'août, indicateur NORSWIAV (SWI moyen), mailles du masque maïs des 17 départements.
"""

import csv
import importlib.util
import sys
import time
from datetime import date

from playwright.sync_api import sync_playwright

from atlas.download import ROOT, download

spec = importlib.util.spec_from_file_location("d37", ROOT / "scripts" / "37_drias_telechargement.py")
d37 = importlib.util.module_from_spec(spec)
spec.loader.exec_module(d37)

RAW = ROOT / "data" / "raw" / "drias_eau"
ORDERS = RAW / "commandes.csv"
PORTAL = "https://www.drias-eau.fr"
PRODUCT = "3EXPL24EAU-SIM2-IMM"
LEVELS = {"REF": "reference", "RWL20": "France +2.0", "RWL27": "France +2.7", "RWL40": "France +4.0"}


def login(page) -> None:
    page.on("dialog", lambda d: (print("  dialogue du portail :", d.message[:200].replace("\n", " ")), d.accept()))
    user, password = d37.credentials()
    page.goto(f"{PORTAL}/commande", timeout=90000, wait_until="networkidle")
    page.fill("input[name='login']", user)
    page.fill("input[name='mdpE']", password)
    page.click("#acces_btn")
    page.wait_for_timeout(15000)
    band = d37.frame(page, "bandeauLogin")
    if "Utilisateur connecté" not in band.evaluate("() => document.body.innerText"):
        raise SystemExit("connexion DRIAS-Eau refusée")


def open_form(page):
    if not any("branche.jsp" in f.url for f in page.frames):   # après une commande, l'arbre du catalogue a disparu
        d37.frame(page, "bandeauLogin").click("text=Catalogue")
        page.wait_for_timeout(12000)
    d37.frame(page, "branche.jsp").evaluate("() => ouvreLaRubrique2('indicSimII2024eau')")
    page.wait_for_timeout(10000)
    d37.frame(page, "listeProduits").click(f"a[href*='{PRODUCT}']")
    page.wait_for_timeout(20000)
    form = d37.frame(page, "rubrique")
    form.select_option("select[name='example_length']", "100")
    page.wait_for_timeout(2000)
    return form


def commander(test: bool = False) -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    n_points, points = d37.mask_points()
    done = set()
    if ORDERS.exists():
        with open(ORDERS, newline="") as f:
            done = {(r["modele"], r["niveau"]) for r in csv.DictReader(f)}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 2600})
        login(page)
        form = open_form(page)
        models = form.evaluate("() => [...document.querySelectorAll('#example tbody tr')].map(r => r.cells[1].innerText.trim())")
        print(f"{len(models)} simulations ; {n_points} points")
        for model in models:
            for level in LEVELS:
                if (model, level) in done:
                    continue
                form = open_form(page)
                form.locator("#example tbody tr", has_text=model).first.click()
                page.wait_for_timeout(3000)
                form.check(f"input[name='rechauf'][value='{level}']")
                for m in [f"{k:02d}" for k in range(1, 13)]:      # clics réels : déclenchent les contrôles du formulaire
                    form.set_checked(f"input[name='fMois'][value='{m}']", m in ("07", "08"))
                form.evaluate("() => razRefGeo()")
                page.wait_for_timeout(3000)
                form.evaluate("""(liste) => { document.formulaire.kposition.selectedIndex = 0; formatLigne(0);
                                              document.formulaire.listepos.value = liste; updateRefGeoSelonProximite(); }""", points)
                page.wait_for_timeout(30000)
                got = int(form.input_value("#nbrePoints"))
                if got != n_points:
                    raise SystemExit(f"{model} {level} : {got} points retenus au lieu de {n_points}")
                form.evaluate("""() => { document.querySelector('input[name=listeParam][value=NORSWIAV]').checked = true;
                                         compteSelectedParams(); }""")
                form.click("input[name='ajoutpanier']")
                page.wait_for_timeout(15000)
                d37.frame(page, "bandeauLogin").click("text=Mon panier")
                page.wait_for_timeout(8000)
                d37.frame(page, "rubrique").click("input[value='Confirmer la requête']")
                page.wait_for_timeout(15000)
                text = d37.frame(page, "rubrique").evaluate("() => document.body.innerText")
                refs = [w for w in text.split() if w.isdigit() and len(w) == 13]
                if "correctement transmise" not in text or len(refs) != 1:
                    raise SystemExit(f"{model} {level} : confirmation inattendue\n{text[:800]}")
                row = {"reference": refs[0], "modele": model, "niveau": level, "mois": "07 08", "points": n_points,
                       "indicateur": "NORSWIAV", "date": date.today().isoformat()}
                new = not ORDERS.exists()
                with open(ORDERS, "a", newline="") as f:
                    writer = csv.DictWriter(f, fieldnames=list(row))
                    if new:
                        writer.writeheader()
                    writer.writerow(row)
                print(f"commande {refs[0]} : {model} {LEVELS[level]}")
                if test:
                    browser.close()
                    return
                time.sleep(20)   # pause entre deux commandes, pour ne pas surcharger le portail
        browser.close()


def telecharger() -> None:
    """Relève les liens de livraison dans « Mes requêtes », puis télécharge chaque fichier livré avec atlas.download."""
    with open(ORDERS, newline="") as f:
        orders = {r["reference"]: r for r in csv.DictReader(f)}
    dl_spec = importlib.util.spec_from_file_location("dl", ROOT / "scripts" / "01_download_raw.py")
    dl = importlib.util.module_from_spec(dl_spec)
    dl_spec.loader.exec_module(dl)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        login(page)
        d37.frame(page, "bandeauLogin").click("text=Mes requêtes")
        page.wait_for_timeout(12000)
        links = d37.frame(page, "rubrique").evaluate(
            "() => [...document.querySelectorAll('a[href*=\"_visualiserProduit\"]')].map(a => a.href)")
        browser.close()
    rows, source_of, pending = [], {}, 0
    for ref in orders:
        hits = [h for h in links if f"p2={ref}" in h]
        if not hits:
            pending += 1
            continue
        url = hits[0].split("p1=", 1)[1].split("&p2=")[0]
        dest = RAW / url.rsplit("/", 1)[1]
        if dest.exists():
            continue
        row = download(url, dest)
        row["url"] = "commande DRIAS-Eau (lien de livraison temporaire)"   # le lien expire : seule la commande se reproduit
        rows.append(row)
        source_of[row["file"]] = "drias_eau"
        dl.update_manifest(rows[-1:], source_of)
        time.sleep(3)
    print(f"{len(rows)} fichiers téléchargés ; {pending} commandes pas encore livrées")


if __name__ == "__main__":
    if sys.argv[1] == "commander":
        commander(test="--test" in sys.argv)
    else:
        telecharger()
