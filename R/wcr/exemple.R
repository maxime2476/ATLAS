# Exemple autonome de R/wcr/wcr.R sur des panels SIMULÉS (aucune donnée ATLAS nécessaire).
# Usage : Rscript R/wcr/exemple.R   (depuis la racine du dépôt ; seule dépendance : fixest)
#
# Processus simulé : 40 régions sur une grille 8 × 5, 25 années. Chaque année, l'exposition x (par ex.
# une vague de chaleur) et le résidu du rendement reçoivent chacun un champ spatial aléatoire, corrélé
# entre régions voisines (corrélation exp(-distance / 3)), dont la géographie change d'une année à
# l'autre. Les effets fixes année n'en retirent que la moyenne. Le vrai effet de x est NUL. Le cluster
# par région suppose les régions indépendantes une même année, ce qui est faux.
#
# 1. Monte-Carlo : on tire R panels indépendants et on compte les rejets à 5 % de chaque inférence.
# 2. Usage sur des données réelles : placebo_size() mesure la taille sur UN jeu de données en permutant
#    les années de l'exposition (c'est ce que fait le projet, R/14_q1_maize.R et R/15_q2_wheat.R).

suppressPackageStartupMessages(library(fixest))
source("R/wcr/wcr.R")

N_REG <- 40
N_YEAR <- 25
coords <- expand.grid(cx = 1:8, cy = 1:5)
L <- t(chol(exp(-as.matrix(dist(coords)) / 3)))           # facteur de Cholesky de la covariance spatiale

simulate_panel <- function() {
  d <- expand.grid(region = seq_len(N_REG), annee = seq_len(N_YEAR))
  field <- function() as.vector(L %*% matrix(rnorm(N_REG * N_YEAR), N_REG))   # un champ par année
  d$x <- field() + rnorm(nrow(d), sd = 0.5)
  d$y <- 0.5 * d$region / N_REG + field() + rnorm(nrow(d), sd = 0.5)
  d$poids <- 1
  d
}

# 1. Taille par Monte-Carlo ------------------------------------------------------
set.seed(123)
R <- 300
rej <- c(cluster_region = 0, cluster_annee_cr1 = 0, wcr_annee = 0)
for (r in seq_len(R)) {
  d <- simulate_panel()
  m <- feols(y ~ x | region + annee, data = d)
  p <- c(coeftable(m, vcov = ~region)["x", "Pr(>|t|)"],
         coeftable(m, vcov = ~annee)["x", "Pr(>|t|)"],
         wcr_pvalue(d, "y", "x", character(0), c("region", "annee"), "annee", "poids", B = 199, seed = r)$p)
  rej <- rej + (p < 0.05)
}
cat(sprintf("Monte-Carlo, %d panels de %d régions × %d années, vrai effet nul.\n", R, N_REG, N_YEAR))
cat("Taux de rejet à tort au seuil de 5 % (intervalle de Monte-Carlo à 95 % : ± 2,5 points) :\n")
print(round(rej / R, 3))

# 2. Usage sur un seul jeu de données (comme sur des données réelles) ---------------
d <- simulate_panel()
tests <- list(
  cluster_region = function(s) coeftable(feols(y ~ x_placebo | region + annee, s), vcov = ~region)["x_placebo", "Pr(>|t|)"],
  wcr_annee = function(s) wcr_pvalue(s, "y", "x_placebo", character(0), c("region", "annee"), "annee", "poids", B = 199)$p
)
cat("\nplacebo_size() sur un seul panel (exposition réelle, années permutées, R = 100) :\n")
print(placebo_size(d, "x", "region", "annee", tests, R = 100), row.names = FALSE)
cat("Ce diagnostic garde y fixe et ne permute que les années de x : il est indicatif (voir R/wcr/README.md).\n")

# Dans le dépôt ATLAS, les résultats du Monte-Carlo sont enregistrés pour le mémoire (chiffres non saisis à la main).
if (dir.exists("reports/tables")) {
  write.csv(data.frame(inference = names(rej), taille_5pct = as.numeric(rej) / R, R = R, n_regions = N_REG,
                       n_annees = N_YEAR), "reports/tables/wcr_exemple_montecarlo.csv", row.names = FALSE)
}
