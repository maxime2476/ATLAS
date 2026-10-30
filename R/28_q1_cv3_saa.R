# Étape 28 (R) : taille du jackknife (CV3) et reconduction des rapports SAA ; ajoutées ensuite, descriptives.
#   - taille et puissance du jackknife par année (CV3) pour H1 ;
#   - signatures d'imputation dans la ventilation irrigué / pluvial de la SAA.
# Usage : Rscript R/28_q1_cv3_saa.R ; sorties : reports/tables/phase7_taille_cv3.csv, phase7_signatures_saa.csv

source("R/common.R")

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement", "rendement_q_ha")]
names(non)[3:4] <- c("log_non_irrigue", "rdt_non_irrigue")
pairs <- merge(irr, non, by = c("dep_code", "annee"))
stopifnot(!anyDuplicated(pairs[, c("dep_code", "annee")]), nrow(pairs) == 981)
pairs$ecart_log <- pairs$log_rendement - pairs$log_non_irrigue
names(pairs)[names(pairs) == "rendement_q_ha"] <- "rdt_irrigue"
d <- subset(pairs, echantillon_principal)
stopifnot(nrow(d) == 435)
FE <- c("dep_code", "annee")
years <- sort(unique(d$annee))
field <- tapply(d$dd_32_ja, list(d$dep_code, d$annee), identity)

# p unilatéral à droite du jackknife par année (CV3), comme dans R/22.
p_cv3 <- function(df, x, y) {
  rhs <- c(x, "swi_ja")
  b_hat <- coef(fit(df, rhs, y = y))[[x]]
  yrs <- sort(unique(df$annee))
  b_loo <- vapply(yrs, function(a) coef(fit(subset(df, annee != a), rhs, y = y))[[x]], numeric(1))
  G <- length(yrs)
  se <- sqrt((G - 1) / G * sum((b_loo - b_hat)^2))
  1 - pt(b_hat / se, G - 1)
}
p_wcr <- function(df, x, y, seed) {
  1 - wcr_pvalue(df, y, x, "swi_ja", FE, "annee", "surface_ref_ha", B = 399, seed = seed)$p_left
}
derange <- function(perm) {
  sim <- d
  sim$x_placebo <- field[cbind(d$dep_code, as.character(perm[match(d$annee, years)]))]
  sim[!is.na(sim$x_placebo), ]
}

# --- contrôle sur les données observées (doit redonner p = 0,074, comme R/22) --------------------------------
p_obs <- p_cv3(d, "dd_32_ja", "ecart_log")
g9 <- read.csv("reports/tables/phase7_inferences.csv")
stopifnot(abs(p_obs - g9$p_unilateral_droite[grepl("CV3", g9$specification)]) < 1e-12)

# Taille : les 300 permutations de R/14, rejouées comme dans R/22 (contrôle : taille du WCR enregistrée par R/14).
R <- 300
set.seed(123)
perms14 <- lapply(seq_len(R), function(r) {
  perm <- sample(years)
  while (any(perm == years)) perm <- sample(years)
  perm
})
t0 <- Sys.time()
size <- do.call(rbind, lapply(seq_len(R), function(r) {
  sim <- derange(perms14[[r]])
  data.frame(r = r, cv3 = p_cv3(sim, "x_placebo", "ecart_log") < 0.05,
             wcr = p_wcr(sim, "x_placebo", "ecart_log", seed = r) < 0.05)
}))
size_r14 <- read.csv("reports/tables/phase4bis_q1_taille.csv")
stopifnot(abs(mean(size$wcr) - size_r14$taille_5pct[size_r14$inference == "wcr_annee"]) < 1e-12)
cat(sprintf("taille : CV3 %.3f, WCR %.3f (%.0f s)\n", mean(size$cv3), mean(size$wcr),
            as.numeric(difftime(Sys.time(), t0, units = "secs"))))

# Puissance : permutations de R/19 (graine 123, tirées d'un coup), écart + beta_vrai × placebo.
set.seed(123)
perms19 <- lapply(seq_len(R), function(r) {
  perm <- sample(years)
  while (any(perm == years)) perm <- sample(years)
  perm
})
power <- do.call(rbind, lapply(c(0.008, 0.016), function(bv) {
  rej <- vapply(seq_len(R), function(r) {
    sim <- derange(perms19[[r]])
    sim$y_sim <- sim$ecart_log + bv * sim$x_placebo
    c(cv3 = p_cv3(sim, "x_placebo", "y_sim") < 0.05, wcr = p_wcr(sim, "x_placebo", "y_sim", seed = r) < 0.05)
  }, numeric(2))
  data.frame(beta_vrai = bv, rejet_cv3 = mean(rej["cv3", ]), rejet_wcr = mean(rej["wcr", ]))
}))
pw19 <- read.csv("reports/tables/phase4bis_q1_puissance.csv")
pw19 <- subset(pw19, grepl("^H1 2000-2025", diagnostic) & beta_vrai > 0)
stopifnot(all(abs(power$rejet_wcr - pw19$taux_rejet_5pct[match(power$beta_vrai, pw19$beta_vrai)]) < 1e-12))
print(power, row.names = FALSE)

v1 <- rbind(
  data.frame(diagnostic = "p CV3 observé", beta_vrai = NA, cv3 = p_obs, wcr = NA),
  data.frame(diagnostic = "taille (5 %)", beta_vrai = 0, cv3 = mean(size$cv3), wcr = mean(size$wcr)),
  data.frame(diagnostic = "puissance (5 %)", beta_vrai = power$beta_vrai, cv3 = power$rejet_cv3,
             wcr = power$rejet_wcr))
