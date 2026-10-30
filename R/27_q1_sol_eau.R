# Étape 27 (R) : eau d'irrigation (volumes, valeur du m³) ; exploratoires.
#   - les volumes prélevés pour l'irrigation suivent-ils la chaleur ? (BNPE, scripts/36_volumes_irrigation.py)
#   - valeur apparente du m³ dans les 6 départements où le maïs grain domine l'irrigation
# Usage : Rscript R/27_q1_sol_eau.R ; sorties : reports/tables/phase7_volumes.csv, phase7_valeur_m3*.csv

source("R/common.R")
FE <- c("dep_code", "annee")
RHS <- c("dd_32_ja", "swi_ja")
one <- function(df, term, rhs, label, y = "ecart_log", pct = TRUE) {
  s <- summarise_term(fit(df, rhs, y = y), df, term, rhs, label = label, y = y, pct_meaningful = pct)
  s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche
  s$n_departements <- length(unique(df$dep_code))
  s
}

# Paires irrigué / non irrigué : 38 départements, puis l'échantillon principal (17).
long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c(FE, "log_rendement", "rendement_q_ha")]
names(non)[3:4] <- c("log_non_irrigue", "rendement_non_irrigue")
all38 <- merge(irr, non, by = FE)
all38$ecart_log <- all38$log_rendement - all38$log_non_irrigue
vpd <- as.data.frame(nanoparquet::read_parquet("data/processed/vpd_dep_ja.parquet"))
all38 <- merge(all38, vpd, by = FE)
stopifnot(nrow(all38) == 981)
d <- subset(all38, echantillon_principal)
stopifnot(nrow(d) == 435, length(unique(d$dep_code)) == 17)

dep17 <- unique(d["dep_code"])   # les 17 départements de l'échantillon principal

# --- volumes d'irrigation et chaleur, 2012-2023 ----------------------------------------------------------
vol <- as.data.frame(nanoparquet::read_parquet("data/processed/bnpe_irr_dep_annee.parquet"))
w <- merge(subset(d, annee >= 2012 & annee <= 2023), vol, by = FE)
stopifnot(nrow(w) == nrow(subset(d, annee >= 2012 & annee <= 2023)))
w$log_volume <- log(w$volume_m3)
w1 <- rbind(one(w, "dd_32_ja", RHS, "log volume BNPE ~ chaleur", y = "log_volume"),
            one(w, "vpd_ja", c("vpd_ja", "swi_ja"), "log volume BNPE ~ VPD", y = "log_volume"),
            one(w, "swi_ja", RHS, "log volume BNPE : SWI", y = "log_volume"))
w1$part_volume_mesure_mediane <- median(w$part_volume_mesure)
write.csv(w1, "reports/tables/phase7_volumes.csv", row.names = FALSE)
print(w1[, c("specification", "estimation", "effet_pct_par_unite", "p_wcb_annee", "p_wcb_annee_unilateral_droite", "n")],
      row.names = FALSE)

# --- valeur apparente du m³ (6 départements où le maïs grain domine l'irrigation en 2020) ----------------
ra <- as.data.frame(nanoparquet::read_parquet("data/processed/ra_irrigation_dep.parquet"))
s20 <- setNames(subset(ra, annee_ra == 2020)[, c("dep_code", "part_mais_grain_irrigue")], c("dep_code", "part_2020"))
s10 <- setNames(subset(ra, annee_ra == 2010)[, c("dep_code", "part_mais_grain_irrigue")], c("dep_code", "part_2010"))
deps6 <- sort(subset(s20, dep_code %in% dep17$dep_code & part_2020 > 0.5)$dep_code)
stopifnot(identical(deps6, c("01", "03", "18", "63", "67", "68")))      # liste fixe des six départements
price <- as.data.frame(nanoparquet::read_parquet("data/processed/prix_mais.parquet"))
v <- merge(merge(merge(subset(w, dep_code %in% deps6), s20, by = "dep_code"), s10, by = "dep_code"), price, by = "annee")
v$gain_q_ha <- v$rendement_q_ha - v$rendement_non_irrigue
dose <- function(part) v$volume_m3 * part / v$surface_ha                  # m³ par ha de maïs grain irrigué
v$dose_m3_ha <- dose(v$part_2020)
v$dose_m3_ha_2010 <- dose(v$part_2010)
v$plausible <- v$dose_m3_ha >= 500 & v$dose_m3_ha <= 3000                 # règle fixée d'avance
v$kg_par_m3 <- ifelse(v$plausible, 100 * v$gain_q_ha / v$dose_m3_ha, NA)
v$eur_par_m3 <- ifelse(v$plausible, v$gain_q_ha * v$prix_eur_q / v$dose_m3_ha, NA)
v$eur_par_m3_part_2010 <- with(v, ifelse(dose_m3_ha_2010 >= 500 & dose_m3_ha_2010 <= 3000,
                                         gain_q_ha * prix_eur_q / dose_m3_ha_2010, NA))
