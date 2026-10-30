# Étape 20 (R) : vérification Q1-E, A1 avec les degrés-jours > 32 °C de juillet-août recalculés avec E-OBS.
# Usage : Rscript R/20_q1_eobs.R   (après scripts/27_eobs_heat.py)
# Ajoutée ensuite, exploratoire.
# Sorties : reports/tables/phase4bis_q1_eobs.csv, phase4bis_q1_eobs_departement.csv

source("R/common.R")

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
long <- subset(long, echantillon_principal)
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
names(non)[3] <- "log_non_irrigue"
d <- merge(irr, non, by = c("dep_code", "annee"))
d$ecart_log <- d$log_rendement - d$log_non_irrigue
eobs <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_eobs_ja.parquet"))
n0 <- nrow(d)
d <- merge(d, eobs, by = c("dep_code", "annee"))
stopifnot(n0 == 435, nrow(d) == n0, !anyNA(d$dd_32_ja_eobs))

RHS <- c("dd_32_ja", "swi_ja")
qe <- d
qe$dd_32_ja <- qe$dd_32_ja_eobs        # seule la mesure de chaleur change ; swi_ja reste celui de SIM
m <- fit(qe, RHS, y = "ecart_log")
s <- summarise_term(m, qe, "dd_32_ja", RHS, label = "Q1-E chaleur E-OBS (masque maïs 2015-2017)", y = "ecart_log")
s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche

# Lecture descriptive associée : effet d'un écart-type intra-département de chaque mesure.
sd_intra <- function(x, g) sd(x - ave(x, g))
s$sd_intra_eobs <- sd_intra(d$dd_32_ja_eobs, d$dep_code)
s$sd_intra_sim <- sd_intra(d$dd_32_ja, d$dep_code)
s$correlation_eobs_sim <- cor(d$dd_32_ja_eobs, d$dd_32_ja)
s$correlation_intra_eobs_sim <- cor(d$dd_32_ja_eobs - ave(d$dd_32_ja_eobs, d$dep_code),
                                    d$dd_32_ja - ave(d$dd_32_ja, d$dep_code))
write.csv(s, "reports/tables/phase4bis_q1_eobs.csv", row.names = FALSE)
cat(sprintf("Q1-E : beta = %.4f (%.2f %% par °C·jour), p WCR unilatérale = %.4f, n = %d (référence A1 : 0,0158, p = 0,007)\n",
            s$estimation, s$effet_pct_par_unite, s$p_wcb_annee_unilateral_droite, s$n))
cat(sprintf("Écart-type intra-département : E-OBS %.2f, SIM %.2f ; corrélation %.3f (intra : %.3f)\n",
            s$sd_intra_eobs, s$sd_intra_sim, s$correlation_eobs_sim, s$correlation_intra_eobs_sim))

# Table descriptive : exposition moyenne 2000-2025 et en 2003, par département, selon les deux sources.
agg <- aggregate(cbind(dd_32_ja_eobs, dd_32_ja) ~ dep_code, data = d, FUN = mean)
names(agg) <- c("dep_code", "eobs_moyenne", "sim_moyenne")
d03 <- subset(d, annee == 2003)[, c("dep_code", "dd_32_ja_eobs", "dd_32_ja")]
names(d03) <- c("dep_code", "eobs_2003", "sim_2003")
agg <- merge(agg, d03, by = "dep_code", all.x = TRUE)
write.csv(agg, "reports/tables/phase4bis_q1_eobs_departement.csv", row.names = FALSE)
print(format(agg, digits = 3), row.names = FALSE)
