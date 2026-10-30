# Étape 22 (R) : analyses complémentaires (hétérogénéité, ensilage, levier, placebos, DML, jackknife) ; exploratoires.
# Prérequis : uv run python scripts/28_complements_python.py preparer
# Usage : Rscript R/22_q1_complements.R ; sorties : reports/tables/phase7_*.csv

source("R/common.R")

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
long <- subset(long, echantillon_principal)
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
names(non)[3] <- "log_non_irrigue"
d <- merge(irr, non, by = c("dep_code", "annee"))
names(d)[names(d) == "log_rendement"] <- "log_irrigue"
d$ecart_log <- d$log_irrigue - d$log_non_irrigue
stopifnot(nrow(d) == 435, !anyDuplicated(d[, c("dep_code", "annee")]))
cov <- as.data.frame(nanoparquet::read_parquet("data/processed/phase7_covariables_dep.parquet"))
d <- merge(d, cov[, c("dep_code", "part_irriguee", "ecart_alt_m", "relief")], by = "dep_code")
stopifnot(nrow(d) == 435)
RHS <- c("dd_32_ja", "swi_ja")
FE <- c("dep_code", "annee")
years <- sort(unique(d$annee))

one <- function(df, term, rhs, label, y = "ecart_log") {
  s <- summarise_term(fit(df, rhs, y = y), df, term, rhs, label = label, y = y)
  s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche
  s$n_departements <- length(unique(df$dep_code))
  s
}

# --- Corrélations entre variables départementales retenues (règle : |r| > 0,7 -> pas dans le même modèle) --------
dep17 <- unique(d[, c("dep_code", "part_irriguee", "ecart_alt_m", "relief")])
cm <- cor(cbind(part_irriguee = dep17$part_irriguee, ecart_alt_m = dep17$ecart_alt_m, relief = as.numeric(dep17$relief)))
write.csv(data.frame(variable = rownames(cm), cm, row.names = NULL), "reports/tables/phase7_correlations_variables.csv",
          row.names = FALSE)
cat("Corrélations entre départements (17) :\n"); print(round(cm, 2))

# --- Interactions avec le relief et avec l'intensité d'irrigation --------------------------------------------------
d$dd32_x_relief <- d$dd_32_ja * d$relief
d$part_irr_c <- d$part_irriguee - mean(unique(d[, c("dep_code", "part_irriguee")])$part_irriguee)
d$dd32_x_part_irr <- d$dd_32_ja * d$part_irr_c
g1 <- one(d, "dd32_x_relief", c(RHS, "dd32_x_relief"), "A1 + chaleur x relief")
g1_base <- one(d, "dd_32_ja", c(RHS, "dd32_x_relief"), "pente hors relief (11 départements)")
g5 <- one(d, "dd32_x_part_irr", c(RHS, "dd32_x_part_irr"), "A1 + chaleur x part irriguée (centrée)")
inter <- rbind(g1, g1_base, g5)
write.csv(inter, "reports/tables/phase7_interactions.csv", row.names = FALSE)
print(inter[, c("specification", "terme", "estimation", "p_wcb_annee", "p_wcb_annee_unilateral_droite")], row.names = FALSE)

# --- ensilage (part du maïs non irrigué récolté en fourrage), 2010-2025 ------------------------------------
fou <- as.data.frame(nanoparquet::read_parquet("data/processed/phase7_fourrage.parquet"))
d2 <- merge(subset(d, annee >= 2010), fou, by = c("dep_code", "annee"))
stopifnot(nrow(d2) == nrow(subset(d, annee >= 2010)), !anyNA(d2$part_fourrage_non_irr))
g2 <- one(d2, "dd_32_ja", RHS, "part fourrage du maïs non irrigué ~ chaleur", y = "part_fourrage_non_irr")
g2$moyenne_part <- weighted.mean(d2$part_fourrage_non_irr, d2$surface_ref_ha)
g2_ctrl <- NULL
if (g2$p_wcb_annee_unilateral_droite < 0.05) {
  g2_ctrl <- one(d2, "dd_32_ja", c(RHS, "part_fourrage_non_irr"), "A1 2010-2025 + part fourrage")
  g2_ctrl$moyenne_part <- NA
}
write.csv(rbind(g2, g2_ctrl), "reports/tables/phase7_ensilage.csv", row.names = FALSE)
cat(sprintf("Ensilage : pente %.5f par °C·jour (moyenne %.2f), p unilatérale = %.4f\n", g2$estimation, g2$moyenne_part,
            g2$p_wcb_annee_unilateral_droite))

