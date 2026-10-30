# Étape 10 (R) : modèles principaux M1 et M2, test H2 et placebo.
# Usage : Rscript R/10_fe_models.R
# Spécification de la phase 4.
# Sorties : reports/tables/phase4_principal.csv, reports/tables/phase4_placebo.csv

source("R/common.R")

panel <- load_panel()
df <- subset(panel, echantillon_principal)
stopifnot(nrow(df) == 83 * 16, !anyDuplicated(df[, c("dep_code", "annee")]))

# Exposition moyenne au-delà de 32 °C en 2019 (référence pour exprimer l'effet), pondérée par la surface.
d19 <- subset(df, annee == 2019)
expo_2019 <- weighted.mean(d19$dd_32_remplissage, d19$surface_ref_ha)

RHS_M1 <- c("gdd_0_32_remplissage", "dd_32_remplissage", "prec_printemps", "dd_0_automne", "prec_automne")
RHS_M2 <- c(RHS_M1, "swi_remplissage", "swi_remplissage_2")

m1 <- fit(df, RHS_M1)
m2 <- fit(df, RHS_M2)

rows <- rbind(
  summarise_term(m1, df, "dd_32_remplissage", RHS_M1, label = "M1", exposure_2019 = expo_2019),
  summarise_term(m1, df, "gdd_0_32_remplissage", RHS_M1, label = "M1"),
  summarise_term(m1, df, "prec_printemps", RHS_M1, label = "M1"),
  summarise_term(m1, df, "dd_0_automne", RHS_M1, label = "M1"),
  summarise_term(m1, df, "prec_automne", RHS_M1, label = "M1"),
  summarise_term(m2, df, "dd_32_remplissage", RHS_M2, label = "M2", exposure_2019 = expo_2019),
  # Termes SWI : WCR individuel conservé pour conformité à la spécification (δ1), mais non interprétable
  # (δ1 = pente à SWI = 0, hors support : min 0,20) ; l'inférence pertinente est le test joint H2 ci-dessous.
  summarise_term(m2, df, "swi_remplissage", RHS_M2, label = "M2", pct_meaningful = FALSE),
  summarise_term(m2, df, "swi_remplissage_2", RHS_M2, label = "M2 (complément, ajouté ensuite)",
                 pct_meaningful = FALSE)
)
dir.create("reports/tables", showWarnings = FALSE, recursive = TRUE)
write.csv(rows, "reports/tables/phase4_principal.csv", row.names = FALSE)

# H2 : test joint des termes SWI dans M2, sous les deux matrices de variance analytiques.
w_dep <- wald(m2, keep = "^swi_", vcov = ~dep_code, print = FALSE)
w_con <- wald(m2, keep = "^swi_", print = FALSE,
              vcov = vcov_conley(m2, lat = ~lat_centroide, lon = ~lon_centroide, cutoff = CONLEY_KM))

# Placebo : chaleur extrême de l'année suivante (récoltes 2010-2024).
lead <- df[order(df$dep_code, df$annee), ]
lead$dd_32_remplissage_lead <- ave(lead$dd_32_remplissage, lead$dep_code, FUN = function(v) c(v[-1], NA))
lead <- subset(lead, !is.na(dd_32_remplissage_lead))
RHS_P <- c(RHS_M1, "dd_32_remplissage_lead")
mp <- fit(lead, RHS_P)
plac <- summarise_term(mp, lead, "dd_32_remplissage_lead", RHS_P, label = "Placebo t+1")

# Ajouté ensuite : les mêmes tests sous l'inférence par année (analytique et WCR joint),
# omis dans la première version alors que la règle de conclusion exige les trois inférences.
w_an <- wald(m2, keep = "^swi_", vcov = ~annee, print = FALSE)
wj <- wcr_wald_pvalue(df, "log_rendement", c("swi_remplissage", "swi_remplissage_2"), RHS_M1,
                      c("dep_code", "annee"), "annee", "surface_ref_ha")
h2 <- data.frame(test = c("H2 : swi = swi^2 = 0 (cluster dép.)", "H2 : swi = swi^2 = 0 (Conley 200 km)",
                          "H2 : swi = swi^2 = 0 (cluster année, analytique)",
                          "H2 : swi = swi^2 = 0 (WCR joint par année, Webb, 9999 tirages)"),
                 stat = c(w_dep$stat, w_con$stat, w_an$stat, wj$wald),
                 p = c(w_dep$p, w_con$p, w_an$p, wj$p))
# Sommet de la parabole SWI et position dans la distribution observée (description, pas un effet).
swi_peak <- -coef(m2)[["swi_remplissage"]] / (2 * coef(m2)[["swi_remplissage_2"]])
cat(sprintf("Sommet de la relation SWI : %.3f (part de l'échantillon sous ce niveau : %.1f %%) ; SWI min %.2f, médiane %.2f\n",
            swi_peak, 100 * mean(df$swi_remplissage < swi_peak), min(df$swi_remplissage), median(df$swi_remplissage)))
write.csv(h2, "reports/tables/phase4_h2.csv", row.names = FALSE)
write.csv(plac, "reports/tables/phase4_placebo.csv", row.names = FALSE)

cat(sprintf("Échantillon : %d obs., %d départements, %d récoltes ; exposition moyenne 2019 = %.2f °C·jour\n\n",
            nrow(df), length(unique(df$dep_code)), length(unique(df$annee)), expo_2019))
print(etable(m1, m2, vcov = ~dep_code, digits = 4, fitstat = ~ n + wr2))
cat("\n")
print(format(rows, digits = 3), row.names = FALSE)
cat("\n"); print(h2, row.names = FALSE)
cat("\n"); print(format(plac, digits = 3), row.names = FALSE)
