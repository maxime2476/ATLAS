"""Étape 2 : contrôles de lecture d'un fichier SIM quotidien avant téléchargement complet.

Usage :
    uv run python scripts/02_check_sim.py               # contrôle QUOT_SIM2_2009.csv.gz
    uv run python scripts/02_check_sim.py --year 2020 --skip-remote

Contrôles :
  1. tailles annoncées par le serveur pour 2009-2025 (requêtes HEAD) ;
  2. lecture directe du csv.gz par DuckDB, colonnes et types ;
  3. couverture : dates, nombre de mailles, mailles présentes chaque jour ;
  4. cohérence des mailles avec le fichier de coordonnées officiel ;
  5. valeurs manquantes et plages de valeurs des variables utiles ;
  6. convention de date de TINF_H et TSUP_H (test des décalages, voir plus bas) ;
  7. temps de lecture, pour estimer le coût du traitement complet.
"""

import argparse
import time

import duckdb

from atlas.download import ROOT, remote_size

SIM_DIR = ROOT / "data" / "raw" / "meteofrance_sim"
SIM_BASE = "https://meteofrance.s3.sbg.io.cloud.ovh.net/data/REF_CC/SIM/"

# Colonnes attendues, dans l'ordre observé (en-tête du fichier 2020).
EXPECTED_COLUMNS = [
    "LAMBX", "LAMBY", "DATE", "PRENEI", "PRELIQ", "T", "FF", "Q", "DLI", "SSI", "HU",
    "EVAP", "ETP", "PE", "SWI", "SSWI_10J", "DRAINC", "RUNC", "RESR_NEIGE",
    "RESR_NEIGE6", "HTEURNEIGE", "HTEURNEIGE6", "HTEURNEIGEX", "SNOW_FRAC",
    "ECOULEMENT", "WG_RACINE", "WGI_RACINE", "TINF_H", "TSUP_H",
]
# Variables utiles au projet : nom -> (min plausible, max plausible), unités de la notice.
RANGES = {
    "T": (-40, 45),        # °C
    "TINF_H": (-45, 40),   # °C
    "TSUP_H": (-35, 50),   # °C
    "PRELIQ": (0, 500),    # mm/jour
    "PRENEI": (0, 500),    # mm/jour
    "ETP": (0, 20),        # mm/jour
    "SWI": (-0.5, 2.0),    # « % » dans la notice, mais l'en-tête 2020 montre des valeurs ~0.9 : à vérifier
    "WG_RACINE": (0, 1),   # m3/m3
}