# --- levier partiel par année ; N_eff sur 2000-2025 et 2000-2009 ---------------------------------------
leverage <- function(df) {
  w <- df$surface_ref_ha
  dm <- fixest::demean(as.matrix(df[, c("dd_32_ja", "swi_ja")]), df[, FE], weights = w)
  xt <- dm[, 1] - dm[, 2] * sum(w * dm[, 1] * dm[, 2]) / sum(w * dm[, 2]^2)
  s <- tapply(w * xt^2, df$annee, sum)
  s / sum(s)
}
lev_all <- leverage(d); lev_early <- leverage(subset(d, annee <= 2009))
lev <- rbind(data.frame(periode = "2000-2025", annee = as.integer(names(lev_all)), part_sxx = as.numeric(lev_all)),
             data.frame(periode = "2000-2009", annee = as.integer(names(lev_early)), part_sxx = as.numeric(lev_early)))
lev$n_eff_periode <- ave(lev$part_sxx, lev$periode, FUN = function(s) 1 / sum(s^2))
write.csv(lev, "reports/tables/phase7_levier_annees.csv", row.names = FALSE)
cat(sprintf("Levier : part de 2003 = %.2f (2000-2025, N_eff %.1f) ; %.2f (2000-2009, N_eff %.1f)\n",
            lev_all[["2003"]], 1 / sum(lev_all^2), lev_early[["2003"]], 1 / sum(lev_early^2)))

# --- placebos -----------------------------------------------------------------
field <- tapply(d$dd_32_ja, list(d$dep_code, d$annee), identity)
R <- 300
p_wcr_right <- function(sim, y = "ecart_log", seed) {
  1 - wcr_pvalue(sim, y, "x_placebo", "swi_ja", FE, "annee", "surface_ref_ha", B = 399, seed = seed)$p_left
}
p_wcr_left <- function(sim, y, seed) {
  wcr_pvalue(sim, y, "x_placebo", "swi_ja", FE, "annee", "surface_ref_ha", B = 399, seed = seed)$p_left
}

# (b) et (c) : permutations de R/14 rejouées. wcr_pvalue() ne modifiant pas l'état du générateur, R/14 tire ses
# permutations à la suite après set.seed(123) : on refait cette séquence (contrôlée ci-dessous par la taille
# du WCR enregistrée par R/14).
set.seed(123)
perms <- vector("list", R)
for (r in seq_len(R)) {
  perm <- sample(years)
  while (any(perm == years)) perm <- sample(years)
  perms[[r]] <- perm
}
derange <- function(perm) {
  sim <- d
  sim$x_placebo <- field[cbind(d$dep_code, as.character(perm[match(d$annee, years)]))]
  sim[!is.na(sim$x_placebo), ]
}
t0 <- Sys.time()
pl <- do.call(rbind, lapply(seq_len(R), function(r) {
  sim <- derange(perms[[r]])
  m <- fit(sim, c("swi_ja", "x_placebo"), y = "ecart_log")
  conley_fixed <- FALSE
  withCallingHandlers(vcov_conley(m, lat = ~lat_centroide, lon = ~lon_centroide, cutoff = CONLEY_KM),
                      warning = function(w) {
                        if (grepl("positive definite", conditionMessage(w))) conley_fixed <<- TRUE
                        invokeRestart("muffleWarning")
                      })
  data.frame(r = r, annee_recoit_2003 = years[perms[[r]] == 2003],
             rejet_wcr = p_wcr_right(sim, seed = r) < 0.05, conley_corrigee = conley_fixed,
             rejet_h2b = p_wcr_left(sim, "log_non_irrigue", seed = r) < 0.05,   # taille de H2b
             rejet_h2c = p_wcr_left(sim, "log_irrigue", seed = r) < 0.05)
}))
cat(sprintf("Placebos par dérangement : %.0f s\n", as.numeric(difftime(Sys.time(), t0, units = "secs"))))
size_r14 <- read.csv("reports/tables/phase4bis_q1_taille.csv")
stopifnot(abs(mean(pl$rejet_wcr) - size_r14$taille_5pct[size_r14$inference == "wcr_annee"]) < 1e-12)  # rejoue R/14
write.csv(pl, "reports/tables/phase7_placebo_derangement.csv", row.names = FALSE)

