"""Étape 37 : commande et téléchargement des projections DRIAS EXPLORE2-Climat 2022.

Usage (Playwright n'est pas une dépendance du projet ; navigateur Chromium installé par `playwright install chromium`) :
    uv run --with playwright==1.63.0 python scripts/37_drias_telechargement.py commander     # passe les commandes
    uv run --with playwright==1.63.0 python scripts/37_drias_telechargement.py telecharger   # récupère les archives
    uv run --with playwright==1.63.0 python scripts/37_drias_telechargement.py fenetres      # fenêtres TRACC par modèle
Prérequis : compte DRIAS personnel ; DRIAS_LOGIN et DRIAS_PASSWORD dans .env (jamais affichés ni versionnés).
Sorties : data/raw/drias/*.zip (archives livrées, non modifiées) ; data/raw/drias/commandes.csv (références) ;
          data/raw/drias/fenetres_tracc.csv (fenêtres de 20 ans du formulaire, par modèle et niveau de réchauffement) ;
          manifeste docs/manifest_raw.csv.

Le portail n'a pas d'API : le script remplit le formulaire « données quotidiennes corrigées par ADAMONT [NetCDF] »
comme le ferait l'utilisateur (jeu de données, période, liste de points en Lambert 93, paramètres), une commande à la
fois, avec des pauses.
"""

import csv
import importlib.util
import sys
import time
from datetime import date

import pandas as pd
from playwright.sync_api import sync_playwright
from pyproj import Transformer

from atlas.download import ROOT, download

RAW = ROOT / "data" / "raw" / "drias"
ORDERS = RAW / "commandes.csv"
DEP17 = ["01", "03", "18", "26", "28", "36", "37", "38", "39", "41", "45", "58", "63", "67", "68", "69", "89"]
PARAMS = ["tasminAdjust", "tasmaxAdjust", "hussAdjust"]
HIST = (1976, 2005)
PORTAL = "https://www.drias-climat.fr"


def credentials() -> tuple[str, str]:
    env = {}
    for line in (ROOT / ".env").read_text().splitlines():
        if line.startswith("DRIAS_") and "=" in line:
            key, value = line.split("=", 1)
            env[key] = value
    return env["DRIAS_LOGIN"], env["DRIAS_PASSWORD"]


def mask_points() -> str:
    """Mailles du masque maïs des 17 départements, en Lambert 93 (seul système accepté par le formulaire)."""
    w = pd.read_parquet(ROOT / "data" / "processed" / "weights_cell_dep_maize.parquet")
    cells = w[w.dep_code.isin(DEP17)][["LAMBX", "LAMBY"]].drop_duplicates().sort_values(["LAMBX", "LAMBY"])
    to93 = Transformer.from_crs("EPSG:27572", "EPSG:2154", always_xy=True)
    x, y = to93.transform(cells.LAMBX.to_numpy() * 100.0, cells.LAMBY.to_numpy() * 100.0)
    return len(cells), "\n".join(f"{a:.0f};{b:.0f};m" for a, b in zip(x, y))


def login(page) -> None:
    page.on("dialog", lambda d: (print("  dialogue du portail :", d.message[:200].replace("\n", " ")), d.accept()))
    user, password = credentials()
    page.goto(f"{PORTAL}/commande", timeout=90000, wait_until="networkidle")
    page.fill("input[name='login']", user)
    page.fill("input[name='mdpE']", password)
    page.click("#acces_btn")
    page.wait_for_timeout(15000)
    band = [f for f in page.frames if "bandeauLogin" in f.url][0]
    if "Utilisateur connecté" not in band.evaluate("() => document.body.innerText"):
        raise SystemExit("connexion DRIAS refusée")


def frame(page, part: str):
    return [f for f in page.frames if part in f.url or f.name == part][0]


def open_form(page):
    if not any("branche.jsp" in f.url for f in page.frames):   # après une commande, l'arbre du catalogue a disparu
        frame(page, "bandeauLogin").click("text=Catalogue")
        page.wait_for_timeout(12000)
    frame(page, "branche.jsp").evaluate("() => ouvreLaRubrique2('explore2atmosadamont')")
    page.wait_for_timeout(10000)
    frame(page, "listeProduits").click("a[href*='3EXPLORE2-CLIM22-TQ2'].produitliste")
    page.wait_for_timeout(20000)
    form = frame(page, "rubrique")
    form.select_option("select[name='example_length']", "100")
    page.wait_for_timeout(2000)
    return form


def read_orders() -> list[dict]:
    if not ORDERS.exists():
        return []
    with open(ORDERS, newline="") as f:
        return list(csv.DictReader(f))


def save_order(row: dict) -> None:
    new = not ORDERS.exists()
    with open(ORDERS, "a", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=list(row))
        if new:
            writer.writeheader()
        writer.writerow(row)