def check_all_years() -> None:
    """Pour chaque fichier local : colonnes, jours, mailles, doublons, manquants T/TINF_H/TSUP_H/SWI."""
    con = duckdb.connect()
    t0 = time.perf_counter()
    for path in sorted(SIM_DIR.glob("QUOT_SIM2_*.csv.gz")):
        year = int(path.name[10:14])
        names = [c[0] for c in con.execute(
            f"DESCRIBE SELECT * FROM read_csv('{path}', delim=';', header=true)").fetchall()]
        n, n_days, d_min, d_max, n_cells, n_pairs, n_na = con.execute(f"""
            SELECT count(*), count(DISTINCT DATE), min(DATE), max(DATE),
                   count(DISTINCT (LAMBX, LAMBY)), count(DISTINCT (LAMBX, LAMBY, DATE)),
                   count(*) FILTER (WHERE T IS NULL OR TINF_H IS NULL OR TSUP_H IS NULL OR SWI IS NULL)
            FROM read_csv('{path}', delim=';', header=true)""").fetchone()
        expected_days = 366 if year % 4 == 0 else 365
        ok = (names == EXPECTED_COLUMNS and n_days == expected_days and n_cells == 9892
              and n == n_pairs == expected_days * 9892 and n_na == 0)
        print(f"  {year}: lignes={n:,} jours={n_days} ({d_min}..{d_max}) mailles={n_cells} "
              f"doublons={n - n_pairs} manquants={n_na}  {'OK' if ok else 'ÉCART'}")
    print(f"  temps : {time.perf_counter() - t0:.0f} s")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--year", type=int, default=2009)
    parser.add_argument("--skip-remote", action="store_true")
    parser.add_argument("--all-years", action="store_true",
                        help="contrôle léger de couverture sur tous les fichiers locaux")
    args = parser.parse_args()
    if args.all_years:
        check_all_years()
        return
    path = SIM_DIR / f"QUOT_SIM2_{args.year}.csv.gz"

    if not args.skip_remote:
        print("== 1. Tailles distantes 2009-2025")
        total = 0
        for year in range(2009, 2026):
            size = remote_size(SIM_BASE + f"QUOT_SIM2_{year}.csv.gz")
            total += size or 0
            print(f"  {year}: " + (f"{size / 1e6:7.1f} Mo" if size else "taille non annoncée"))
        print(f"  total : {total / 1e9:.2f} Go compressés")

    con = duckdb.connect()
    t0 = time.perf_counter()
    # Lecture directe du fichier compressé ; DATE lue comme entier AAAAMMJJ puis convertie.
    con.execute(f"""
        CREATE TABLE sim AS
        SELECT * REPLACE (strptime(CAST(DATE AS VARCHAR), '%Y%m%d')::DATE AS DATE)
        FROM read_csv('{path}', delim=';', header=true)
    """)
    elapsed = time.perf_counter() - t0
    print(f"\n== 2. Lecture de {path.name} : {elapsed:.1f} s")
    cols = con.execute("DESCRIBE sim").fetchall()
    names = [c[0] for c in cols]
    print("  colonnes conformes à l'attendu :", names == EXPECTED_COLUMNS)
    if names != EXPECTED_COLUMNS:
        print("  colonnes lues :", names)
    print("  types :", {c[0]: c[1] for c in cols if c[0] in ("LAMBX", "LAMBY", "DATE", "T", "TINF_H", "TSUP_H", "SWI")})

    print("\n== 3. Couverture")
    n, d_min, d_max, n_dates, n_cells = con.execute("""
        SELECT count(*), min(DATE), max(DATE), count(DISTINCT DATE),
               count(DISTINCT (LAMBX, LAMBY)) FROM sim""").fetchone()
    print(f"  lignes={n:,}  dates={d_min}..{d_max} ({n_dates} jours)  mailles={n_cells}")
    per_day = con.execute("""SELECT min(c), max(c) FROM
        (SELECT DATE, count(*) c FROM sim GROUP BY DATE)""").fetchone()
    dup = con.execute("""SELECT count(*) FROM
        (SELECT LAMBX, LAMBY, DATE FROM sim GROUP BY ALL HAVING count(*) > 1)""").fetchone()[0]
    print(f"  mailles par jour : min={per_day[0]} max={per_day[1]}  doublons (maille, date) = {dup}")

    print("\n== 4. Cohérence avec la grille officielle")
    grid = SIM_DIR / "coordonnees_grille_safran_lambert-2-etendu.csv"
    con.execute(f"""
        CREATE TABLE grid AS SELECT "LAMBX (hm)" AS LAMBX, "LAMBY (hm)" AS LAMBY
        FROM read_csv('{grid}', delim=';', header=true, decimal_separator=',')""")
    n_grid = con.execute("SELECT count(*) FROM grid").fetchone()[0]
    missing_in_data = con.execute("""SELECT count(*) FROM grid g ANTI JOIN
        (SELECT DISTINCT LAMBX, LAMBY FROM sim) s USING (LAMBX, LAMBY)""").fetchone()[0]
    missing_in_grid = con.execute("""SELECT count(*) FROM (SELECT DISTINCT LAMBX, LAMBY FROM sim) s
        ANTI JOIN grid g USING (LAMBX, LAMBY)""").fetchone()[0]
    print(f"  mailles grille={n_grid}  absentes des données={missing_in_data}  absentes de la grille={missing_in_grid}")

    print("\n== 5. Manquants et plages (unités de la notice Météo-France)")
    for var, (lo, hi) in RANGES.items():
        nn, vmin, vmax, out = con.execute(f"""
            SELECT count(*) FILTER (WHERE {var} IS NULL), min({var}), max({var}),
                   count(*) FILTER (WHERE {var} < {lo} OR {var} > {hi}) FROM sim""").fetchone()
        print(f"  {var:9s} manquants={nn:<6d} min={vmin:8.3f} max={vmax:8.3f} hors [{lo}, {hi}] : {out}")
    inverted = con.execute("SELECT avg((TINF_H > TSUP_H)::INT) FROM sim").fetchone()[0]
    print(f"  part des lignes avec TINF_H > TSUP_H : {inverted:.4%}")

    # 6. Convention de date. La notice définit T sur ]00UTC-00UTC] du jour DATE,
    # TINF_H sur ]18UTC-18UTC] et TSUP_H sur ]06UTC-06UTC], sans dire si la fenêtre
    # commence le jour DATE ou la veille. Test : corrélation des variations
    # journalières (pour neutraliser la persistance) entre X(DATE) et T(DATE + k).
    # Le k qui maximise la corrélation indique à quel jour civil X se rapporte.
    print("\n== 6. Convention de date (corrélation de ΔX(d) avec ΔT(d+k))")
    con.execute("""
        CREATE TABLE diffs AS
        SELECT LAMBX, LAMBY, DATE,
               T      - lag(T)      OVER w AS dT,
               TINF_H - lag(TINF_H) OVER w AS dTN,
               TSUP_H - lag(TSUP_H) OVER w AS dTX
        FROM sim WINDOW w AS (PARTITION BY LAMBX, LAMBY ORDER BY DATE)""")
    for var in ("dTN", "dTX"):
        res = []
        for k in (-1, 0, 1):
            r = con.execute(f"""
                SELECT corr(a.{var}, b.dT) FROM diffs a JOIN diffs b
                ON a.LAMBX = b.LAMBX AND a.LAMBY = b.LAMBY AND b.DATE = a.DATE + INTERVAL ({k}) DAY
            """).fetchone()[0]
            res.append(f"k={k:+d}: {r:.3f}")
        print(f"  {var}: " + "  ".join(res))
    print(f"\nTemps total : {time.perf_counter() - t0:.1f} s")


if __name__ == "__main__":
    main()