# (a) placebo intra-année : chaque année, valeurs de dd_32_ja permutées au hasard entre départements.
set.seed(123)
within_perms <- lapply(seq_len(R), function(r) lapply(years, function(y) sample(which(d$annee == y))))
pa <- vapply(seq_len(R), function(r) {
  sim <- d
  sim$x_placebo <- NA_real_
  for (k in seq_along(years)) {
    idx <- which(d$annee == years[k])
    sim$x_placebo[idx] <- d$dd_32_ja[within_perms[[r]][[k]]]
  }
  p_wcr_right(sim, seed = r)
}, numeric(1))
sizes <- data.frame(
  diagnostic = c("H1, placebo intra-année", "H2b (non irrigué), dérangement", "H2c (irrigué), dérangement",
                 "rappel H1, dérangement (R/14)", "matrices de Conley corrigées (dérangement)"),
  taux = c(mean(pa < 0.05), mean(pl$rejet_h2b), mean(pl$rejet_h2c), mean(pl$rejet_wcr), mean(pl$conley_corrigee)),
  R = R)
sizes$erreur_monte_carlo <- sqrt(sizes$taux * (1 - sizes$taux) / R)
write.csv(sizes, "reports/tables/phase7_tailles.csv", row.names = FALSE)
print(sizes, row.names = FALSE)
by03 <- aggregate(rejet_wcr ~ annee_recoit_2003, data = pl, FUN = function(x) c(n = length(x), taux = mean(x)))
by03 <- data.frame(annee_recoit_2003 = by03$annee_recoit_2003, n = by03$rejet_wcr[, "n"], taux_rejet = by03$rejet_wcr[, "taux"])
write.csv(by03, "reports/tables/phase7_placebo_par_annee_2003.csv", row.names = FALSE)

# --- pentes départementales et rétrécissement empirique bayésien -----------------------------------------
# Les 17 pentes sont corrélées (effets fixes année et swi_ja communs, chaleur corrélée entre départements) :
# version principale avec leur covariance complète regroupée par année (CR1) ; version diagonale
# (erreurs-types hétéroscédastiques, DerSimonian-Laird usuel) conservée pour comparaison.
m6 <- feols(ecart_log ~ dd_32_ja:dep_code + swi_ja | dep_code + annee, data = d, weights = ~surface_ref_ha,
            vcov = "hetero")
keep <- grepl("^dd_32_ja:dep_code", names(coef(m6)))
b <- coef(m6)[keep]
V_het <- vcov(m6, vcov = "hetero")[keep, keep]
V_an <- vcov(m6, cluster = ~annee)[keep, keep]
deps <- sub("dd_32_ja:dep_code", "", names(b))
eb <- eb_moments(b, V_an)
eb_diag <- eb_moments(b, diag(diag(V_het)))
g6 <- data.frame(dep_code = deps, pente = b, se_hetero = sqrt(diag(V_het)), se_annee = sqrt(diag(V_an)),
                 pente_retrecie = eb$shrunk, pente_retrecie_diag = eb_diag$shrunk)
