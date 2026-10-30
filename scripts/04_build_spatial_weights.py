"""Étape 4 : poids surfaciques maille SIM -> département (métropole).

Usage : uv run python scripts/04_build_spatial_weights.py
Sortie : data/processed/weights_cell_dep_area.parquet
Imprime un tableau de contrôle de la jointure spatiale.
"""

from atlas.download import ROOT
from atlas.spatial import area_weights, departements, sim_cells

RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "processed" / "weights_cell_dep_area.parquet"


def main() -> None:
    cells = sim_cells(RAW / "meteofrance_sim" / "coordonnees_grille_safran_lambert-2-etendu.csv")
    dep = departements(RAW / "ign_admin_express" / "ADMIN-EXPRESS-COG-CARTO_4-0_2026-01-01_departement.parquet")
    print(f"mailles : {len(cells)} | départements métropolitains : {len(dep)}")
    print(f"géométries invalides : mailles={(~cells.is_valid).sum()}  départements={(~dep.is_valid).sum()}")

    w = area_weights(cells, dep)

    # --- Tableau de contrôle --------------------------------------------------
    n_cells_used = w[["LAMBX", "LAMBY"]].drop_duplicates().shape[0]
    deps_per_cell = w.groupby(["LAMBX", "LAMBY"]).size()
    covered = w.groupby("dep_code")["area_m2"].sum() / dep.set_index("dep_code").area
    print(f"lignes (maille, dép.) : {len(w)}")
    print(f"mailles intersectant au moins un département : {n_cells_used} / {len(cells)}")
    print(f"mailles sur 1 / 2 / 3+ départements : {(deps_per_cell == 1).sum()} / "
          f"{(deps_per_cell == 2).sum()} / {(deps_per_cell >= 3).sum()}")
    print(f"départements sans maille : {sorted(set(dep.dep_code) - set(w.dep_code))}")
    print(f"part de la surface départementale couverte par la grille : "
          f"min={covered.min():.4f} ({covered.idxmin()}), médiane={covered.median():.4f}")
    print(f"mailles par département : min={w.groupby('dep_code').size().min()} "
          f"({w.groupby('dep_code').size().idxmin()}), max={w.groupby('dep_code').size().max()}")
    print(f"somme des poids par département : min={w.groupby('dep_code').w_area.sum().min():.6f} "
          f"max={w.groupby('dep_code').w_area.sum().max():.6f}")

    OUT.parent.mkdir(parents=True, exist_ok=True)
    w.to_parquet(OUT, index=False)
    print(f"écrit {OUT.relative_to(ROOT)}")


if __name__ == "__main__":
    main()
