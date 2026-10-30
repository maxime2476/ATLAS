# Étape 26 (R) : VPD du fourrage, influence des années, corrélation sérielle, multivers ; exploratoires.
#   - VPD sur le maïs fourrage ; influence de chaque année (A1) ;
#   - taille du WCR sous corrélation sérielle (simulation) ; analyse multivers (courbe des spécifications)
# Usage : Rscript R/26_q1_annees_multivers.R ; sorties : reports/tables/phase7_vpd_fourrage.csv, phase7_influence_annees.csv, phase7_correlation_serielle.csv, phase7_multivers.csv

source("R/common.R")
FE <- c("dep_code", "annee")
RHS <- c("dd_32_ja", "swi_ja")
one <- function(df, term, rhs, label, y = "ecart_log", weighted = TRUE) {
  s <- summarise_term(fit(df, rhs, y = y, weighted = weighted), df, term, rhs, label = label, y = y, weighted = weighted)
  s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche
  s$n_departements <- length(unique(df$dep_code))
  s
}

# --- VPD sur le maïs fourrage ------------------------------------------------------------------------
fo <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_fourrage.parquet"))
vf <- as.data.frame(nanoparquet::read_parquet("data/processed/vpd_dep_ja_fourrage.parquet"))
fo <- merge(fo, vf, by = FE)
stopifnot(nrow(fo) == 448)
s1 <- rbind(one(fo, "vpd_ja", c("vpd_ja", "swi_ja"), "fourrage : VPD à la place de dd_32_ja"),
            one(fo, "dd_32_ja", c("dd_32_ja", "vpd_ja", "swi_ja"), "fourrage, ensemble : chaleur"),
            one(fo, "vpd_ja", c("dd_32_ja", "vpd_ja", "swi_ja"), "fourrage, ensemble : VPD"))
s1$correlation_intra_dd32_vpd <- cor(fo$dd_32_ja - ave(fo$dd_32_ja, fo$dep_code), fo$vpd_ja - ave(fo$vpd_ja, fo$dep_code))
write.csv(s1, "reports/tables/phase7_vpd_fourrage.csv", row.names = FALSE)
print(s1[, c("specification", "estimation", "p_wcb_annee", "p_wcb_annee_unilateral_droite", "correlation_intra_dd32_vpd")],
      row.names = FALSE)

# --- Paires du maïs grain : 38 départements (tous statuts) et échantillon principal -------------------
long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c(FE, "log_rendement")]
names(non)[3] <- "log_non_irrigue"
mz <- merge(irr, non, by = FE)
mz$ecart_log <- mz$log_rendement - mz$log_non_irrigue
eobs <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_eobs_ja.parquet"))
m08 <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_harvest_maize2008.parquet"))
names(m08)[3:4] <- c("dd_32_ja_m2008", "swi_ja_m2008")
mz <- merge(mz, eobs, by = FE, all.x = TRUE)
mz <- merge(mz, m08, by = FE, all.x = TRUE)
stopifnot(nrow(mz) == 981)
d <- subset(mz, echantillon_principal)
stopifnot(nrow(d) == 435)

# --- influence de chaque année -----------------------------------------------------------------------
years <- sort(unique(d$annee))
b_all <- coef(fit(d, RHS, y = "ecart_log"))[["dd_32_ja"]]
s2 <- do.call(rbind, lapply(years, function(y) {
  s <- one(subset(d, annee != y), "dd_32_ja", RHS, paste("A1 sans", y))
  s$annee_retiree <- y
  s
}))
s2$variation_beta <- s2$estimation - b_all
write.csv(s2, "reports/tables/phase7_influence_annees.csv", row.names = FALSE)
cat(sprintf("Retrait des années : beta de %.4f à %.4f ; %d sur %d avec p unilatérale < 0,05 ; plus forte variation : sans %d (%+.4f)\n",
            min(s2$estimation), max(s2$estimation), sum(s2$p_wcb_annee_unilateral_droite < 0.05), nrow(s2),
            s2$annee_retiree[which.max(abs(s2$variation_beta))], s2$variation_beta[which.max(abs(s2$variation_beta))]))

