# Étape 12 (R) : diagnostics ajoutés ensuite (rapportés comme tels).
# Usage : Rscript R/12_diagnostics.R
# Sorties : reports/tables/phase4_loyo.csv, reports/tables/phase4_simulation_inference.csv
#
# 1. Leave-one-year-out : beta(dd_32_remplissage) de M1 en retirant chaque récolte à tour de rôle.
# 2. Taille et puissance des trois inférences SUR CES DONNÉES : le régresseur placebo est le champ réel
#    dd_32_remplissage dont on permute les années (même permutation pour tous les départements). Il garde
#    la structure spatiale et la concentration sur quelques années, mais n'a plus de lien avec les rendements.
#    Puissance : on ajoute beta_vrai * x_placebo au log-rendement.

source("R/common.R")

df <- subset(load_panel(), echantillon_principal)
RHS_M1 <- c("gdd_0_32_remplissage", "dd_32_remplissage", "prec_printemps", "dd_0_automne", "prec_automne")
TERM <- "dd_32_remplissage"

# 1. Leave-one-year-out -------------------------------------------------------
loyo <- do.call(rbind, lapply(sort(unique(df$annee)), function(yr) {
  m <- fit(subset(df, annee != yr), RHS_M1)
  ct <- coeftable(m, vcov = ~dep_code)[TERM, ]
  data.frame(annee_retiree = yr, estimation = ct[["Estimate"]], se_cluster_dep = ct[["Std. Error"]])
}))
write.csv(loyo, "reports/tables/phase4_loyo.csv", row.names = FALSE)
cat("Leave-one-year-out (beta dd_32, M1) :\n")
print(format(loyo, digits = 3), row.names = FALSE)

# 2. Simulation de taille et de puissance -------------------------------------
years <- sort(unique(df$annee))
field <- tapply(df$dd_32_remplissage, list(df$dep_code, df$annee), identity)  # départements × années
other <- setdiff(RHS_M1, TERM)  # le vrai dd_32 est retiré : le placebo le remplace
R <- 300
set.seed(123)
res <- list()
for (beta_vrai in c(0, -0.015, -0.03)) {
  rej <- c(cluster_dep = 0, conley_200 = 0, wcr_annee = 0)
  for (r in seq_len(R)) {
    perm <- sample(years)
    while (any(perm == years)) perm <- sample(years)  # aucune année ne garde son propre champ
    x <- field[cbind(df$dep_code, as.character(perm[match(df$annee, years)]))]
    sim <- df
    sim$x_placebo <- x
    sim$log_rendement <- df$log_rendement + beta_vrai * x
    rhs <- c(other, "x_placebo")
    m <- fit(sim, rhs)
    p_dep <- coeftable(m, vcov = ~dep_code)["x_placebo", "Pr(>|t|)"]
    v_con <- suppressWarnings(vcov_conley(m, lat = ~lat_centroide, lon = ~lon_centroide, cutoff = CONLEY_KM))
    p_con <- coeftable(m, vcov = v_con)["x_placebo", "Pr(>|t|)"]
    p_wcr <- wcr_pvalue(sim, "log_rendement", "x_placebo", other, c("dep_code", "annee"), "annee",
                        "surface_ref_ha", B = 399, seed = r)$p
    rej <- rej + (c(p_dep, p_con, p_wcr) < 0.05)  # parenthèses indispensables (priorité de <)
  }
  res[[length(res) + 1]] <- data.frame(beta_vrai = beta_vrai, inference = names(rej),
                                       taux_rejet_5pct = as.numeric(rej) / R, R = R,
                                       # erreur-type de Monte-Carlo d'une taille de 5 % ; elle ne vaut pas
                                       # pour les lignes de puissance (sqrt(p (1 - p) / R) avec p le taux observé)
                                       erreur_monte_carlo = sqrt(0.05 * 0.95 / R))
}
sim_out <- do.call(rbind, res)
write.csv(sim_out, "reports/tables/phase4_simulation_inference.csv", row.names = FALSE)
cat("\nTaux de rejet à 5 % (beta_vrai = 0 : taille ; sinon : puissance), placebo = champ dd_32 à années permutées :\n")
print(format(sim_out, digits = 3), row.names = FALSE)
