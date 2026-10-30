# Étape 29 (R) : chaleur moyenne SIM2 / E-OBS, statut de qualité, récolte 2026 ; exploratoires.
#   - chaleur moyenne SIM2 / E-OBS dans A1 ;
#   - pente de la chaleur selon le statut de qualité (38 départements) ;
#   - récolte 2026 (estimations de conjoncture au 1er octobre 2026), pente transversale et A1 sur 2000-2026.
# Prérequis : uv run python scripts/40_recolte_2026.py ; usage : Rscript R/29_q1_chaleur_statut_2026.R
# Sorties : reports/tables/phase7_chaleur_moyenne.csv, phase7_statut_qualite.csv, phase7_recolte_2026.csv

source("R/common.R")

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
pairs_of <- function(lg) {
  irr <- subset(lg, modalite == "irrigue")
  non <- subset(lg, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
  names(non)[3] <- "log_non_irrigue"
  p <- merge(irr, non, by = c("dep_code", "annee"))
  stopifnot(!anyDuplicated(p[, c("dep_code", "annee")]))
  p$ecart_log <- p$log_rendement - p$log_non_irrigue
  p
}
pairs <- pairs_of(long)
stopifnot(nrow(pairs) == 981)
d <- subset(pairs, echantillon_principal)
stopifnot(nrow(d) == 435)
FE <- c("dep_code", "annee")
p_right <- function(df, x, z, B = 9999, seed = 123) {
  1 - wcr_pvalue(df, "ecart_log", x, z, FE, "annee", "surface_ref_ha", B = B, seed = seed)$p_left
}
sd_intra <- function(x, g) sd(x - ave(x, g))

# --- moyenne des deux mesures de chaleur ------------------------------------------------------------------
eobs <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_eobs_ja.parquet"))
d1 <- merge(d, eobs, by = c("dep_code", "annee"))
stopifnot(nrow(d1) == 435, !anyNA(d1$dd_32_ja_eobs))
d1$dd_32_ja_moy <- (d1$dd_32_ja + d1$dd_32_ja_eobs) / 2
b1 <- coef(fit(d1, c("dd_32_ja_moy", "swi_ja"), y = "ecart_log"))[["dd_32_ja_moy"]]
pv1 <- p_right(d1, "dd_32_ja_moy", "swi_ja")
size1 <- placebo_size(d1, "dd_32_ja_moy", "dep_code", "annee",
                      list(wcr = function(sim) p_right(sim, "x_placebo", "swi_ja", B = 399)), R = 300)
sd1 <- sd_intra(d1$dd_32_ja_moy, d1$dep_code)
p1 <- data.frame(specification = "A1, chaleur = moyenne SIM2 et E-OBS", estimation = b1,
                 effet_pct_par_unite = 100 * (exp(b1) - 1), p_wcb_annee_unilateral_droite = pv1,
                 taille_placebo = size1$taille, permutations_distinctes = size1$permutations_distinctes,
                 ecart_type_intra = sd1, effet_pct_un_ecart_type = 100 * (exp(b1 * sd1) - 1),
                 correlation_sim2_eobs = cor(d1$dd_32_ja, d1$dd_32_ja_eobs), n = nrow(d1))
p1$lecture <- ifelse(pv1 < 0.05 & size1$taille <= 0.10, "soutenue avec la mesure moyenne", "non soutenue avec cette mesure")
write.csv(p1, "reports/tables/phase7_chaleur_moyenne.csv", row.names = FALSE)
print(p1, row.names = FALSE)

# --- statut de qualité ------------------------------------------------------------------------------------
pairs$statut2 <- as.numeric(pairs$statut_irrigue == "2")
pairs$dd_x_s2 <- pairs$dd_32_ja * pairs$statut2
pairs$swi_x_s2 <- pairs$swi_ja * pairs$statut2
stopifnot(length(unique(pairs$dep_code[pairs$statut2 == 1])) == 21)
m2 <- fit(pairs, c("dd_32_ja", "dd_x_s2", "swi_ja", "swi_x_s2"), y = "ecart_log")
p_inter <- wcr_pvalue(pairs, "ecart_log", "dd_x_s2", c("dd_32_ja", "swi_ja", "swi_x_s2"), FE, "annee",
                      "surface_ref_ha", B = 9999)$p
s2 <- subset(pairs, statut2 == 1)
b_s2 <- coef(fit(s2, c("dd_32_ja", "swi_ja"), y = "ecart_log"))[["dd_32_ja"]]
p_s2 <- p_right(s2, "dd_32_ja", "swi_ja")
p2 <- data.frame(
  terme = c("pente statut 1 (dans le modèle joint)", "écart de pente statut 2 - statut 1", "pente statut 2 seul (21 dép.)"),
  estimation = c(coef(m2)[["dd_32_ja"]], coef(m2)[["dd_x_s2"]], b_s2),
  p_wcr = c(NA, p_inter, p_s2), sens = c(NA, "bilatéral", "unilatéral à droite"),
  n = c(nrow(pairs), nrow(pairs), nrow(s2)))
p2$effet_pct_par_unite <- 100 * (exp(p2$estimation) - 1)
p2$lecture <- c(NA, ifelse(p_inter < 0.05, "les pentes diffèrent", "pas de différence détectable"), NA)
write.csv(p2, "reports/tables/phase7_statut_qualite.csv", row.names = FALSE)
print(p2, row.names = FALSE)

# --- récolte 2026 (provisoire) --------------------------------------------------------------------------
l26 <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_2026.parquet"))
l26$annee <- 2026
q26 <- pairs_of(l26)
q26 <- subset(q26, echantillon_principal)
stopifnot(nrow(q26) == 17)
# (b) pente transversale : résidu 2026 après effets département et SWI estimés sur 2000-2025.
m25 <- fit(d, c("dd_32_ja", "swi_ja"), y = "ecart_log")
alpha <- fixef(m25)$dep_code
q26$resid <- q26$ecart_log - alpha[q26$dep_code] - coef(m25)[["swi_ja"]] * q26$swi_ja
mb <- lm(resid ~ dd_32_ja, data = q26, weights = surface_ref_ha)
# Écart observé en 2026 par rapport à l'écart moyen de chaque département (comme le contrôle de 2003, § 7.10).
moy <- tapply(d$ecart_log, d$dep_code, mean)
gap_dev26 <- weighted.mean(q26$ecart_log - moy[q26$dep_code], q26$surface_ref_ha)
heat_dev26 <- weighted.mean(q26$dd_32_ja - tapply(d$dd_32_ja, d$dep_code, mean)[q26$dep_code], q26$surface_ref_ha)
# (c) A1 sur 2000-2026.
cols <- intersect(names(d), names(q26))
d27 <- rbind(d[, cols], q26[, cols])
stopifnot(nrow(d27) == 452)
b27 <- coef(fit(d27, c("dd_32_ja", "swi_ja"), y = "ecart_log"))[["dd_32_ja"]]
p27 <- p_right(d27, "dd_32_ja", "swi_ja")
p4 <- data.frame(
  diagnostic = c("pente transversale 2026 (17 dép., sans inférence)", "A1 2000-2026 (2026 provisoire)",
                 "rappel A1 2000-2025"),
  estimation = c(coef(mb)[["dd_32_ja"]], b27, coef(m25)[["dd_32_ja"]]),
  p_wcr_unilateral = c(NA, p27, NA), n = c(nrow(q26), nrow(d27), nrow(d)))
p4$effet_pct_par_unite <- 100 * (exp(p4$estimation) - 1)
p4$chaleur_2026_moyenne <- weighted.mean(q26$dd_32_ja, q26$surface_ref_ha)
p4$ecart_2026_moins_moyenne_dep <- gap_dev26
p4$chaleur_2026_moins_moyenne_dep <- heat_dev26
p4$ecart_predit_par_beta <- coef(m25)[["dd_32_ja"]] * heat_dev26
p4$ecart_median_2026_pct <- 100 * (exp(median(q26$ecart_log)) - 1)
p4$lecture <- c(NA, ifelse(coef(mb)[["dd_32_ja"]] > 0 & p27 < 0.05, "cohérent avec H1", "pas cohérent avec H1"), NA)
write.csv(p4, "reports/tables/phase7_recolte_2026.csv", row.names = FALSE)
print(p4, row.names = FALSE)
