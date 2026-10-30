# Étape 17 (R) : robustesse Q1-R9, A1 avec la météo pondérée par le masque maïs 2008 (RPG 1.0, îlots).
# Usage : Rscript R/17_q1_mask2008.R   (après scripts/25_build_maize_mask_2008.py)
# Ajoutée ensuite.
# Sorties : reports/tables/phase4bis_q1_r9_masque2008.csv, phase4bis_q1_mesures_departement.csv

source("R/common.R")

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
long <- subset(long, echantillon_principal)
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
names(non)[3] <- "log_non_irrigue"
d <- merge(irr, non, by = c("dep_code", "annee"))
d$ecart_log <- d$log_rendement - d$log_non_irrigue
m08 <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_harvest_maize2008.parquet"))
names(m08)[3:4] <- c("dd_32_ja_m2008", "swi_ja_m2008")
n0 <- nrow(d)
d <- merge(d, m08, by = c("dep_code", "annee"))
stopifnot(nrow(d) == n0, !anyNA(d$dd_32_ja_m2008))

RHS <- c("dd_32_ja", "swi_ja")
r9 <- d
r9$dd_32_ja <- r9$dd_32_ja_m2008
r9$swi_ja <- r9$swi_ja_m2008
m <- fit(r9, RHS, y = "ecart_log")
s <- summarise_term(m, r9, "dd_32_ja", RHS, label = "Q1-R9 masque maïs 2008 (îlots RPG 1.0)", y = "ecart_log")
s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche
write.csv(s, "reports/tables/phase4bis_q1_r9_masque2008.csv", row.names = FALSE)
cat(sprintf("Q1-R9 : beta = %.4f (%.2f %% par °C·jour), p WCR unilatérale = %.4f, n = %d (référence A1 : 0,0158, p = 0,007)\n",
            s$estimation, s$effet_pct_par_unite, s$p_wcb_annee_unilateral_droite, s$n))

# Table descriptive : exposition moyenne 2000-2025 par département selon les trois mesures.
agg <- aggregate(cbind(dd_32_ja_m2008, dd_32_ja, dd_32_ja_surf) ~ dep_code, data = d, FUN = mean)
names(agg) <- c("dep_code", "masque_2008", "masque_2015_2017", "ponderation_surfacique")
d03 <- subset(d, annee == 2003)[, c("dep_code", "dd_32_ja_m2008", "dd_32_ja", "dd_32_ja_surf")]
names(d03) <- c("dep_code", "masque_2008_2003", "masque_2015_2017_2003", "ponderation_surfacique_2003")
agg <- merge(agg, d03, by = "dep_code", all.x = TRUE)
agg$ecart_surface_moins_masque_2003 <- agg$ponderation_surfacique_2003 - agg$masque_2015_2017_2003
write.csv(agg, "reports/tables/phase4bis_q1_mesures_departement.csv", row.names = FALSE)
print(format(agg[order(agg$ecart_surface_moins_masque_2003), ], digits = 3), row.names = FALSE)
cat(sprintf("Corrélation des expositions (toutes années) : masque 2008 / 2015-2017 = %.3f ; surface / 2015-2017 = %.3f\n",
            cor(d$dd_32_ja_m2008, d$dd_32_ja), cor(d$dd_32_ja_surf, d$dd_32_ja)))