def commander() -> None:
    RAW.mkdir(parents=True, exist_ok=True)
    n_points, points = mask_points()
    done = {(r["modele"], r["scenario"]) for r in read_orders()}
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 2600})
        login(page)
        form = open_form(page)
        rows = form.evaluate("() => [...document.querySelectorAll('#example tbody tr')].map(r => r.cells[1].innerText.trim() + '|' + r.cells[2].innerText.trim())")
        models = sorted({r.split("|")[0] for r in rows if r.endswith("|RCP8.5")})
        windows = form.evaluate("() => Object.fromEntries(Object.keys(perGWL).map(k => [k, [perGWL[k].debGWL1, perGWL[k].finGWL3]]))")
        print(f"{len(models)} modèles en RCP 8.5 ; {n_points} points")
        for model in models:
            for scenario in ["Historique", "RCP8.5"]:
                if (model, scenario) in done:
                    continue
                start, end = HIST if scenario == "Historique" else (max(2021, int(windows[model][0])), int(windows[model][1]))
                form = open_form(page)
                form.locator("#example tbody tr", has_text=model).filter(has_text=scenario).first.click()
                page.wait_for_timeout(3000)
                form.evaluate("""([a, b]) => { document.formulaire.dateDeb.value = a; document.formulaire.dateFin.value = b;
                                               initAnneesDuScenario(a, b); }""", [str(start), str(end)])
                form.evaluate("() => razRefGeo()")
                page.wait_for_timeout(3000)
                form.evaluate("""(liste) => { document.formulaire.kposition.selectedIndex = 0; formatLigne(0);
                                              document.formulaire.listepos.value = liste; updateRefGeoSelonProximite(); }""", points)
                page.wait_for_timeout(30000)
                got = int(form.input_value("#nbrePoints"))
                if got != n_points:
                    raise SystemExit(f"{model} {scenario} : {got} points retenus au lieu de {n_points}")
                form.evaluate("""(params) => { for (const v of params)
                                    document.querySelector(`input[name=listeParam][value=${v}]`).checked = true;
                                  compteSelectedParams(); }""", PARAMS)
                form.click("input[name='ajoutpanier']")
                page.wait_for_timeout(15000)
                frame(page, "bandeauLogin").click("text=Mon panier")
                page.wait_for_timeout(8000)
                frame(page, "rubrique").click("input[value='Confirmer la requête']")
                page.wait_for_timeout(15000)
                text = frame(page, "rubrique").evaluate("() => document.body.innerText")
                refs = [w for w in text.split() if w.isdigit() and len(w) == 13]
                if "correctement transmise" not in text or len(refs) != 1:
                    raise SystemExit(f"{model} {scenario} : confirmation inattendue")
                save_order({"reference": refs[0], "modele": model, "scenario": scenario, "debut": start, "fin": end,
                            "points": n_points, "parametres": " ".join(PARAMS), "date": date.today().isoformat()})
                print(f"commande {refs[0]} : {model} {scenario} {start}-{end}")
                time.sleep(20)   # pause entre deux commandes, pour ne pas surcharger le portail
        browser.close()


def fenetres() -> None:
    """Fenêtres TRACC lues dans le formulaire (variable JavaScript perGWL du portail)."""
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1600, "height": 2600})
        login(page)
        form = open_form(page)
        w = form.evaluate("() => Object.keys(perGWL).map(k => [k, perGWL[k].debGWL1, perGWL[k].finGWL1, perGWL[k].debGWL2, perGWL[k].finGWL2, perGWL[k].debGWL3, perGWL[k].finGWL3])")
        browser.close()
    rows = [{"modele": m, "niveau": lvl, "debut": int(r[2 * i + 1]), "fin": int(r[2 * i + 2])}
            for r in w for m in [r[0]] for i, lvl in enumerate(["France +2.0", "France +2.7", "France +4.0"])]
    pd.DataFrame(rows).to_csv(RAW / "fenetres_tracc.csv", index=False)
    print(f"{len(w)} modèles, fenêtres enregistrées")


def telecharger() -> None:
    """Relève les liens de livraison (session connectée), puis télécharge en flux avec atlas.download.

    Les archives dépassent 512 Mo, taille maximale d'une réponse lue par Playwright ; les liens de livraison
    (https://www.drias-climat.fr/donnees/<date>/<fichier>.zip) se téléchargent sans session.
    """
    orders = {r["reference"]: r for r in read_orders()}
    spec = importlib.util.spec_from_file_location("dl", ROOT / "scripts" / "01_download_raw.py")
    dl = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(dl)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page()
        login(page)
        frame(page, "bandeauLogin").click("text=Mes requêtes")
        page.wait_for_timeout(12000)
        links = frame(page, "rubrique").evaluate(
            "() => [...document.querySelectorAll('a[href*=\"_visualiserProduit\"]')].map(a => a.href)")
        browser.close()
    rows, source_of, pending = [], {}, 0
    for ref in orders:
        hits = [h for h in links if f"p2={ref}" in h]
        if not hits:
            pending += 1
            continue
        url = hits[0].split("p1=", 1)[1].split("&p2=")[0]
        row = download(url, RAW / url.rsplit("/", 1)[1])
        row["url"] = "commande DRIAS-Climat (lien de livraison temporaire)"   # le lien expire : seule la commande se reproduit
        rows.append(row)
        source_of[row["file"]] = "drias"
        dl.update_manifest(rows[-1:], source_of)          # manifeste à jour après chaque archive
        time.sleep(5)
    print(f"{len(rows)} archives présentes ; {pending} commandes pas encore livrées")


if __name__ == "__main__":
    {"commander": commander, "telecharger": telecharger, "fenetres": fenetres}[sys.argv[1]]()