g6 <- merge(g6, cov[, c("dep_code", "part_irriguee", "ecart_alt_m", "relief")], by = "dep_code")
g6$tau <- sqrt(eb$tau2); g6$mu <- eb$mu; g6$Q <- eb$Q; g6$p_Q <- eb$p_Q
g6$tau_diag <- sqrt(eb_diag$tau2); g6$mu_diag <- eb_diag$mu; g6$Q_diag <- eb_diag$Q; g6$p_Q_diag <- eb_diag$p_Q
g6$cor_retrecie_part_irr <- cor(g6$pente_retrecie, g6$part_irriguee)
g6$cor_retrecie_ecart_alt <- cor(g6$pente_retrecie, g6$ecart_alt_m)
g6$cor_brute_ecart_alt <- cor(g6$pente, g6$ecart_alt_m)
g6$cor_mediane_pentes_annee <- median(cov2cor(V_an)[upper.tri(V_an)])
write.csv(g6, "reports/tables/phase7_pentes_departements.csv", row.names = FALSE)
cat(sprintf("Pentes rétrécies (covariance par année) : mu = %.4f, tau = %.4f, Q = %.1f (p = %.3f) ; diagonale : tau = %.4f, p = %.3f\n",
            eb$mu, sqrt(eb$tau2), eb$Q, eb$p_Q, sqrt(eb_diag$tau2), eb_diag$p_Q))

# Test d'homogénéité calibré par bootstrap sauvage restreint par année.
# Reparamétrage : pente commune + 16 écarts au département de référence ; H0 (écarts nuls) = modèle A1.
dep_levels <- sort(unique(d$dep_code))
hx <- paste0("hx_", dep_levels[-1])
add_gaps <- function(df, x) {
  for (k in dep_levels[-1]) df[[paste0("hx_", k)]] <- df[[x]] * (df$dep_code == k)
  df
}
homog_wcr <- function(df, x, B, seed = 123) {
  wcr_wald_pvalue(add_gaps(df, x), "ecart_log", hx, c(x, "swi_ja"), FE, "annee", "surface_ref_ha", B = B, seed = seed)
}
homog_chi2 <- function(df, x) {   # χ² usuel : Q généralisé avec la covariance CR1 par année
  m <- feols(as.formula(paste0("ecart_log ~ ", x, ":dep_code + swi_ja | dep_code + annee")), data = df,
             weights = ~surface_ref_ha)
  k <- grepl(paste0("^", x, ":dep_code"), names(coef(m)))
  eb_moments(coef(m)[k], vcov(m, cluster = ~annee)[k, k])$p_Q
}
hw <- homog_wcr(d, "dd_32_ja", B = 9999)
hsize <- placebo_size(d, "dd_32_ja", "dep_code", "annee",
                      list(wcr = function(sim) homog_wcr(sim, "x_placebo", B = 399)$p,
                           chi2 = function(sim) homog_chi2(sim, "x_placebo")), R = 300)
homog <- data.frame(test = c("Wald WCR par année (9 999 tirages)", "chi2 à 16 ddl, covariance CR1 par année"),
                    statistique = c(hw$wald, eb$Q), p = c(hw$p, eb$p_Q),
                    taille_placebo = hsize$taille[match(c("wcr", "chi2"), hsize$test)], R = 300,
                    erreur_monte_carlo = sqrt(hsize$taille[match(c("wcr", "chi2"), hsize$test)] *
                                                (1 - hsize$taille[match(c("wcr", "chi2"), hsize$test)]) / 300))
homog$lecture <- c(if (homog$taille_placebo[1] > 0.10) "non interprétable (taille > 10 %)" else
                     if (hw$p < 0.05) "hétérogénéité des pentes détectée" else "pas d'hétérogénéité détectable",
                   "référence (chi2)")
write.csv(homog, "reports/tables/phase7_pentes_homogeneite.csv", row.names = FALSE)
print(homog, row.names = FALSE)

