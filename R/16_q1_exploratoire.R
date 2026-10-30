# Étape 16 (R) : diagnostics EXPLORATOIRES de Q1 (ajoutés ensuite).
# Usage : Rscript R/16_q1_exploratoire.R
# 1. beta de A1 selon la mesure de la chaleur (masque maïs / pondération surfacique) et la période : estimations
#    ponctuelles seules (moindres carrés pondérés), sans inférence.
# 2. Composition : la part irriguée du maïs grain varie-t-elle avec la chaleur de l'année ? (descriptif)
# Sortie : reports/tables/phase4bis_q1_exploratoire.csv

source("R/common.R")

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
long <- subset(long, echantillon_principal)
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement", "surface_ha")]
names(non)[3:4] <- c("log_non_irrigue", "surface_non_irrigue")
d <- merge(irr, non, by = c("dep_code", "annee"))
d$ecart_log <- d$log_rendement - d$log_non_irrigue
d$part_irriguee <- d$surface_ha / (d$surface_ha + d$surface_non_irrigue)

periods <- list("2000-2025" = d, "2000-2009" = subset(d, annee <= 2009), "2010-2025" = subset(d, annee >= 2010),
                "sans 2003" = subset(d, annee != 2003), "2000-2009 sans 2003" = subset(d, annee <= 2009 & annee != 2003))
rows <- list()
for (per in names(periods)) {
  for (mes in c("masque maïs", "pondération surfacique")) {
    x <- periods[[per]]
    if (mes == "pondération surfacique") { x$dd_32_ja <- x$dd_32_ja_surf; x$swi_ja <- x$swi_ja_surf }
    m <- fit(x, c("dd_32_ja", "swi_ja"), y = "ecart_log")
    rows[[length(rows) + 1]] <- data.frame(analyse = "beta A1 (dd_32_ja)", periode = per, mesure = mes,
                                           estimation = coef(m)[["dd_32_ja"]], n = nobs(m), p_cluster_annee = NA)
  }
}
# Composition : part irriguée (surface de l'année) expliquée par la chaleur, effets fixes département et année.
mc <- fit(d, c("dd_32_ja", "swi_ja"), y = "part_irriguee")
rows[[length(rows) + 1]] <- data.frame(analyse = "part irriguée ~ dd_32_ja (composition)", periode = "2000-2025",
                                       mesure = "masque maïs", estimation = coef(mc)[["dd_32_ja"]], n = nobs(mc),
                                       p_cluster_annee = coeftable(mc, vcov = ~annee)["dd_32_ja", "Pr(>|t|)"])
out <- do.call(rbind, rows)
write.csv(out, "reports/tables/phase4bis_q1_exploratoire.csv", row.names = FALSE)
print(format(out, digits = 3), row.names = FALSE)
cat(sprintf("Part irriguée : moyenne %.3f ; écart-type intra (après effets fixes) %.3f ; coefficient cluster année p = %.3f (information)\n",
            mean(d$part_irriguee), sd(resid(mc)), coeftable(mc, vcov = ~annee)["dd_32_ja", "Pr(>|t|)"]))
