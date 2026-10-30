"""Étape 32 : diagrammes du README (SVG clairs et sombres) : chaîne de données, règle de décision, frise du projet.

Usage : uv run python scripts/32_diagrammes_readme.py
Sorties (docs/figures/) : pipeline_atlas[_dark].svg, regle_decision[_dark].svg, frise_projet[_dark].svg

Système graphique : diagram-design (Cathryn Lavery, licence MIT, https://github.com/cathrynlavery/diagram-design),
types « Medallion » (chaîne de données), « Flowchart » (règle de décision) et « Timeline » (frise). Adaptations
pour GitHub, qui affiche un SVG comme une image : texte en <text>/<tspan> (pas de <foreignObject>), polices
système (une image SVG ne charge pas de police externe), fond uni sans motif de points.
- Medallion : marge droite réduite à la marge gauche (aucune légende) ; étages de 296 px au lieu de 380.
- Flowchart : les chiffres des deux exemples sont lus dans reports/tables/.
- Timeline : une bande par temps du projet ; seul l'ordre des étapes est représenté.
Le contenu décrit le dépôt ; le mettre à jour s'il change.
"""

import pandas as pd

from atlas.download import ROOT

OUT = ROOT / "docs" / "figures"

TIERS = [
    {"name": "Brut", "bucket": "data/raw/", "style": "outer",
     "tool": ["scripts 01, 17, 30", "manifeste SHA-256"], "format": ["CSV · netCDF · GeoTIFF", "XLSX · Shapefile"],
     "writer": ["téléchargement,", "jamais modifié"], "example": ["SIM2 quotidien, 8 km", "SAA, deux éditions"]},
    {"name": "Intermédiaire", "bucket": "data/interim/", "style": "default",
     "tool": ["DuckDB · pandas"], "format": ["Parquet"],
     "writer": ["scripts 03, 05, 08"], "example": ["météo maille × mois", "SAA au format long"]},
    {"name": "Panels", "bucket": "data/processed/", "style": "default",
     "tool": ["GeoPandas", "masques RPG maïs, blé"], "format": ["Parquet", "+ dictionnaire"],
     "writer": ["scripts 04-34"], "example": ["maïs : 435 paires", "blé : 1959-2025"]},
    {"name": "Résultats", "bucket": "reports/tables/", "style": "focal",
     "tool": ["R : fixest, module wcr", "Python : scikit-learn"], "format": ["CSV, dans le dépôt"],
     "writer": ["R/10-23 ; Python :", "10, 15, 16, 19, 24, 28"], "example": ["+1,6 % par °C·jour", "taille des tests"]},
    {"name": "Mémoire", "bucket": "memoire/ · README", "style": "default", "color": "olive",
     "tool": ["script 26 · LaTeX"], "format": ["macros · PDF", "figures"],
     "writer": ["chiffres générés", "depuis reports/tables/"], "example": ["mémoire de 50 pages", "figures du README"]},
]
PROMOTIONS = ["DEGRÉS-JOURS", "MASQUES RPG", "ESTIMATION", "PUBLICATION"]   # ≤ 14 caractères
PATHS = [
    {"tag": "PYTHON · UV", "title": "Python 3.12 · uv · uv.lock",
     "sub": "ingestion · géospatial · degrés-jours · prévision"},
    {"tag": "R · RENV", "title": "R 4.5 · renv · fixest · module wcr",
     "sub": "effets fixes · bootstrap par année · taille par placebo"},
]

