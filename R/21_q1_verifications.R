# Étape 21 (R) : intervalle de β, retrait de départements, humidité du sol, décennies ; ajoutées ensuite.
#   - intervalles de beta par inversion du WCR (A1 maïs ; H1 blé de la phase 4, prévu par sa spécification)
#   - A1 sans chaque département tour à tour ; A1 sans les six départements de relief
#   - A1 sans SWI ; A1 avec le bilan hydrique P - ETP de juillet-août à la place du SWI
#   - différence de pente entre 2000-2009 et 2010-2025 (interaction), avec et sans 2003
# Usage : Rscript R/21_q1_verifications.R ; sorties : reports/tables/phase4bis_q1_verif_*.csv

source("R/common.R")

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
long <- subset(long, echantillon_principal)
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
names(non)[3] <- "log_non_irrigue"
d <- merge(irr, non, by = c("dep_code", "annee"))
d$ecart_log <- d$log_rendement - d$log_non_irrigue
stopifnot(nrow(d) == 435, !anyDuplicated(d[, c("dep_code", "annee")]))
RHS <- c("dd_32_ja", "swi_ja")
FE <- c("dep_code", "annee")

# --- inversion du WCR ---------------------------------------------------------------------------
# p bilatérale du WCR de H0 : beta = b0, obtenue en testant beta = 0 sur y - b0 * x. Même graine pour
# toutes les valeurs de b0 (mêmes tirages de Webb), pour que la fonction p(b0) soit lisse.
p_at <- function(df, y, x, z, b0) {
  df$y_b0 <- df[[y]] - b0 * df[[x]]
  wcr_pvalue(df, "y_b0", x, z, FE, "annee", "surface_ref_ha", B = 9999)$p
}

# Bornes de l'ensemble {b0 : p(b0) > 1 - niveau} : grille, puis bissection entre deux points de grille.
invert <- function(df, y, x, z, b_hat, half_width, step = 0.0005, levels = c(0.90, 0.95), tol = 1e-5) {
  grid <- seq(b_hat - half_width, b_hat + half_width, by = step)
  p <- vapply(grid, function(b0) p_at(df, y, x, z, b0), numeric(1))
  out <- NULL
  for (lev in levels) {
    ok <- p > 1 - lev
    if (!any(ok)) stop("aucune valeur acceptée sur la grille")
    if (ok[1] || ok[length(ok)]) stop("grille trop étroite pour le niveau ", lev)
    i_lo <- min(which(ok)); i_hi <- max(which(ok))
    bisect <- function(a, b) {  # a rejeté, b accepté
      while (abs(b - a) > tol) {
        m <- (a + b) / 2
        if (p_at(df, y, x, z, m) > 1 - lev) b <- m else a <- m
      }
      b
    }
    # Contrôle : l'ensemble accepté doit être un intervalle sur la grille.
    contiguous <- all(ok[i_lo:i_hi])
    out <- rbind(out, data.frame(niveau = lev, borne_inf = bisect(grid[i_lo - 1], grid[i_lo]),
                                 borne_sup = bisect(grid[i_hi + 1], grid[i_hi]), ensemble_contigu = contiguous))
  }
  out
}

t0 <- Sys.time()
b_maize <- coef(fit(d, RHS, y = "ecart_log"))[["dd_32_ja"]]
ci_maize <- cbind(modele = "A1 maïs 2000-2025", terme = "dd_32_ja", estimation = b_maize,
                  invert(d, "ecart_log", "dd_32_ja", "swi_ja", b_maize, half_width = 0.04))

# Échantillon de M1 en phase 4 (R/10) : 83 départements de statut 1, 1 328 observations. Un premier état
# de ce script prenait les 85 départements (robustesse R4) ; corrigé.
wheat <- subset(load_panel(), echantillon_principal)
stopifnot(nrow(wheat) == 1328)
RHS_M1 <- c("gdd_0_32_remplissage", "dd_32_remplissage", "prec_printemps", "dd_0_automne", "prec_automne")
b_wheat <- coef(fit(wheat, RHS_M1))[["dd_32_remplissage"]]
p4 <- read.csv("reports/tables/phase4_principal.csv")
stopifnot(abs(b_wheat - p4$estimation[p4$specification == "M1" & p4$terme == "dd_32_remplissage"]) < 1e-12)
ci_wheat <- cbind(modele = "M1 blé 2010-2025 (H1 phase 4)", terme = "dd_32_remplissage", estimation = b_wheat,
                  invert(wheat, "log_rendement", "dd_32_remplissage", setdiff(RHS_M1, "dd_32_remplissage"),
                         b_wheat, half_width = 0.2, step = 0.001))  # 16 grappes : intervalle large
