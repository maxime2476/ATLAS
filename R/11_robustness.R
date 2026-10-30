# Étape 11 (R) : robustesses R1-R10 (spécification de la phase 4).
# Usage : Rscript R/11_robustness.R
# Sortie : reports/tables/phase4_robustesse.csv (une ligne par spécification, coefficient de chaleur extrême)

source("R/common.R")

panel <- load_panel()
base <- subset(panel, echantillon_principal)
RHS_M1 <- c("gdd_0_32_remplissage", "dd_32_remplissage", "prec_printemps", "dd_0_automne", "prec_automne")
TERM <- "dd_32_remplissage"

# Exposition moyenne 2019 (pondérée) pour exprimer l'effet ; recalculée pour les variantes de seuil.
expo_2019 <- function(df, var = TERM) {
  d <- subset(df, annee == 2019)
  weighted.mean(d[[var]], d$surface_ref_ha)
}

run <- function(label, df, rhs = RHS_M1, term = TERM, fe = "dep_code + annee", fe_vars = c("dep_code", "annee"),
                weighted = TRUE, conley_km = CONLEY_KM) {
  m <- fit(df, rhs, fe = fe, weighted = weighted)
  summarise_term(m, df, term, rhs, fe_vars = fe_vars, weighted = weighted, label = label,
                 conley_km = conley_km, exposure_2019 = expo_2019(df, term))
}

rows <- list()
rows$M1 <- run("M1 (référence)", base)
# L'exposition 2019 qui sert à exprimer l'effet en % reste la moyenne pondérée par la surface, comme ailleurs.
rows$R1 <- run("R1 sans pondération", base, weighted = FALSE)
rows$R2 <- run("R2 sans 84, 30, 48", subset(base, !dep_code %in% c("84", "30", "48")))
rows$R3 <- run("R3 sans 2025", subset(base, annee < 2025))
rows$R4 <- run("R4 85 départements (statuts 1 et 2)", panel)

# R5 : seuil de 30 °C.
rhs30 <- c("gdd_0_30_remplissage", "dd_30_remplissage", "prec_printemps", "dd_0_automne", "prec_automne")
rows$R5 <- run("R5 seuil 30 °C", base, rhs = rhs30, term = "dd_30_remplissage")

# R6 : météo pondérée par la surface (et non par le masque blé).
area <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_harvest_area.parquet"))
area$gdd_0_32_remplissage <- area$dd_0_remplissage - area$dd_32_remplissage
meteo <- c("dd_32_remplissage", "gdd_0_32_remplissage", "prec_printemps", "dd_0_automne", "prec_automne")
r6 <- merge(base[, setdiff(names(base), meteo)], area[, c("dep_code", "annee", meteo)], by = c("dep_code", "annee"))
stopifnot(nrow(r6) == nrow(base))
rows$R6 <- run("R6 météo pondérée par la surface", r6)

# R7 : tendances linéaires par région (une région de référence omise : la somme est absorbée par l'effet fixe année).
r7 <- base
regs <- sort(unique(r7$reg_libelle))
trend_vars <- character(0)
for (k in regs[-1]) {
  v <- paste0("tendance_", make.names(k))
  r7[[v]] <- (r7$reg_libelle == k) * (r7$annee - 2010)
  trend_vars <- c(trend_vars, v)
}
rows$R7 <- run("R7 + tendances régionales", r7, rhs = c(RHS_M1, trend_vars))

# R8 : panel long 1990-2025, effets fixes département × période (rupture de source en 2010) et année.
long <- subset(load_panel("data/processed/panel_ble_long.parquet"), echantillon_principal)
long$dep_periode <- paste(long$dep_code, ifelse(long$annee <= 2009, "avant2010", "depuis2010"))
rows$R8 <- run("R8 panel long 1990-2025", long, fe = "dep_periode + annee", fe_vars = c("dep_periode", "annee"))

# R9 : rayon de Conley de 300 km.
rows$R9 <- run("R9 Conley 300 km", base, conley_km = 300)

# R10 : fenêtre de remplissage mai-juillet (approximation mensuelle).
mjj <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_harvest_wheat_mjj.parquet"))
r10 <- merge(base, mjj, by = c("dep_code", "annee"))
stopifnot(nrow(r10) == nrow(base))
rhs_mjj <- c("gdd_0_32_mjj", "dd_32_mjj", "prec_printemps", "dd_0_automne", "prec_automne")
rows$R10 <- run("R10 fenêtre mai-juillet", r10, rhs = rhs_mjj, term = "dd_32_mjj")

# --- Compléments ------------
extra <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_harvest_wheat_extra.parquet"))
ext <- merge(base, extra, by = c("dep_code", "annee"))
stopifnot(nrow(ext) == nrow(base))
ctrl <- c("prec_printemps", "dd_0_automne", "prec_automne")

# R11 / R12 : fenêtre décalée de -2 / +2 semaines (calcul par demi-mois).
rows$R11 <- run("R11 fenêtre -2 semaines (16 avr.-15 juin)", ext,
                rhs = c("gdd_0_32_m2s", "dd_32_m2s", ctrl), term = "dd_32_m2s")
rows$R12 <- run("R12 fenêtre +2 semaines (16 mai-15 juil.)", ext,
                rhs = c("gdd_0_32_p2s", "dd_32_p2s", ctrl), term = "dd_32_p2s")

# R13 : sans les départements « de montagne » (≥ 25 % du blé dans des mailles à ≥ 600 m).
mont <- as.data.frame(nanoparquet::read_parquet("data/processed/dep_montagne.parquet"))
excl <- mont$dep_code[mont$montagne_r13]
rows$R13 <- run(sprintf("R13 sans montagne (%s)", paste(intersect(excl, base$dep_code), collapse = ", ")),
                subset(base, !dep_code %in% excl))

# R14 : classes de température de 3 °C en mai-juin (jours), référence 15-18 °C omise.
bins <- c("bin_lt9", "bin_9_12", "bin_12_15", "bin_18_21", "bin_21_24", "bin_24_27", "bin_27_30", "bin_30_33", "bin_ge33")
for (b in c("bin_30_33", "bin_ge33")) {
  rows[[paste0("R14_", b)]] <- run(sprintf("R14 classes de température : %s (jours, réf. 15-18 °C)", b), ext,
                                   rhs = c(bins, ctrl), term = b)
}
# Toutes les classes (coefficients seuls, cluster département), pour décrire la forme de la réponse.
m14 <- fit(ext, c(bins, ctrl))
bin_tab <- data.frame(classe = bins, coefficient = coef(m14)[bins],
                      se_cluster_dep = se(m14, vcov = ~dep_code)[bins],
                      se_cluster_annee = se(m14, vcov = ~annee)[bins], row.names = NULL)
write.csv(bin_tab, "reports/tables/phase4_classes_temperature.csv", row.names = FALSE)
cat("R14, toutes les classes (log-rendement par jour passé dans la classe, réf. 15-18 °C) :\n")
print(format(bin_tab, digits = 3), row.names = FALSE)

out <- do.call(rbind, rows)
write.csv(out, "reports/tables/phase4_robustesse.csv", row.names = FALSE)
show <- out[, c("specification", "terme", "estimation", "p_cluster_dep", "p_conley", "conley_non_dp_corrigee", "p_wcb_annee",
                "n_grappes_annee", "effet_pct_par_unite", "effet_pct_exposition_2019", "n")]
print(format(show, digits = 3), row.names = FALSE)