# Jetons du guide de style (light / dark) ; olive = « publication » dans la palette sémantique.
SKINS = {
    "light": {"paper": "#f5f5f5", "paper2": "#ececec", "ink": "#2d3142", "muted": "#4f5d75", "soft": "#5a6580",
              "accent": "#bf4520", "white": "#ffffff", "olive": "#7a8c47",
              "ink_rgb": "45,49,66", "muted_rgb": "79,93,117", "accent_rgb": "191,69,32", "olive_rgb": "122,140,71"},
    "dark": {"paper": "#2d3142", "paper2": "#393e53", "ink": "#f5f5f5", "muted": "#bfc0c0", "soft": "#949eb2",
             "accent": "#f08a59", "white": "rgba(245,245,245,0.04)", "olive": "#9aad66",
             "ink_rgb": "245,245,245", "muted_rgb": "191,192,192", "accent_rgb": "240,138,89", "olive_rgb": "154,173,102"},
}

TIER_W, TIER_H, GAP, PAD, ARC_H, PATH_H, PATH_GAP, BOTTOM = 172, 296, 16, 16, 80, 56, 16, 16
N = len(TIERS)
W = 2 * PAD + N * TIER_W + (N - 1) * GAP
H = ARC_H + TIER_H + PATH_GAP + PATH_H + BOTTOM
PATH_W = (W - 2 * PAD - GAP) // 2


def tier_x(i):
    return PAD + i * (TIER_W + GAP)


def lines(x, y, values, cls, extra=""):
    """Une à deux lignes de 9 px (interligne 11 px), sans foreignObject."""
    tspans = "".join(f'<tspan x="{x}" dy="{0 if k == 0 else 11}">{v}</tspan>' for k, v in enumerate(values))
    return f'<text x="{x}" y="{y}" class="{cls}"{extra}>{tspans}</text>'