# --- inférence WCR du DML (résidus de scripts/28) -------------------------------------------------------
# 50 découpages des années en plis : estimation et p-valeur par découpage, puis médianes (Chernozhukov et al.
# 2018, § 3.4). Le point rapporté est celui que teste le WCR : résidus régressés avec effets fixes département
# et année (re-projection) ; la version sans effets fixes est gardée en colonne (écart d'environ 0,5 %).
dml_all <- as.data.frame(nanoparquet::read_parquet("data/processed/phase7_dml_residus.parquet"))
g8_rep <- do.call(rbind, lapply(split(dml_all, dml_all$repetition), function(dml) {
  bt <- wcr_pvalue(dml, "y_res", "d_res", character(0), FE, "annee", "surface_ref_ha", B = 9999)
  data.frame(repetition = dml$repetition[1],
             estimation = coef(feols(y_res ~ d_res | dep_code + annee, data = dml, weights = ~surface_ref_ha))[["d_res"]],
             estimation_sans_ef = sum(dml$surface_ref_ha * dml$d_res * dml$y_res) / sum(dml$surface_ref_ha * dml$d_res^2),
             p_wcb_annee = bt$p, p_wcb_annee_unilateral_droite = 1 - bt$p_left)
}))
write.csv(g8_rep, "reports/tables/phase7_dml_repetitions.csv", row.names = FALSE)
# variante Mundlak (moyennes annuelles retirées dans les plis, moyennes départementales en variables).
mund_all <- as.data.frame(nanoparquet::read_parquet("data/processed/phase7_dml_mundlak_residus.parquet"))
mund_rep <- do.call(rbind, lapply(split(mund_all, mund_all$repetition), function(dml) {
  bt <- wcr_pvalue(dml, "y_res", "d_res", character(0), "annee", "annee", "surface_ref_ha", B = 9999)
  data.frame(repetition = dml$repetition[1],
             estimation = coef(feols(y_res ~ d_res | annee, data = dml, weights = ~surface_ref_ha))[["d_res"]],
             p_wcb_annee_unilateral_droite = 1 - bt$p_left)
}))
write.csv(mund_rep, "reports/tables/phase7_dml_mundlak_repetitions.csv", row.names = FALSE)
# deux fois la médiane des p-valeurs est une p-valeur valide (Meinshausen et al. 2009) ; la médiane seule ne l'est pas.
g8 <- data.frame(specification = sprintf(c("DML (forêts aléatoires, 5 plis par années, médiane de %d découpages)",
                                           "DML, variante Mundlak (médiane de %d découpages)"), nrow(g8_rep)),
                 estimation = c(median(g8_rep$estimation), median(mund_rep$estimation)),
                 p_wcb_annee = c(median(g8_rep$p_wcb_annee), NA),
                 p_wcb_annee_unilateral_droite = c(median(g8_rep$p_wcb_annee_unilateral_droite),
                                                   median(mund_rep$p_wcb_annee_unilateral_droite)),
                 p_unilateral_droite_2x_mediane = pmin(1, 2 * c(median(g8_rep$p_wcb_annee_unilateral_droite),
                                                                median(mund_rep$p_wcb_annee_unilateral_droite))),
                 estimation_min = c(min(g8_rep$estimation), min(mund_rep$estimation)),
                 estimation_max = c(max(g8_rep$estimation), max(mund_rep$estimation)),
                 part_p_unilateral_inf_005 = c(mean(g8_rep$p_wcb_annee_unilateral_droite < 0.05),
                                               mean(mund_rep$p_wcb_annee_unilateral_droite < 0.05)),
                 n = nrow(dml_all) / nrow(g8_rep))

# --- Jackknife par année (CV3) et inférence par randomisation ------------------------------------
b_hat <- coef(fit(d, RHS, y = "ecart_log"))[["dd_32_ja"]]
b_loo <- vapply(years, function(y) coef(fit(subset(d, annee != y), RHS, y = "ecart_log"))[["dd_32_ja"]], numeric(1))
G <- length(years)
se_cv3 <- sqrt((G - 1) / G * sum((b_loo - b_hat)^2))
set.seed(123)
b_ri <- vapply(seq_len(5000), function(i) {
  perm <- sample(years)
  while (any(perm == years)) perm <- sample(years)
  coef(fit(derange(perm), c("swi_ja", "x_placebo"), y = "ecart_log"))[["x_placebo"]]
}, numeric(1))
g9 <- data.frame(
  specification = c("jackknife par année (CV3)", "randomisation (5 000 dérangements, stat. beta)"),
  estimation = b_hat, se = c(se_cv3, NA),
  p_unilateral_droite = c(1 - pt(b_hat / se_cv3, G - 1), mean(b_ri >= b_hat)), n = nrow(d))
write.csv(merge(g8, g9, all = TRUE), "reports/tables/phase7_inferences.csv", row.names = FALSE)
print(rbind(g8[, c("specification", "estimation", "p_wcb_annee_unilateral_droite")],
            setNames(g9[, c("specification", "estimation", "p_unilateral_droite")], names(g8)[c(1, 2, 4)])), row.names = FALSE)
