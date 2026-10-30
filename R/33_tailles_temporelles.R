# Étape 33 (R) : taille des inférences à composante temporelle sur les cinq tests du tableau des tailles ; ajoutée ensuite.
# Pour chaque test, on rejoue exactement les permutations placebo du script d'origine (graine 123, même boucle de
# dérangement, même ordre des tirages ; le WCR, qui tire sous une graine locale, n'est pas refait) et on mesure la
# taille du cluster par année, du cluster à deux dimensions et de Driscoll-Kraay. Contrôle : la taille du cluster par
# département doit être identique à celle publiée par le script d'origine.
# Usage : Rscript R/33_tailles_temporelles.R ; sortie : reports/tables/phase7_tailles_temporelles.csv

source("R/common.R")

two_sided <- function(ct) ct[["Pr(>|t|)"]]
one_sided_right <- function(ct) if (ct[["t value"]] > 0) ct[["Pr(>|t|)"]] / 2 else 1 - ct[["Pr(>|t|)"]] / 2
one_sided_left <- function(ct) if (ct[["t value"]] < 0) ct[["Pr(>|t|)"]] / 2 else 1 - ct[["Pr(>|t|)"]] / 2

# Rejoue R permutations à partir de l'état aléatoire courant ; renvoie les taux de rejet à 5 %.
# `df` : données ; `x` : chaleur réelle ; `rhs` : contrôles ; `side` : fonction de p-valeur.
replay <- function(df, x, rhs, y, fe, side, R) {
  years <- sort(unique(df$annee))
  field <- tapply(df[[x]], list(df$dep_code, df$annee), identity)
  rej <- c(cluster_dep = 0, cluster_annee = 0, cluster_dep_annee = 0, driscoll_kraay = 0)
  for (r in seq_len(R)) {
    perm <- sample(years)
    while (any(perm == years)) perm <- sample(years)
    sim <- df
    sim$x_placebo <- field[cbind(df$dep_code, as.character(perm[match(df$annee, years)]))]
    sim <- sim[!is.na(sim$x_placebo), ]
    m <- fit(sim, c(rhs, "x_placebo"), fe = fe, y = y)
    p <- c(side(coeftable(m, vcov = ~dep_code)["x_placebo", ]),
           side(coeftable(m, vcov = ~annee)["x_placebo", ]),
           side(coeftable(m, vcov = ~dep_code + annee)["x_placebo", ]),
           side(coeftable(m, vcov = DK ~ annee)["x_placebo", ]))
    rej <- rej + (p < 0.05)
  }
  rej / R
}

out <- list()
add <- function(test, sizes, R, published_dep) {
  if (abs(sizes[["cluster_dep"]] - published_dep) > 1e-12)
    stop(sprintf("%s : permutations non reproduites (cluster dép. %.4f contre %.4f publié)", test,
                 sizes[["cluster_dep"]], published_dep))
  out[[length(out) + 1]] <<- data.frame(test = test, inference = names(sizes), taille_5pct = as.numeric(sizes), R = R)
}

# 1. Blé 2010-2025, bilatéral (R/12_diagnostics.R, beta vrai = 0 : les 300 premiers tirages).
ble <- subset(load_panel(), echantillon_principal)
RHS_M1 <- c("gdd_0_32_remplissage", "dd_32_remplissage", "prec_printemps", "dd_0_automne", "prec_automne")
other <- setdiff(RHS_M1, "dd_32_remplissage")
pub <- read.csv("reports/tables/phase4_simulation_inference.csv")
set.seed(123)
s <- replay(ble, "dd_32_remplissage", other, "log_rendement", "dep_code + annee", two_sided, 300)
add("Blé 2010-2025 (bilatéral)", s, 300, subset(pub, beta_vrai == 0 & inference == "cluster_dep")$taux_rejet_5pct)