def medallion_svg(skin: str) -> str:
    c = SKINS[skin]
    slug = "pipeline-atlas" + ("-dark" if skin == "dark" else "")
    out = [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {W} {H}" width="{W}" height="{H}" role="img" '
           f'aria-labelledby="{slug}-title {slug}-desc">',
           f'<title id="{slug}-title">Chaîne de données d\'ATLAS</title>',
           f'<desc id="{slug}-desc">Les fichiers bruts téléchargés, jamais modifiés, deviennent des tables intermédiaires, '
           f'puis des panels départementaux, puis des tables de résultats estimées en R et en Python, dont sont '
           f'générés les chiffres du mémoire.</desc>',
           "<style>"
           f".t{{fill:{c['ink']};font:600 13px 'Geist',system-ui,-apple-system,'Segoe UI',sans-serif;text-anchor:middle}}"
           f".b{{fill:{c['muted']};font:400 9px 'Geist Mono',ui-monospace,'SFMono-Regular',Menlo,Consolas,monospace;text-anchor:middle}}"
           f".fl{{fill:{c['ink']};font:600 11px 'Geist',system-ui,-apple-system,'Segoe UI',sans-serif}}"
           f".fv{{fill:{c['muted']};font:400 9px 'Geist Mono',ui-monospace,'SFMono-Regular',Menlo,Consolas,monospace}}"
           f".el{{fill:{c['soft']};font:500 8px 'Geist Mono',ui-monospace,Menlo,Consolas,monospace;letter-spacing:0.08em}}"
           f".al{{font:500 10px 'Geist Mono',ui-monospace,Menlo,Consolas,monospace;letter-spacing:0.08em;text-anchor:middle}}"
           f".pt{{fill:{c['ink']};font:500 7px 'Geist Mono',ui-monospace,Menlo,Consolas,monospace;letter-spacing:0.08em;text-anchor:middle}}"
           f".ph{{fill:{c['ink']};font:600 11px 'Geist',system-ui,-apple-system,'Segoe UI',sans-serif}}"
           f".ps{{fill:{c['muted']};font:400 9px 'Geist Mono',ui-monospace,Menlo,Consolas,monospace}}"
           "</style>",
           "<defs>"
           f'<marker id="{slug}-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{c["muted"]}"/></marker>'
           f'<marker id="{slug}-arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{c["accent"]}"/></marker>'
           f'<marker id="{slug}-arrow-olive" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{c["olive"]}"/></marker>']
    for i in range(N):
        out.append(f'<clipPath id="{slug}-clip{i}"><rect x="{tier_x(i)}" y="{ARC_H}" width="{TIER_W}" height="{TIER_H}" rx="6"/></clipPath>')
    out.append("</defs>")
    out.append(f'<rect width="{W}" height="{H}" fill="{c["paper"]}"/>')

    # Arcs de promotion d'abord (les cartes passent par-dessus) ; style dicté par l'étage d'arrivée.
    for k, label in enumerate(PROMOTIONS):
        x0, x1 = tier_x(k) + TIER_W // 2, tier_x(k + 1) + TIER_W // 2
        target = TIERS[k + 1]
        if target["style"] == "focal":
            col, width, marker = c["accent"], 1.6, "arrow-accent"
        elif target.get("color") == "olive":
            col, width, marker = c["olive"], 1.4, "arrow-olive"
        else:
            col, width, marker = c["muted"], 1.4, "arrow"
        out.append(f'<path d="M{x0} {ARC_H} C{x0} 0 {x1} 0 {x1} {ARC_H}" fill="none" stroke="{col}" '
                   f'stroke-width="{width}" marker-end="url(#{slug}-{marker})"/>')
        out.append(f'<text x="{(x0 + x1) // 2}" y="50" class="al" fill="{col}">{label}</text>')

    for i, t in enumerate(TIERS):
        x, cx = tier_x(i), tier_x(i) + TIER_W // 2
        if t["style"] == "focal":
            fill, band, stroke, sw, hi = f"rgba({c['accent_rgb']},0.07)", f"rgba({c['accent_rgb']},0.14)", c["accent"], 1.6, c["accent"]
        elif t.get("color") == "olive":
            fill, band, stroke, sw, hi = f"rgba({c['olive_rgb']},0.07)", f"rgba({c['olive_rgb']},0.14)", c["olive"], 1.4, c["olive"]
        elif t["style"] == "outer":
            fill, band, stroke, sw, hi = c["white"], f"rgba({c['muted_rgb']},0.10)", c["muted"], 1, None
        else:
            fill, band, stroke, sw, hi = c["white"], f"rgba({c['ink_rgb']},0.06)", (c["ink"] if skin == "light" else "rgba(245,245,245,0.30)"), 1, None
        hl = f' fill="{hi}"' if hi else ""
        fx = x + 16
        out += [f'<rect x="{x}" y="{ARC_H}" width="{TIER_W}" height="{TIER_H}" rx="6" fill="{fill}"/>',
                f'<rect x="{x}" y="{ARC_H}" width="{TIER_W}" height="50" fill="{band}" clip-path="url(#{slug}-clip{i})"/>',
                f'<rect x="{x}" y="{ARC_H}" width="{TIER_W}" height="{TIER_H}" rx="6" fill="none" stroke="{stroke}" stroke-width="{sw}"/>',
                f'<text x="{cx}" y="106" class="t">{t["name"]}</text>',
                f'<text x="{cx}" y="144" class="b"{hl}>{t["bucket"]}</text>']
        for label, key, y in [("Outil", "tool", 172), ("Format", "format", 216), ("Produit par", "writer", 260)]:
            out.append(f'<text x="{fx}" y="{y}" class="fl">{label}</text>')
            out.append(lines(fx, y + 14, t[key], "fv"))
        out.append(f'<text x="{fx}" y="324" class="el">EXEMPLE ATLAS</text>')
        out.append(lines(fx, 338, t["example"], "fv", hl))

    py = ARC_H + TIER_H + PATH_GAP
    for j, p in enumerate(PATHS):
        x = PAD + j * (PATH_W + GAP)
        out += [f'<rect x="{x}" y="{py}" width="{PATH_W}" height="{PATH_H}" rx="6" fill="{c["white"]}" stroke="rgba({c["ink_rgb"]},0.20)"/>',
                f'<rect x="{x + 8}" y="{py + 6}" width="64" height="12" rx="2" fill="none" stroke="rgba({c["ink_rgb"]},0.30)" stroke-width="0.8"/>',
                f'<text x="{x + 40}" y="{py + 15}" class="pt">{p["tag"]}</text>',
                f'<text x="{x + 80}" y="{py + 30}" class="ph">{p["title"]}</text>',
                f'<text x="{x + 80}" y="{py + 46}" class="ps">{p["sub"]}</text>']
    out.append("</svg>")
    return "\n".join(out) + "\n"


