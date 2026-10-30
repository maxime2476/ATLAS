# Étape 15 (R) : Q2 de la phase 4 bis, sensibilité du blé tendre à la chaleur, 1959-2025.
# Usage : Rscript R/15_q2_wheat.R
# Spécification de la phase 4 bis.
# Effets fixes département × période de source (1959-1988, 1989-2009, 2010-2025) et année ; WCR par année.
# Sorties : reports/tables/phase4bis_q2_*.csv

source("R/common.R")

RHS_M1 <- c("gdd_0_32_remplissage", "dd_32_remplissage", "prec_printemps", "dd_0_automne", "prec_automne")
FE <- "dep_periode + annee"
FE_VARS <- c("dep_periode", "annee")

p <- load_panel("data/processed/panel_ble_1959.parquet")
p <- subset(p, echantillon_principal)
n0 <- nrow(p)
p <- p[!is.na(p$rendement_q_ha), ]
cat(sprintf("Échantillon principal : %d lignes, %d rendements manquants retirés (années %s) -> %d lignes, %d départements\n",
            n0, n0 - nrow(p), "1959-1967", nrow(p), length(unique(p$dep_code))))
p$periode_source <- cut(p$annee, c(-Inf, 1988, 2009, Inf), labels = c("1959-1988", "1989-2009", "2010-2025"))
p$dep_periode <- paste(p$dep_code, p$periode_source)

one <- function(df, term, rhs, label, fe = FE, fe_vars = FE_VARS) {
  m <- fit(df, rhs, fe = fe)
  s <- summarise_term(m, df, term, rhs, fe_vars = fe_vars, label = label)
  s$n_departements <- length(unique(df$dep_code))
  s$annees <- paste(range(df$annee), collapse = "-")
  s
}

# --- Q2-H1 : beta_2 (dd_32_remplissage) < 0 -----------------------------------
main <- one(p, "dd_32_remplissage", RHS_M1, "B1 principal 1959-2025")
cat("\nQ2-H1 :\n")
print(format(main[, c("terme", "estimation", "effet_pct_par_unite", "p_cluster_dep", "p_conley",
                      "p_wcb_annee_unilateral_gauche", "n", "r2_within")], digits = 3), row.names = FALSE)

# --- Q2-H2 : la pente de chaleur diffère-t-elle entre trois périodes de 22-23 ans ? ----
p$periode_adapt <- cut(p$annee, c(-Inf, 1981, 2003, Inf), labels = c("1959-1981", "1982-2003", "2004-2025"))
for (k in 1:3) p[[paste0("dd32_p", k)]] <- p$dd_32_remplissage * (as.integer(p$periode_adapt) == k)
others <- setdiff(RHS_M1, "dd_32_remplissage")
slopes_rhs <- c(others, "dd32_p1", "dd32_p2", "dd32_p3")
m_sl <- fit(p, slopes_rhs, fe = FE)
slopes <- do.call(rbind, lapply(paste0("dd32_p", 1:3), function(v)
  summarise_term(m_sl, p, v, slopes_rhs, fe_vars = FE_VARS, label = paste("pente", v))))
slopes$n_departements <- length(unique(p$dep_code))
slopes$annees <- "1959-2025"
slopes$periode <- levels(p$periode_adapt)
# Égalité des trois pentes <=> nullité jointe des écarts à la première période (paramétrage équivalent).
p$dd32_d2 <- p$dd32_p2
p$dd32_d3 <- p$dd32_p3
wald <- wcr_wald_pvalue(p, "log_rendement", c("dd32_d2", "dd32_d3"), RHS_M1, FE_VARS, "annee", "surface_ref_ha")
slopes$wald_egalite <- wald$wald
slopes$p_wald_wcr_annee <- wald$p
write.csv(rbind(transform(main, periode = "1959-2025", wald_egalite = NA, p_wald_wcr_annee = NA), slopes),
          "reports/tables/phase4bis_q2_hypotheses.csv", row.names = FALSE)
