# Étape 18 (R) : diagnostic ajouté ensuite.
# Le bootstrap par année suppose l'indépendance entre années ; le placebo à années permutées ne peut pas
# détecter une sur-taille due à une dépendance temporelle intra-département. On mesure donc l'autocorrélation
# d'ordre 1 des résidus, au sein de chaque département, pour A1 (maïs) et B1 (blé 1959-2025 ; « B1 » est le nom de
# la spécification 4 bis, M3 dans le mémoire). Limites : des résidus après effets fixes biaisent rho vers le bas
# (biais de Nickell, environ -1/(T-1), soit -0,04 pour T = 26) ; pour le blé, quelques paires d'années consécutives
# traversent les ruptures de source de 1989 et 2010.
# Usage : Rscript R/18_residual_autocorr.R ; sortie : reports/tables/diag_autocorr_residus.csv

source("R/common.R")

ar1 <- function(df, res, unit, time) {
  d <- data.frame(u = df[[unit]], t = df[[time]], e = res)
  d <- d[order(d$u, d$t), ]
  lag <- ave(d$e, d$u, FUN = function(v) c(NA, head(v, -1)))
  consecutive <- ave(d$t, d$u, FUN = function(v) c(NA, diff(v))) == 1
  ok <- !is.na(lag) & !is.na(consecutive) & consecutive
  c(rho = cor(d$e[ok], lag[ok]), n_paires = sum(ok))
}

# Maïs, A1 (paires de l'échantillon principal)
long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
long <- subset(long, echantillon_principal)
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
names(non)[3] <- "log_non_irrigue"
mz <- merge(irr, non, by = c("dep_code", "annee"))
mz$ecart_log <- mz$log_rendement - mz$log_non_irrigue
m1 <- fit(mz, c("dd_32_ja", "swi_ja"), y = "ecart_log")
a <- ar1(mz, resid(m1), "dep_code", "annee")

# Blé, B1 (1959-2025)
p <- load_panel("data/processed/panel_ble_1959.parquet")
p <- subset(p, echantillon_principal & !is.na(rendement_q_ha))
p$dep_periode <- paste(p$dep_code, cut(p$annee, c(-Inf, 1988, 2009, Inf)))
rhs <- c("gdd_0_32_remplissage", "dd_32_remplissage", "prec_printemps", "dd_0_automne", "prec_automne")
m2 <- fit(p, rhs, fe = "dep_periode + annee")
b <- ar1(p, resid(m2), "dep_code", "annee")

out <- data.frame(modele = c("A1 maïs 2000-2025", "B1 blé 1959-2025"), rho_ar1 = c(a[["rho"]], b[["rho"]]),
                  n_paires = c(a[["n_paires"]], b[["n_paires"]]))
write.csv(out, "reports/tables/diag_autocorr_residus.csv", row.names = FALSE)
print(out)