# --- Styles communs aux deux autres diagrammes -------------------------------------------------------
SANS = "'Geist',system-ui,-apple-system,'Segoe UI',sans-serif"
MONO = "'Geist Mono',ui-monospace,'SFMono-Regular',Menlo,Consolas,monospace"


def head(slug: str, w: int, h: int, title: str, desc: str, c: dict) -> list[str]:
    return [f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img" '
            f'aria-labelledby="{slug}-title {slug}-desc">',
            f'<title id="{slug}-title">{title}</title>', f'<desc id="{slug}-desc">{desc}</desc>',
            "<style>"
            f".n{{fill:{c['ink']};font:600 12px {SANS};text-anchor:middle}}"
            f".nb{{fill:{c['ink']};font:600 14px {SANS};text-anchor:middle}}"
            f".s{{fill:{c['muted']};font:400 9px {MONO};text-anchor:middle}}"
            f".lab{{font:400 8px {MONO};letter-spacing:0.12em;text-anchor:middle}}"
            f".d{{font:400 8px {MONO};letter-spacing:0.14em;text-anchor:middle}}"
            f".lg{{fill:{c['muted']};font:400 8.5px {SANS}}}"
            f".lgh{{fill:{c['muted']};font:400 8px {MONO};letter-spacing:0.18em}}"
            "</style>",
            "<defs>"
            f'<marker id="{slug}-arrow" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{c["muted"]}"/></marker>'
            f'<marker id="{slug}-arrow-accent" markerWidth="8" markerHeight="6" refX="7" refY="3" orient="auto"><polygon points="0 0, 8 3, 0 6" fill="{c["accent"]}"/></marker>'
            "</defs>",
            f'<rect width="{w}" height="{h}" fill="{c["paper"]}"/>']


def two_lines(x, y, a, b, cls_a="n", cls_b="s"):
    return [f'<text x="{x}" y="{y}" class="{cls_a}">{a}</text>', f'<text x="{x}" y="{y + 16}" class="{cls_b}">{b}</text>']


def arrow(x1, y1, x2, y2, c, slug, accent=False, dashed=False):
    col = c["accent"] if accent else c["muted"]
    dash = ' stroke-dasharray="4,3"' if dashed else ""
    mk = "arrow-accent" if accent else "arrow"
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" stroke="{col}" stroke-width="{1.4 if accent else 1.2}"'
            f'{dash} marker-end="url(#{slug}-{mk})"/>')


def label(x, y, text, c, w, accent=False):
    """Étiquette de flèche sur un masque opaque (règle 2 : écart visible avec le trait)."""
    col = c["accent"] if accent else c["muted"]
    return [f'<rect x="{x - w / 2}" y="{y - 9}" width="{w}" height="12" rx="2" fill="{c["paper"]}"/>',
            f'<text x="{x}" y="{y}" class="lab" fill="{col}">{text}</text>']


def decision_numbers() -> dict:
    """Exemples réels : H1 du maïs (règle remplie) et Q2-H1 du blé 1959-2025 (règle non remplie)."""
    tab = ROOT / "reports" / "tables"
    h = pd.read_csv(tab / "phase4bis_q1_hypotheses.csv").set_index("hypothese").loc["H1"]
    size = pd.read_csv(tab / "phase4bis_q1_taille.csv").set_index("inference").loc["wcr_annee", "taille_5pct"]
    q2 = pd.read_csv(tab / "phase4bis_q2_hypotheses.csv")
    q2 = q2[q2.periode == "1959-2025"].iloc[0]
    fr = lambda x, d: f"{x:.{d}f}".replace(".", ",")
    return {"maize_p": fr(h.p_unilaterale, 3), "maize_size": fr(100 * size, 1),
            "wheat_p": fr(q2.p_wcb_annee_unilateral_gauche, 3)}


