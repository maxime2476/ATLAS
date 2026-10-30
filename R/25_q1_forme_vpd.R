# Étape 25 (R) : forme de la relation, chaleur × sol, VPD ; exploratoires.
#   - forme de la relation (terme quadratique ; tranches 30-32, 32-34, > 34 °C ; 2003 revu)
#   - chaleur × humidité du sol (extrêmes combinés)
#   - déficit de pression de vapeur (scripts/34_vpd.py)
# Usage : Rscript R/25_q1_forme_vpd.R ; sorties : reports/tables/phase7_forme.csv, phase7_forme_2003.csv, phase7_chaleur_sol.csv, phase7_vpd.csv

source("R/common.R")
FE <- c("dep_code", "annee")
RHS <- c("dd_32_ja", "swi_ja")
one <- function(df, term, rhs, label, y = "ecart_log", pct = TRUE) {
  s <- summarise_term(fit(df, rhs, y = y), df, term, rhs, label = label, y = y, pct_meaningful = pct)
  s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche
  s
}

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
long <- subset(long, echantillon_principal)
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c(FE, "log_rendement")]
names(non)[3] <- "log_non_irrigue"
d <- merge(irr, non, by = FE)
d$ecart_log <- d$log_rendement - d$log_non_irrigue
stopifnot(nrow(d) == 435)

# Tranches de degrés-jours de juillet-août depuis la météo mensuelle (masque maïs).
wm <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_month_maize.parquet"))
ja <- aggregate(cbind(dd_30, dd_32, dd_34) ~ dep_code + year, data = subset(wm, month %in% 7:8), FUN = sum)
names(ja)[2] <- "annee"
d <- merge(d, ja, by = FE)
stopifnot(nrow(d) == 435, max(abs(d$dd_32 - d$dd_32_ja)) < 1e-9)
d$tr_30_32 <- d$dd_30 - d$dd_32
d$tr_32_34 <- d$dd_32 - d$dd_34
d$tr_34 <- d$dd_34

# --- Forme de la relation -------------------------------------------------------------------------------------------------
d$dd_32_ja_carre <- d$dd_32_ja^2
rhs_q <- c("dd_32_ja", "dd_32_ja_carre", "swi_ja")
n1a <- rbind(one(d, "dd_32_ja", rhs_q, "quadratique : terme linéaire"),
             one(d, "dd_32_ja_carre", rhs_q, "quadratique : terme au carré", pct = FALSE))
rhs_b <- c("tr_30_32", "tr_32_34", "tr_34", "swi_ja")
n1b <- do.call(rbind, lapply(c("tr_30_32", "tr_32_34", "tr_34"), function(v) one(d, v, rhs_b, paste("tranche", v))))
n1b$moyenne_exposition <- sapply(c("tr_30_32", "tr_32_34", "tr_34"), function(v) weighted.mean(d[[v]], d$surface_ref_ha))
n1a$moyenne_exposition <- NA
# (c) 2003 : écart moyen observé au-dessus de la moyenne du département, contre la prédiction linéaire et quadratique
#     (même calcul que la vérification de 2003 du mémoire, ValOverPct : moyenne pondérée sur les 17 départements).
dev <- function(v) v - ave(v, d$dep_code)
w03 <- d$annee == 2003
b_lin <- coef(fit(d, RHS, y = "ecart_log"))[["dd_32_ja"]]
cq <- coef(fit(d, rhs_q, y = "ecart_log"))
wm03 <- function(x) weighted.mean(x[w03], d$surface_ref_ha[w03])
n1c <- data.frame(ecart_observe_2003 = wm03(dev(d$ecart_log)),
                  predit_lineaire = wm03(b_lin * dev(d$dd_32_ja)),
                  predit_quadratique = wm03(cq[["dd_32_ja"]] * dev(d$dd_32_ja) + cq[["dd_32_ja_carre"]] * dev(d$dd_32_ja_carre)))
n1 <- rbind(n1a, n1b)
write.csv(n1, "reports/tables/phase7_forme.csv", row.names = FALSE)
write.csv(n1c, "reports/tables/phase7_forme_2003.csv", row.names = FALSE)
print(n1[, c("specification", "estimation", "p_wcb_annee", "moyenne_exposition")], row.names = FALSE)
print(n1c)

# --- Chaleur × humidité du sol -------------------------------------------------------------------------------------------------
d$swi_c <- d$swi_ja - weighted.mean(d$swi_ja, d$surface_ref_ha)
d$dd32_x_swi <- d$dd_32_ja * d$swi_c
rhs_2 <- c("dd_32_ja", "swi_ja", "dd32_x_swi")
n2 <- rbind(one(d, "dd32_x_swi", rhs_2, "chaleur x SWI (centré)", pct = FALSE),
            one(d, "dd_32_ja", rhs_2, "pente de la chaleur au SWI moyen"))
n2$ecart_type_swi_intra <- sd(d$swi_ja - ave(d$swi_ja, d$dep_code))
write.csv(n2, "reports/tables/phase7_chaleur_sol.csv", row.names = FALSE)
print(n2[, c("specification", "estimation", "p_wcb_annee", "ecart_type_swi_intra")], row.names = FALSE)

# --- Déficit de pression de vapeur -------------------------------------------------------------------------------------------------
vpd <- as.data.frame(nanoparquet::read_parquet("data/processed/vpd_dep_ja.parquet"))
d <- merge(d, vpd, by = FE)
stopifnot(nrow(d) == 435)
n3 <- rbind(one(d, "vpd_ja", c("vpd_ja", "swi_ja"), "A1 avec VPD (kPa) à la place de dd_32_ja"),
            one(d, "dd_32_ja", c("dd_32_ja", "vpd_ja", "swi_ja"), "chaleur et VPD ensemble : chaleur"),
            one(d, "vpd_ja", c("dd_32_ja", "vpd_ja", "swi_ja"), "chaleur et VPD ensemble : VPD"))
n3$correlation_intra_dd32_vpd <- cor(d$dd_32_ja - ave(d$dd_32_ja, d$dep_code), d$vpd_ja - ave(d$vpd_ja, d$dep_code))
n3$ecart_type_vpd_intra <- sd(d$vpd_ja - ave(d$vpd_ja, d$dep_code))
write.csv(n3, "reports/tables/phase7_vpd.csv", row.names = FALSE)
print(n3[, c("specification", "estimation", "effet_pct_par_unite", "p_wcb_annee", "p_wcb_annee_unilateral_droite",
             "correlation_intra_dd32_vpd", "ecart_type_vpd_intra")], row.names = FALSE)
