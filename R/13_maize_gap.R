# Étape 13 (R) : maïs irrigué / non irrigué, analyse exploratoire A de la phase 6.
# Usage : Rscript R/13_maize_gap.R
# Spécification de la phase 6. Seul le WCR par année est jugé fiable (phase 4).
# Sortie : reports/tables/phase6_mais.csv

source("R/common.R")

mz <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais.parquet"))
mz$log_irrigue <- log(mz$rdt_irrigue)
mz$log_non_irrigue <- log(mz$rdt_non_irrigue)
RHS <- c("dd_32_ja", "swi_ja")

rows <- list()
for (s in c("principal", "tous_statuts")) {
  d <- if (s == "principal") subset(mz, echantillon_principal) else mz
  for (y in c("ecart_log", "log_irrigue", "log_non_irrigue")) {
    m <- fit(d, RHS, y = y)
    for (term in RHS) {
      rows[[length(rows) + 1]] <- cbind(echantillon = s, variable_expliquee = y,
                                        summarise_term(m, d, term, RHS, label = paste(s, y), y = y))
    }
  }
}
out <- do.call(rbind, rows)
write.csv(out, "reports/tables/phase6_mais.csv", row.names = FALSE)
cat(sprintf("Échantillon principal : %d départements, %d obs. ; tous statuts : %d départements, %d obs.\n",
            length(unique(subset(mz, echantillon_principal)$dep_code)), nrow(subset(mz, echantillon_principal)),
            length(unique(mz$dep_code)), nrow(mz)))
print(format(out[, c("echantillon", "variable_expliquee", "terme", "estimation", "p_cluster_dep", "p_conley",
                     "p_wcb_annee", "n")], digits = 3), row.names = FALSE)

# Diagnostic (rapporté comme tel) : taille des trois inférences SUR LES DONNÉES MAÏS.
# Placebo = champ réel dd_32_ja à années permutées (même méthode que R/12_diagnostics.R pour le blé).
d <- subset(mz, echantillon_principal)
years <- sort(unique(d$annee))
field <- tapply(d$dd_32_ja, list(d$dep_code, d$annee), identity)
set.seed(123)
R <- 200
res <- list()
for (y in c("ecart_log", "log_non_irrigue")) {
  rej <- c(cluster_dep = 0, conley_200 = 0, wcr_annee = 0)
  for (r in seq_len(R)) {
    perm <- sample(years)
    while (any(perm == years)) perm <- sample(years)
    sim <- d
    sim$x_placebo <- field[cbind(d$dep_code, as.character(perm[match(d$annee, years)]))]
    ok <- !is.na(sim$x_placebo)          # Jura : années absentes du panel
    sim <- sim[ok, ]
    m <- fit(sim, c("swi_ja", "x_placebo"), y = y)
    p_dep <- coeftable(m, vcov = ~dep_code)["x_placebo", "Pr(>|t|)"]
    p_con <- coeftable(m, vcov = suppressWarnings(vcov_conley(m, lat = ~lat_centroide, lon = ~lon_centroide,
                                                              cutoff = CONLEY_KM)))["x_placebo", "Pr(>|t|)"]
    p_wcr <- wcr_pvalue(sim, y, "x_placebo", "swi_ja", c("dep_code", "annee"), "annee", "surface_ref_ha",
                        B = 399, seed = r)$p
    rej <- rej + (c(p_dep, p_con, p_wcr) < 0.05)
  }
  res[[y]] <- data.frame(variable_expliquee = y, inference = names(rej), taille_5pct = as.numeric(rej) / R, R = R)
}
size <- do.call(rbind, res)
write.csv(size, "reports/tables/phase6_mais_taille.csv", row.names = FALSE)
cat("\nTaille sous H0 (placebo = dd_32_ja à années permutées), échantillon principal :\n")
print(size, row.names = FALSE)