def flowchart_svg(skin: str) -> str:
    c = SKINS[skin]
    slug = "regle-decision" + ("-dark" if skin == "dark" else "")
    k = decision_numbers()
    W2, H2 = 960, 704
    cx = 360                                    # colonne principale ; sorties « non » à droite
    ex = 700                                    # centre des issues « non établie »
    out = head(slug, W2, H2, "Règle de décision des hypothèses principales",
               "Une hypothèse principale n'est établie que si la taille de son test, mesurée par placebo, est d'au plus "
               "10 % et si la p-valeur unilatérale du bootstrap par année est inférieure à 0,05 ; les vérifications "
               "ajoutées ensuite sont rapportées sans changer ce statut.", c)
    ext_fill, ext_stroke = f"rgba({c['ink_rgb']},0.03)", f"rgba({c['ink_rgb']},0.30)"
    box = c["white"]
    # Flèches d'abord (sous les formes).
    out += [arrow(cx, 88, cx, 120, c, slug), arrow(cx, 168, cx, 196, c, slug),
            arrow(cx + 132, 248, ex - 124, 248, c, slug), arrow(cx, 300, cx, 340, c, slug),
            arrow(cx + 132, 392, ex - 124, 392, c, slug), arrow(cx, 444, cx, 484, c, slug, accent=True),
            arrow(cx, 540, cx, 572, c, slug, dashed=True)]
    out += label((cx + 132 + ex - 124) / 2, 240, "NON", c, 28) + label(cx + 22, 324, "OUI", c, 28)
    out += label((cx + 132 + ex - 124) / 2, 384, "NON", c, 28) + label(cx + 22, 468, "OUI", c, 28, accent=True)
    # Départ (ovale)
    out.append(f'<rect x="{cx - 132}" y="40" width="264" height="48" rx="20" fill="{ext_fill}" stroke="{ext_stroke}"/>')
    out += two_lines(cx, 60, "Hypothèse principale", "fixée dans le plan, sens du test inclus")
    # Étape (rectangle)
    out.append(f'<rect x="{cx - 132}" y="120" width="264" height="48" rx="6" fill="{box}" stroke="{c["ink"]}"/>')
    out += two_lines(cx, 140, "Estimer le modèle", "effets fixes département et année")
    # Décision 1 (losange)
    out.append(f'<polygon points="{cx},196 {cx + 132},248 {cx},300 {cx - 132},248" fill="{box}" stroke="{c["ink"]}"/>')
    out += [f'<text x="{cx}" y="244" class="n">Taille du test</text>', f'<text x="{cx}" y="260" class="n">≤ 10 % ?</text>',
            f'<text x="{cx - 150}" y="252" class="s" text-anchor="end" style="text-anchor:end">placebo : années permutées</text>']
    # Issue 1
    out.append(f'<rect x="{ex - 124}" y="224" width="248" height="48" rx="20" fill="{ext_fill}" stroke="{ext_stroke}"/>')
    out += two_lines(ex, 244, "Non établie", "test non fiable sur ces données")
    # Décision 2
    out.append(f'<polygon points="{cx},340 {cx + 132},392 {cx},444 {cx - 132},392" fill="{box}" stroke="{c["ink"]}"/>')
    out += [f'<text x="{cx}" y="388" class="n">p bootstrap par</text>', f'<text x="{cx}" y="404" class="n">année &lt; 0,05 ?</text>',
            f'<text x="{cx - 150}" y="396" class="s" text-anchor="end" style="text-anchor:end">unilatérale, 9 999 tirages</text>']
    # Issue 2
    out.append(f'<rect x="{ex - 124}" y="368" width="248" height="48" rx="20" fill="{ext_fill}" stroke="{ext_stroke}"/>')
    out += two_lines(ex, 388, "Non établie, rapportée", f"ex. blé 1959-2025 : p = {k['wheat_p']}")
    # Issue focale
    out.append(f'<rect x="{cx - 132}" y="484" width="264" height="56" rx="20" fill="rgba({c["accent_rgb"]},0.08)" stroke="{c["accent"]}"/>')
    out += two_lines(cx, 508, "Établie, au sens de la règle", f"ex. maïs : p = {k['maize_p']}, taille {k['maize_size']} %")
    # Vérifications ajoutées (étape facultative, pointillés)
    out.append(f'<rect x="{cx - 132}" y="572" width="264" height="48" rx="6" fill="rgba({c["ink_rgb"]},0.02)" '
               f'stroke="rgba({c["ink_rgb"]},0.30)" stroke-dasharray="4,3"/>')
    out += two_lines(cx, 592, "Vérifications ajoutées", "rapportées, sans changer le statut")
    # Légende (bande du bas)
    y0 = 648
    out += [f'<line x1="40" y1="{y0}" x2="{W2 - 40}" y2="{y0}" stroke="rgba({c["ink_rgb"]},0.10)" stroke-width="0.8"/>',
            f'<text x="40" y="{y0 + 16}" class="lgh">LÉGENDE · LA FORME DONNE LE TYPE</text>',
            f'<rect x="40" y="{y0 + 32}" width="24" height="12" rx="6" fill="{ext_fill}" stroke="{ext_stroke}"/>',
            f'<text x="72" y="{y0 + 42}" class="lg">Départ / issue</text>',
            f'<rect x="200" y="{y0 + 32}" width="24" height="12" rx="2" fill="{box}" stroke="{c["ink"]}"/>',
            f'<text x="232" y="{y0 + 42}" class="lg">Étape</text>',
            f'<polygon points="324,{y0 + 38} 336,{y0 + 32} 348,{y0 + 38} 336,{y0 + 44}" fill="{box}" stroke="{c["ink"]}"/>',
            f'<text x="360" y="{y0 + 42}" class="lg">Décision</text>',
            f'<line x1="452" y1="{y0 + 40}" x2="480" y2="{y0 + 40}" stroke="{c["accent"]}" stroke-width="1.4" marker-end="url(#{slug}-arrow-accent)"/>',
            f'<text x="488" y="{y0 + 42}" class="lg">Chemin d\'une hypothèse établie</text>',
            f'<line x1="680" y1="{y0 + 40}" x2="708" y2="{y0 + 40}" stroke="{c["muted"]}" stroke-width="1.2" stroke-dasharray="4,3" marker-end="url(#{slug}-arrow)"/>',
            f'<text x="716" y="{y0 + 42}" class="lg">Ajouté après coup</text>']
    out.append("</svg>")
    return "\n".join(out) + "\n"


