# Étape 14 (R) : Q1 de la phase 4 bis, maïs grain irrigué / non irrigué 2000-2025.
# Usage : Rscript R/14_q1_maize.R
# Spécification de la phase 4 bis.
# Seule l'inférence WCR par année fonde les conclusions ; cluster département et Conley : information.
# p unilatérale à droite = 1 - p unilatérale à gauche (la distribution bootstrap de t* est continue).
# Sorties : reports/tables/phase4bis_q1_*.csv

source("R/common.R")

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement", "rendement_q_ha", "surface_ha")]
names(non)[3:5] <- c("log_non_irrigue", "rdt_non_irrigue", "surface_non_irrigue")
names(irr)[names(irr) == "log_rendement"] <- "log_irrigue"
names(irr)[names(irr) == "rendement_q_ha"] <- "rdt_irrigue"
names(irr)[names(irr) == "surface_ha"] <- "surface_irrigue"
# Paires : département-années où les deux modalités sont observées (jointure interne, contrôlée).
mz <- merge(irr, non, by = c("dep_code", "annee"))
stopifnot(!anyDuplicated(mz[, c("dep_code", "annee")]))
mz$ecart_log <- mz$log_irrigue - mz$log_non_irrigue
mz$dd32_x_crise <- mz$dd_32_ja * mz$jours_crise_ja
d <- subset(mz, echantillon_principal)
cat(sprintf("Paires : %d (tous statuts, %d départements) ; principal : %d paires, %d départements, %d années\n",
            nrow(mz), length(unique(mz$dep_code)), nrow(d), length(unique(d$dep_code)), length(unique(d$annee))))

RHS <- c("dd_32_ja", "swi_ja")
one <- function(df, term, rhs, label, y = "ecart_log", weighted = TRUE) {
  m <- fit(df, rhs, weighted = weighted, y = y)
  s <- summarise_term(m, df, term, rhs, weighted = weighted, label = label, y = y)
  s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche
  ci <- confint(m, parm = term, level = 0.90, vcov = ~annee)
  s$ic90_cr1_annee_bas <- ci[1, 1]
  s$ic90_cr1_annee_haut <- ci[1, 2]
  s$n_departements <- length(unique(df$dep_code))
  s$annees <- paste(range(df$annee), collapse = "-")
  cbind(variable_expliquee = y, s)
}

# --- Modèle principal A1 et hypothèse principale H1 (beta > 0) --------------
main <- one(d, "dd_32_ja", RHS, "A1 principal 2000-2025")
repl <- one(subset(d, annee <= 2009), "dd_32_ja", RHS, "A1 réplication 2000-2009")

# --- Hypothèses secondaires (famille de Holm, 4 tests unilatéraux) -----------
h2a <- one(d, "swi_ja", RHS, "H2a A1 : SWI")
h2b <- one(d, "dd_32_ja", RHS, "H2b non irrigué", y = "log_non_irrigue")
h2c <- one(d, "dd_32_ja", RHS, "H2c irrigué", y = "log_irrigue")
d3 <- subset(d, annee >= 2016)
h3 <- one(d3, "dd32_x_crise", c(RHS, "jours_crise_ja", "dd32_x_crise"), "H3 A1 + crise VigiEau 2016-2025")
sec <- rbind(h2a, h2b, h2c, h3)
sec$hypothese <- c("H2a", "H2b", "H2c", "H3")
sec$sens <- "gauche"
sec$p_unilaterale <- sec$p_wcb_annee_unilateral_gauche
sec$p_holm <- p.adjust(sec$p_unilaterale, method = "holm")

hyp <- rbind(transform(main, hypothese = "H1", sens = "droite", p_unilaterale = p_wcb_annee_unilateral_droite, p_holm = NA),
             transform(repl, hypothese = "réplication", sens = "droite", p_unilaterale = p_wcb_annee_unilateral_droite, p_holm = NA),
             sec)
write.csv(hyp, "reports/tables/phase4bis_q1_hypotheses.csv", row.names = FALSE)
cat("\nHypothèses (Q1) :\n")
print(format(hyp[, c("hypothese", "variable_expliquee", "terme", "estimation", "effet_pct_par_unite", "p_cluster_dep",
                     "p_conley", "p_unilaterale", "p_holm", "n", "annees")], digits = 3), row.names = FALSE)