# 2. Blé 1959-2025, unilatéral à gauche (R/15_q2_wheat.R ; effets fixes département x période de source).
p <- subset(load_panel("data/processed/panel_ble_1959.parquet"), echantillon_principal)
p <- p[!is.na(p$rendement_q_ha), ]
p$dep_periode <- paste(p$dep_code, cut(p$annee, c(-Inf, 1988, 2009, Inf), labels = c("1959-1988", "1989-2009", "2010-2025")))
pub <- read.csv("reports/tables/phase4bis_q2_taille.csv")
set.seed(123)
s <- replay(p, "dd_32_remplissage", other, "log_rendement", "dep_periode + annee", one_sided_left, 300)
add("Blé 1959-2025 (unilatéral)", s, 300, subset(pub, inference == "cluster_dep")$taille_5pct)

# 3-4. Maïs, phase 6, 2010-2025, bilatéral (R/13_maize_gap.R : écart, puis maïs non irrigué, à la suite).
mz <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais.parquet"))
mz$log_non_irrigue <- log(mz$rdt_non_irrigue)
d6 <- subset(mz, echantillon_principal)
pub <- read.csv("reports/tables/phase6_mais_taille.csv")
set.seed(123)
s <- replay(d6, "dd_32_ja", "swi_ja", "ecart_log", "dep_code + annee", two_sided, 200)
add("Maïs, écart, phase 6 (bilatéral)", s, 200, subset(pub, variable_expliquee == "ecart_log" & inference == "cluster_dep")$taille_5pct)
s <- replay(d6, "dd_32_ja", "swi_ja", "log_non_irrigue", "dep_code + annee", two_sided, 200)
add("Maïs non irrigué, phase 6 (bilatéral)", s, 200,
    subset(pub, variable_expliquee == "log_non_irrigue" & inference == "cluster_dep")$taille_5pct)

# 5. Maïs, A1, 2000-2025, unilatéral à droite (R/14_q1_maize.R).
long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
names(non)[3] <- "log_non_irrigue"
a1 <- merge(irr, non, by = c("dep_code", "annee"))
a1$ecart_log <- a1$log_rendement - a1$log_non_irrigue
a1 <- subset(a1, echantillon_principal)
stopifnot(nrow(a1) == 435)
pub <- read.csv("reports/tables/phase4bis_q1_taille.csv")
set.seed(123)
s <- replay(a1, "dd_32_ja", "swi_ja", "ecart_log", "dep_code + annee", one_sided_right, 300)
add("Maïs, écart, A1 2000-2025 (unilatéral)", s, 300, subset(pub, inference == "cluster_dep")$taille_5pct)

# p-valeurs sur les données (blé M1 2010-2025, bilatéral ; A1, unilatéral à droite), pour situer ces inférences.
pvals <- function(m, term, side) c(cluster_dep = side(coeftable(m, vcov = ~dep_code)[term, ]),
                                   cluster_annee = side(coeftable(m, vcov = ~annee)[term, ]),
                                   cluster_dep_annee = side(coeftable(m, vcov = ~dep_code + annee)[term, ]),
                                   driscoll_kraay = side(coeftable(m, vcov = DK ~ annee)[term, ]))
pb <- pvals(fit(ble, RHS_M1), "dd_32_remplissage", two_sided)
pa <- pvals(fit(a1, c("dd_32_ja", "swi_ja"), y = "ecart_log"), "dd_32_ja", one_sided_right)
out[[length(out) + 1]] <- data.frame(test = "p sur données : blé M1 2010-2025 (bilatéral)", inference = names(pb),
                                     taille_5pct = NA, R = NA, p_donnees = as.numeric(pb))
out[[length(out) + 1]] <- data.frame(test = "p sur données : A1 (unilatéral)", inference = names(pa),
                                     taille_5pct = NA, R = NA, p_donnees = as.numeric(pa))
out[1:5] <- lapply(out[1:5], function(x) transform(x, p_donnees = NA))
res <- do.call(rbind, out)
write.csv(res, "reports/tables/phase7_tailles_temporelles.csv", row.names = FALSE)
print(res[!is.na(res$p_donnees), c("test", "inference", "p_donnees")], row.names = FALSE)
print(reshape(res[is.na(res$p_donnees), c("test", "inference", "taille_5pct")], idvar = "test", timevar = "inference", direction = "wide"),
      row.names = FALSE)