# Frise : (temps, titre, sous-titre, majeur). Ordre des étapes, sans dates.
EVENTS = [
    (0, "Cadrage", "blé tendre, sources", False),
    (0, "Données et panels", "SIM2, SAA, RPG", False),
    (0, "Blé 2010-2025", "tests usuels trop permissifs", True),
    (0, "Prévision, maïs", "phases 5 et 6", False),
    (1, "Recentrage", "maïs irrigué / non irrigué", False),
    (1, "Maïs 2000-2025", "plan, puis estimations", True),
    (1, "Contrôle des données", "masque maïs de 2008", False),
    (2, "Vérifications", "E-OBS, puissance", False),
    (2, "Compléments", "analyses exploratoires", False),
]
DAYS = ["PREMIER TEMPS", "DEUXIÈME TEMPS", "TROISIÈME TEMPS"]


def timeline_svg(skin: str) -> str:
    c = SKINS[skin]
    slug = "frise-projet" + ("-dark" if skin == "dark" else "")
    W3, H3, x0, x1, base = 1200, 372, 60, 1140, 150
    band = (x1 - x0) / len(DAYS)
    out = head(slug, W3, H3, "Étapes du projet ATLAS",
               "Frise des étapes du projet en trois temps, du cadrage sur le blé à l'analyse du maïs "
               "irrigué et non irrigué, puis aux vérifications ajoutées ensuite.", c)
    out.append(f'<line x1="{x0}" y1="{base}" x2="{x1}" y2="{base}" stroke="rgba({c["muted_rgb"]},0.45)" stroke-width="1"/>')
    for d, name in enumerate(DAYS):
        xa = x0 + d * band
        out += [f'<line x1="{xa}" y1="{base - 8}" x2="{xa}" y2="{base + 8}" stroke="rgba({c["ink_rgb"]},0.20)"/>',
                f'<text x="{xa + band / 2}" y="{H3 - 92}" class="d" fill="{c["soft"]}">{name}</text>']
    out.append(f'<line x1="{x1}" y1="{base - 8}" x2="{x1}" y2="{base + 8}" stroke="rgba({c["ink_rgb"]},0.20)"/>')
    for d in range(len(DAYS)):
        evs = [e for e in EVENTS if e[0] == d]
        for j, (_, title, sub, major) in enumerate(evs):
            x = x0 + d * band + (j + 1) * band / (len(evs) + 1)
            k = EVENTS.index((d, title, sub, major))
            up = k % 2 == 1                                   # alternance haut / bas sur toute la frise
            col = c["accent"] if major else f"rgba({c['ink_rgb']},0.30)"
            y_end = base - (64 if major else 52) if up else base + (64 if major else 52)
            out.append(f'<line x1="{x}" y1="{min(base, y_end)}" x2="{x}" y2="{max(base, y_end)}" stroke="{col}"/>')
            out.append(f'<circle cx="{x}" cy="{base}" r="{6 if major else 4}" fill="{c["accent"] if major else c["ink"]}"/>')
            cls = "nb" if major else "n"
            if up:
                out += [f'<text x="{x}" y="{y_end - 22}" class="{cls}">{title}</text>',
                        f'<text x="{x}" y="{y_end - 8}" class="s">{sub}</text>']
            else:
                out += [f'<text x="{x}" y="{y_end + 18}" class="{cls}">{title}</text>',
                        f'<text x="{x}" y="{y_end + 32}" class="s">{sub}</text>']
    y0 = H3 - 64
    out += [f'<line x1="40" y1="{y0}" x2="{W3 - 40}" y2="{y0}" stroke="rgba({c["ink_rgb"]},0.10)" stroke-width="0.8"/>',
            f'<text x="40" y="{y0 + 16}" class="lgh">LÉGENDE</text>',
            f'<circle cx="52" cy="{y0 + 36}" r="4" fill="{c["ink"]}"/><text x="68" y="{y0 + 40}" class="lg">Étape</text>',
            f'<circle cx="148" cy="{y0 + 36}" r="6" fill="{c["accent"]}"/><text x="164" y="{y0 + 40}" class="lg">Tournant du projet</text>',
            f'<text x="300" y="{y0 + 40}" class="lg" font-style="italic">Une bande par jour (échelle réelle) ; dans une journée, '
            f'seul l\'ordre des étapes est représenté, pas leur durée.</text>']
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for base, fn in [("pipeline_atlas", medallion_svg), ("regle_decision", flowchart_svg), ("frise_projet", timeline_svg)]:
        for skin, suffix in [("light", ""), ("dark", "_dark")]:
            (OUT / f"{base}{suffix}.svg").write_text(fn(skin), encoding="utf-8")
            print(f"écrit docs/figures/{base}{suffix}.svg")


if __name__ == "__main__":
    main()