# --- taille sous corrélation sérielle ----------------------------------------------------------------
simulate_y <- function(df, rho) {
  deps <- sort(unique(df$dep_code))
  f <- setNames(rnorm(length(years)), years)                 # facteur commun de l'année
  lam <- setNames(rnorm(length(deps), 1, 0.5), deps)         # poids départemental
  e <- numeric(nrow(df))
  for (k in deps) {                                          # AR(1) sur les années successives du département
    idx <- which(df$dep_code == k)
    idx <- idx[order(df$annee[idx])]
    z <- numeric(length(idx))
    z[1] <- rnorm(1)
    for (t in seq_along(idx)[-1]) {
      gap <- df$annee[idx[t]] - df$annee[idx[t - 1]]          # année manquante : rho^écart
      z[t] <- rho^gap * z[t - 1] + sqrt(1 - rho^(2 * gap)) * rnorm(1)
    }
    e[idx] <- z
  }
  f[as.character(df$annee)] * lam[df$dep_code] + e
}
R <- 300
s3 <- do.call(rbind, lapply(c(0, 0.3, 0.6), function(rho) {
  set.seed(123 + round(1000 * rho))
  ys <- replicate(R, simulate_y(d, rho))                     # tirages faits avant les tests
  rej <- vapply(seq_len(R), function(r) {
    sim <- d
    sim$y_sim <- ys[, r]
    p <- 1 - wcr_pvalue(sim, "y_sim", "dd_32_ja", "swi_ja", FE, "annee", "surface_ref_ha", B = 399, seed = r)$p_left
    p < 0.05
  }, logical(1))
  data.frame(rho = rho, taille_5pct = mean(rej), R = R, B = 399, erreur_monte_carlo = sqrt(mean(rej) * (1 - mean(rej)) / R))
}))
write.csv(s3, "reports/tables/phase7_correlation_serielle.csv", row.names = FALSE)
print(s3, row.names = FALSE)

# --- multivers -----------------------------------------------------------------------------------
grid <- expand.grid(mesure = c("masque 2015-2017", "surface"), seuil = c(30, 32), fenetre = c("ja", "juillet"),
                    poids = c(TRUE, FALSE), echantillon = c("17", "38"), sans_2003 = c(FALSE, TRUE),
                    stringsAsFactors = FALSE)
extra <- rbind(expand.grid(mesure = "masque 2008", seuil = 32, fenetre = "ja", poids = c(TRUE, FALSE), echantillon = "17",
                           sans_2003 = c(FALSE, TRUE), stringsAsFactors = FALSE),
               expand.grid(mesure = "E-OBS", seuil = 32, fenetre = "ja", poids = c(TRUE, FALSE), echantillon = c("17", "38"),
                           sans_2003 = c(FALSE, TRUE), stringsAsFactors = FALSE))
grid <- rbind(grid, extra)
stopifnot(nrow(grid) == 76)
s4 <- do.call(rbind, lapply(seq_len(nrow(grid)), function(i) {
  g <- grid[i, ]
  df <- if (g$echantillon == "17") d else mz
  if (g$sans_2003) df <- subset(df, annee != 2003)
  suffix <- if (g$mesure == "surface") "_surf" else ""
  x <- switch(g$mesure, "masque 2008" = "dd_32_ja_m2008", "E-OBS" = "dd_32_ja_eobs",
              paste0("dd_", g$seuil, "_", g$fenetre, suffix))
  h <- switch(g$mesure, "masque 2008" = "swi_ja_m2008", "E-OBS" = "swi_ja", paste0("swi_", g$fenetre, suffix))
  df$chaleur <- df[[x]]
  df$humidite <- df[[h]]
  df <- df[!is.na(df$chaleur) & !is.na(df$humidite), ]
  s <- one(df, "chaleur", c("chaleur", "humidite"), paste("spécification", i), weighted = g$poids)
  cbind(g, s[, c("estimation", "effet_pct_par_unite", "p_wcb_annee_unilateral_droite", "n", "n_departements")])
}))
s4$principale <- with(s4, mesure == "masque 2015-2017" & seuil == 32 & fenetre == "ja" & poids & echantillon == "17" & !sans_2003)
stopifnot(sum(s4$principale) == 1, abs(s4$estimation[s4$principale] - b_all) < 1e-12)
write.csv(s4, "reports/tables/phase7_multivers.csv", row.names = FALSE)
cat(sprintf("Multivers : %d spécifications ; beta > 0 : %d ; p < 0,05 : %d ; médiane %.4f\n", nrow(s4), sum(s4$estimation > 0),
            sum(s4$p_wcb_annee_unilateral_droite < 0.05), median(s4$estimation)))
print(aggregate(cbind(positif = estimation > 0, significatif = p_wcb_annee_unilateral_droite < 0.05) ~ mesure,
                data = s4, FUN = mean))

# La courbe des spécifications est tracée par scripts/39_figures_complements.py (fig10).