write.csv(v[order(v$dep_code, v$annee), c("dep_code", "annee", "volume_m3", "part_2020", "part_2010", "surface_ha",
                                           "dose_m3_ha", "dose_m3_ha_2010", "plausible", "gain_q_ha", "prix_eur_q",
                                           "kg_par_m3", "eur_par_m3", "eur_par_m3_part_2010", "dd_32_ja")],
          "reports/tables/phase7_valeur_m3_departement_annee.csv", row.names = FALSE)
med <- function(x) median(x, na.rm = TRUE)
# Médianes de la dose et de l'écart sur les seules années plausibles, comme les kg/m³ et €/m³ : les quatre
# chiffres décrivent alors le même échantillon. La médiane de la dose sur toutes les années (exclues comprises)
# reste fournie à part : c'est elle qui montre pourquoi la règle écarte des années (ex. Puy-de-Dôme).
# La colonne €/m³ « part 2010 » a sa propre règle de plausibilité (dose calculée avec la part 2010).
summarise_w2 <- function(g, dep_code, part_2020) {
  p <- g[g$plausible, ]
  data.frame(dep_code = dep_code, annees = nrow(g), exclues = sum(!g$plausible), part_2020 = part_2020,
             dose_mediane_m3_ha = med(p$dose_m3_ha), dose_mediane_toutes_m3_ha = med(g$dose_m3_ha),
             gain_median_q_ha = med(p$gain_q_ha), kg_par_m3_median = med(g$kg_par_m3),
             eur_par_m3_median = med(g$eur_par_m3), eur_par_m3_median_part_2010 = med(g$eur_par_m3_part_2010))
}
by_dep <- do.call(rbind, lapply(split(v, v$dep_code), function(g) summarise_w2(g, g$dep_code[1], g$part_2020[1])))
by_dep <- rbind(by_dep, summarise_w2(v, "ensemble", NA))
write.csv(by_dep, "reports/tables/phase7_valeur_m3.csv", row.names = FALSE)
print(by_dep, row.names = FALSE, digits = 3)

# Pentes de l'écart (q/ha) et de la dose (m³/ha) sur la chaleur : rapport = kg de grain par m³ supplémentaire
# des étés chauds (descriptif, sans inférence sur le rapport).
vp <- subset(v, plausible)
w2s <- rbind(one(vp, "dd_32_ja", RHS, "écart irrigué - non irrigué (q/ha) ~ chaleur", y = "gain_q_ha", pct = FALSE),
             one(vp, "dd_32_ja", RHS, "dose (m³/ha) ~ chaleur", y = "dose_m3_ha", pct = FALSE))
w2s$kg_par_m3_supplementaire <- 100 * w2s$estimation[1] / w2s$estimation[2]
write.csv(w2s, "reports/tables/phase7_valeur_m3_pentes.csv", row.names = FALSE)
print(w2s[, c("specification", "estimation", "p_wcb_annee", "n", "kg_par_m3_supplementaire")], row.names = FALSE)