v1$R <- c(NA, R, R, R)
v1$erreur_monte_carlo_cv3 <- ifelse(is.na(v1$R), NA, sqrt(v1$cv3 * (1 - v1$cv3) / v1$R))
v1$lecture <- c(NA, if (mean(size$cv3) < 0.02) "conservateur" else if (mean(size$cv3) <= 0.08) "calibré" else
  "rejette trop", NA, NA)
write.csv(v1, "reports/tables/phase7_taille_cv3.csv", row.names = FALSE)
print(v1, row.names = FALSE)

# --- signatures d'imputation ---------------------------------------------------------------------------
signatures <- function(df) {
  df <- df[order(df$dep_code, df$annee), ]
  ratio <- round(df$rdt_irrigue / df$rdt_non_irrigue, 2)
  prev_same <- ave(seq_along(ratio), df$dep_code, FUN = function(i) {
    out <- rep(NA, length(i))
    if (length(i) > 1) out[-1] <- ratio[i[-1]] == ratio[i[-length(i)]] & diff(df$annee[i]) == 1
    out
  })
  list(repet = as.logical(prev_same), rond = abs(ratio * 20 - round(ratio * 20)) < 1e-9, df = df)
}
v2_one <- function(df, label) {
  s <- signatures(df)
  obs_rep <- mean(s$repet, na.rm = TRUE)
  obs_rond <- mean(s$rond)
  # Référence : années du rendement pluvial permutées à l'intérieur de chaque département.
  set.seed(123)
  ref <- t(vapply(seq_len(1000), function(k) {
    sim <- s$df
    sim$rdt_non_irrigue <- ave(sim$rdt_non_irrigue, sim$dep_code, FUN = function(v) v[sample.int(length(v))])
    ss <- signatures(sim)
    c(mean(ss$repet, na.rm = TRUE), mean(ss$rond))
  }, numeric(2)))
  # arrondis par mode et par source.
  per <- ifelse(s$df$annee <= 2009, "2000-2009", "2010-2025")
  ent <- function(v) mean(abs(v - round(v)) < 1e-9)
  # rang de la variation 2009-2010 de l'écart parmi les variations annuelles de chaque département.
  rk <- vapply(split(s$df, s$df$dep_code), function(g) {
    g <- g[order(g$annee), ]
    dg <- abs(diff(g$ecart_log))
    names(dg) <- g$annee[-1]
    if (!"2010" %in% names(dg) || !2009 %in% g$annee) return(NA_real_)
    rank(-dg)[["2010"]]
  }, numeric(1))
  data.frame(
    echantillon = label, n_paires = nrow(s$df),
    s1_entiers_irrigue_2000_2009 = ent(s$df$rdt_irrigue[per == "2000-2009"]),
    s1_entiers_irrigue_2010_2025 = ent(s$df$rdt_irrigue[per == "2010-2025"]),
    s1_entiers_pluvial_2000_2009 = ent(s$df$rdt_non_irrigue[per == "2000-2009"]),
    s1_entiers_pluvial_2010_2025 = ent(s$df$rdt_non_irrigue[per == "2010-2025"]),
    s2_repetition = obs_rep, s2_ref_mediane = median(ref[, 1]), s2_ref_p95 = quantile(ref[, 1], 0.95),
    s2_p_permutation = mean(ref[, 1] >= obs_rep),
    s3_ronds = obs_rond, s3_ref_mediane = median(ref[, 2]), s3_ref_p95 = quantile(ref[, 2], 0.95),
    s3_p_permutation = mean(ref[, 2] >= obs_rond),
    s4_depts = sum(!is.na(rk)), s4_part_rang_1 = mean(rk == 1, na.rm = TRUE), s4_attendu = 1 / 25,
    row.names = NULL)
}
v2 <- rbind(v2_one(d, "principal (17)"), v2_one(pairs, "population (38)"))
signature <- v2$s2_repetition[1] > v2$s2_ref_p95[1] | v2$s3_ronds[1] > v2$s3_ref_p95[1]

# signalement (rapport répété ou rond) selon la chaleur, échantillon principal, effets fixes département.
s <- signatures(d)
dd <- s$df
dd$signal <- as.numeric(s$rond | (!is.na(s$repet) & s$repet))
m5 <- feols(signal ~ dd_32_ja | dep_code, data = dd, weights = ~surface_ref_ha)
p5 <- wcr_pvalue(dd, "signal", "dd_32_ja", character(0), "dep_code", "annee", "surface_ref_ha", B = 9999)$p
v2$s5_pente_signal_par_dd <- c(coef(m5)[["dd_32_ja"]], NA)
v2$s5_p_wcr_bilateral <- c(p5, NA)
v2$signature_retenue <- c(signature, NA)

# Conditionnel : départements dont au moins un quart des années sont signalées.
part_dep <- tapply(dd$signal, dd$dep_code, mean)
flag <- names(part_dep)[part_dep >= 0.25]
v2$s6_departements_signales <- c(paste(flag, collapse = " "), NA)
if (signature && length(flag) > 0) {
  d6 <- subset(d, !dep_code %in% flag)
  b6 <- coef(fit(d6, c("dd_32_ja", "swi_ja"), y = "ecart_log"))[["dd_32_ja"]]
  p6 <- 1 - wcr_pvalue(d6, "ecart_log", "dd_32_ja", "swi_ja", FE, "annee", "surface_ref_ha", B = 9999)$p_left
  v2$s6_beta_sans <- c(b6, NA)
  v2$s6_p_unilateral <- c(p6, NA)
  v2$s6_n_departements <- c(length(unique(d6$dep_code)), NA)
} else {
  v2$s6_beta_sans <- NA
  v2$s6_p_unilateral <- NA
  v2$s6_n_departements <- NA
}
write.csv(v2, "reports/tables/phase7_signatures_saa.csv", row.names = FALSE)
print(t(v2))