e1 <- rbind(ci_maize, ci_wheat)
write.csv(e1, "reports/tables/phase4bis_q1_verif_intervalles.csv", row.names = FALSE)
print(e1, row.names = FALSE)
cat(sprintf("Intervalles : %.0f s\n", as.numeric(difftime(Sys.time(), t0, units = "secs"))))

# --- Variantes de A1 (départements, humidité, décennies), WCR via summarise_term ----------------------------------------
one <- function(df, term, rhs, label) {
  s <- summarise_term(fit(df, rhs, y = "ecart_log"), df, term, rhs, label = label, y = "ecart_log")
  s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche
  s$n_departements <- length(unique(df$dep_code))
  s
}

# sans chaque département ; (b) sans les six départements de relief du tableau 5.
deps <- sort(unique(d$dep_code))
e2a <- do.call(rbind, lapply(deps, function(k) {
  s <- one(subset(d, dep_code != k), "dd_32_ja", RHS, paste("A1 sans", k)); s$departement_retire <- k; s
}))
RELIEF <- c("01", "26", "38", "39", "63", "69")
stopifnot(all(RELIEF %in% deps))
e2b <- one(subset(d, !dep_code %in% RELIEF), "dd_32_ja", RHS, "A1 sans les six départements de relief")
e2b$departement_retire <- paste(RELIEF, collapse = " ")
e2 <- rbind(e2a, e2b)
write.csv(e2, "reports/tables/phase4bis_q1_verif_departements.csv", row.names = FALSE)
cat(sprintf("Sans chaque département : beta de %.4f à %.4f ; %d sur %d avec p unilatérale < 0,05\n", min(e2a$estimation),
            max(e2a$estimation), sum(e2a$p_wcb_annee_unilateral_droite < 0.05), nrow(e2a)))
cat(sprintf("Sans les départements de relief : beta = %.4f, p unilatérale = %.4f, %d départements\n", e2b$estimation,
            e2b$p_wcb_annee_unilateral_droite, e2b$n_departements))

# contrôle d'humidité.
d$bilan_hydrique_ja <- d$prec_ja - d$etp_ja
e3 <- rbind(one(d, "dd_32_ja", "dd_32_ja", "A1 sans SWI"),
            one(d, "dd_32_ja", c("dd_32_ja", "bilan_hydrique_ja"), "A1 avec P - ETP à la place du SWI"))
within <- function(v) v - ave(v, d$dep_code)
e3$correlation_intra_dd32_bilan <- cor(within(d$dd_32_ja), within(d$bilan_hydrique_ja))
e3$correlation_intra_dd32_swi <- cor(within(d$dd_32_ja), within(d$swi_ja))
write.csv(e3, "reports/tables/phase4bis_q1_verif_humidite.csv", row.names = FALSE)
print(e3[, c("specification", "estimation", "p_wcb_annee_unilateral_droite", "correlation_intra_dd32_bilan")],
      row.names = FALSE)

# interaction avec la décennie 2000-2009 (son effet principal est absorbé par les effets année).
d$dd32_x_2000s <- d$dd_32_ja * (d$annee <= 2009)
RHS4 <- c("dd_32_ja", "dd32_x_2000s", "swi_ja")
e4 <- rbind(one(d, "dd32_x_2000s", RHS4, "A1 + interaction décennie 2000-2009"),
            one(subset(d, annee != 2003), "dd32_x_2000s", RHS4, "A1 + interaction décennie, sans 2003"))
write.csv(e4, "reports/tables/phase4bis_q1_verif_decennies.csv", row.names = FALSE)
print(e4[, c("specification", "estimation", "p_wcb_annee", "n")], row.names = FALSE)