# --- Robustesses de A1 --------------------------------------------------------
# swap() copie une variable de remplacement sous le nom de la variable principale : dans la sortie, la colonne
# `terme` reste « dd_32_ja » pour R3, R4 (en réalité dd_30_ja) et R5 ; le libellé de la spécification fait foi.
swap <- function(df, from, to) { for (i in seq_along(from)) df[[to[i]]] <- df[[from[i]]]; df }
rob <- list(
  one(subset(mz), "dd_32_ja", RHS, "Q1-R1 38 départements (tous statuts)"),
  one(subset(d, annee >= 2010), "dd_32_ja", RHS, "Q1-R2 2010-2025"),
  one(swap(d, c("dd_32_ja_surf", "swi_ja_surf"), RHS), "dd_32_ja", RHS, "Q1-R3 météo pondérée par la surface"),
  one(swap(d, "dd_30_ja", "dd_32_ja"), "dd_32_ja", RHS, "Q1-R4 seuil 30 °C"),
  one(swap(d, c("dd_32_juillet", "swi_juillet"), RHS), "dd_32_ja", RHS, "Q1-R5 juillet seul"),
  one(d, "dd_32_ja", RHS, "Q1-R6 sans pondération", weighted = FALSE),
  one(subset(d, annee != 2025), "dd_32_ja", RHS, "Q1-R7 sans 2025"),
  one(subset(d, annee != 2003), "dd_32_ja", RHS, "Q1-R8 sans 2003")
)
rob <- do.call(rbind, c(list(main), rob))
write.csv(rob, "reports/tables/phase4bis_q1_robustesse.csv", row.names = FALSE)
cat("\nRobustesses de A1 (terme dd_32_ja ; p WCR unilatérale à droite) :\n")
print(format(rob[, c("specification", "estimation", "effet_pct_par_unite", "p_wcb_annee_unilateral_droite",
                     "n", "n_departements", "annees")], digits = 3), row.names = FALSE)

# --- Taille du test principal (H1) sur ces données ------------------------------
# Placebo = champ réel dd_32_ja à années permutées (dérangement), R = 300, B = 399, test unilatéral à 5 %.
one_sided_right <- function(ct) {
  p <- ct[["Pr(>|t|)"]]
  if (ct[["t value"]] > 0) p / 2 else 1 - p / 2
}
years <- sort(unique(d$annee))
field <- tapply(d$dd_32_ja, list(d$dep_code, d$annee), identity)
set.seed(123)
R <- 300
rej <- c(cluster_dep = 0, conley_200 = 0, wcr_annee = 0)
n_used <- 0
for (r in seq_len(R)) {
  perm <- sample(years)
  while (any(perm == years)) perm <- sample(years)
  sim <- d
  sim$x_placebo <- field[cbind(d$dep_code, as.character(perm[match(d$annee, years)]))]
  sim <- sim[!is.na(sim$x_placebo), ]     # paires absentes l'année permutée
  m <- fit(sim, c("swi_ja", "x_placebo"), y = "ecart_log")
  p_dep <- one_sided_right(coeftable(m, vcov = ~dep_code)["x_placebo", ])
  v_con <- suppressWarnings(vcov_conley(m, lat = ~lat_centroide, lon = ~lon_centroide, cutoff = CONLEY_KM))
  p_con <- one_sided_right(coeftable(m, vcov = v_con)["x_placebo", ])
  p_wcr <- 1 - wcr_pvalue(sim, "ecart_log", "x_placebo", "swi_ja", c("dep_code", "annee"), "annee",
                          "surface_ref_ha", B = 399, seed = r)$p_left
  rej <- rej + (c(p_dep, p_con, p_wcr) < 0.05)
  n_used <- n_used + nrow(sim)
}
size <- data.frame(test = "Q1-H1 (unilatéral à droite)", inference = names(rej), taille_5pct = as.numeric(rej) / R,
                   R = R, B = 399, n_moyen = n_used / R)
write.csv(size, "reports/tables/phase4bis_q1_taille.csv", row.names = FALSE)
cat("\nTaille du test H1 sous H0 (placebo) :\n")
print(size, row.names = FALSE)