cat("\nQ2-H2 : pentes par période (descriptif) et test WCR joint d'égalité :\n")
print(format(slopes[, c("periode", "estimation", "effet_pct_par_unite", "p_wcb_annee", "n")], digits = 3), row.names = FALSE)
cat(sprintf("Wald = %.2f ; p WCR (année) = %.4f\n", wald$wald, wald$p))

# --- Robustesses de B1 ----------------------------------------------------------
r1 <- p
regs <- sort(unique(r1$reg_libelle))
trend_vars <- character(0)
for (k in regs[-1]) {      # une région de référence omise : la somme est absorbée par l'effet fixe année
  v <- paste0("tendance_", make.names(k))
  r1[[v]] <- (r1$reg_libelle == k) * (r1$annee - 1990)
  trend_vars <- c(trend_vars, v)
}
r5 <- p
r5$gdd_0_32_remplissage <- r5$gdd_0_30_remplissage
r5$dd_32_remplissage <- r5$dd_30_remplissage  # dans la sortie, terme = « dd_32_remplissage » désigne dd_30
rob <- rbind(
  main,
  one(r1, "dd_32_remplissage", c(RHS_M1, trend_vars), "Q2-R1 + tendances régionales"),
  one(subset(p, annee != 2025), "dd_32_remplissage", RHS_M1, "Q2-R2 sans 2025"),
  one(subset(p, annee >= 1968), "dd_32_remplissage", RHS_M1, "Q2-R3 1968-2025"),
  one(p, "dd_32_remplissage", RHS_M1, "Q2-R4 effet fixe département unique", fe = "dep_code + annee",
      fe_vars = c("dep_code", "annee")),
  one(r5, "dd_32_remplissage", RHS_M1, "Q2-R5 seuil 30 °C")
)
write.csv(rob, "reports/tables/phase4bis_q2_robustesse.csv", row.names = FALSE)
cat("\nRobustesses de B1 (terme dd_32_remplissage ; p WCR unilatérale à gauche) :\n")
print(format(rob[, c("specification", "estimation", "effet_pct_par_unite", "p_wcb_annee_unilateral_gauche",
                     "n", "annees")], digits = 3), row.names = FALSE)

# --- Taille du test Q2-H1 sur ces données ----------------------------------------
one_sided_left <- function(ct) {
  pv <- ct[["Pr(>|t|)"]]
  if (ct[["t value"]] < 0) pv / 2 else 1 - pv / 2
}
years <- sort(unique(p$annee))
field <- tapply(p$dd_32_remplissage, list(p$dep_code, p$annee), identity)
rhs_pl <- c(setdiff(RHS_M1, "dd_32_remplissage"), "x_placebo")
set.seed(123)
R <- 300
rej <- c(cluster_dep = 0, conley_200 = 0, wcr_annee = 0)
for (r in seq_len(R)) {
  perm <- sample(years)
  while (any(perm == years)) perm <- sample(years)
  sim <- p
  sim$x_placebo <- field[cbind(p$dep_code, as.character(perm[match(p$annee, years)]))]
  sim <- sim[!is.na(sim$x_placebo), ]
  m <- fit(sim, rhs_pl, fe = FE)
  p_dep <- one_sided_left(coeftable(m, vcov = ~dep_code)["x_placebo", ])
  v_con <- suppressWarnings(vcov_conley(m, lat = ~lat_centroide, lon = ~lon_centroide, cutoff = CONLEY_KM))
  p_con <- one_sided_left(coeftable(m, vcov = v_con)["x_placebo", ])
  p_wcr <- wcr_pvalue(sim, "log_rendement", "x_placebo", setdiff(rhs_pl, "x_placebo"), FE_VARS, "annee",
                      "surface_ref_ha", B = 399, seed = r)$p_left
  rej <- rej + (c(p_dep, p_con, p_wcr) < 0.05)
}
size <- data.frame(test = "Q2-H1 (unilatéral à gauche)", inference = names(rej), taille_5pct = as.numeric(rej) / R,
                   R = R, B = 399)
write.csv(size, "reports/tables/phase4bis_q2_taille.csv", row.names = FALSE)
cat("\nTaille du test Q2-H1 sous H0 (placebo) :\n")
print(size, row.names = FALSE)
