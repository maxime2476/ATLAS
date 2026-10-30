# Étape 19 (R) : puissance du test de H1 et taille / puissance de la réplication 2000-2009.
# Diagnostics ajoutés ensuite. Même placebo que la taille de H1 dans R/14 : champ réel dd_32_ja à années permutées
# (dérangement), WCR par année unilatéral à droite, 5 %, R = 300, B = 399.
# Usage : Rscript R/19_q1_power_size.R ; sortie : reports/tables/phase4bis_q1_puissance.csv

source("R/common.R")

# Paires de l'échantillon principal (même construction que R/14).
long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
names(non)[3] <- "log_non_irrigue"
mz <- merge(irr, non, by = c("dep_code", "annee"))
stopifnot(!anyDuplicated(mz[, c("dep_code", "annee")]))
mz$ecart_log <- mz$log_rendement - mz$log_non_irrigue
d <- subset(mz, echantillon_principal)
stopifnot(nrow(d) == 435)

# Taux de rejet du WCR unilatéral à droite quand on ajoute beta_vrai × placebo à l'écart.
rejection <- function(df, beta_vrai, R = 300, B = 399, seed = 123) {
  years <- sort(unique(df$annee))
  field <- tapply(df$dd_32_ja, list(df$dep_code, df$annee), identity)
  set.seed(seed)
  perms <- lapply(seq_len(R), function(r) {   # permutations tirées avant les tests (indépendantes des tests)
    perm <- sample(years)
    while (any(perm == years)) perm <- sample(years)
    perm
  })
  rej <- 0
  for (r in seq_len(R)) {
    sim <- df
    sim$x_placebo <- field[cbind(df$dep_code, as.character(perms[[r]][match(df$annee, years)]))]
    sim <- sim[!is.na(sim$x_placebo), ]       # paires absentes l'année permutée
    sim$y_sim <- sim$ecart_log + beta_vrai * sim$x_placebo
    p <- 1 - wcr_pvalue(sim, "y_sim", "x_placebo", "swi_ja", c("dep_code", "annee"), "annee",
                        "surface_ref_ha", B = B, seed = r)$p_left
    rej <- rej + (p < 0.05)
  }
  rej / R
}

R <- 300
cases <- list(
  list("H1 2000-2025", d, 0), list("H1 2000-2025", d, 0.008), list("H1 2000-2025", d, 0.016),
  list("réplication 2000-2009", subset(d, annee <= 2009), 0),
  list("réplication 2000-2009", subset(d, annee <= 2009), 0.011)
)
out <- do.call(rbind, lapply(cases, function(k) {
  t0 <- Sys.time()
  rate <- rejection(k[[2]], k[[3]], R = R)
  cat(sprintf("%s, beta = %.3f : rejet %.3f (%.0f s)\n", k[[1]], k[[3]], rate,
              as.numeric(difftime(Sys.time(), t0, units = "secs"))))
  data.frame(diagnostic = k[[1]], beta_vrai = k[[3]], taux_rejet_5pct = rate, R = R, B = 399,
             n_grappes_annee = length(unique(k[[2]]$annee)),
             # erreur-type de Monte-Carlo du taux observé
             erreur_monte_carlo = sqrt(rate * (1 - rate) / R))
}))
write.csv(out, "reports/tables/phase4bis_q1_puissance.csv", row.names = FALSE)
print(out, row.names = FALSE)
