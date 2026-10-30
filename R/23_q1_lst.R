# Étape 23 (R) : température de surface MODIS de juillet-août sur le masque maïs.
# Prérequis : scripts/30_lst_appeears.py (commande, téléchargement), scripts/31_lst_aggregate.py,
#             scripts/28_complements_python.py preparer (part irriguée)
# Usage : Rscript R/23_q1_lst.R ; sorties : reports/tables/phase7_lst.csv

source("R/common.R")

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
lst <- as.data.frame(nanoparquet::read_parquet("data/processed/lst_dep_ja.parquet"))
cov <- as.data.frame(nanoparquet::read_parquet("data/processed/phase7_covariables_dep.parquet"))
FE <- c("dep_code", "annee")

pairs <- function(df) {
  irr <- subset(df, modalite == "irrigue")
  non <- subset(df, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
  names(non)[3] <- "log_non_irrigue"
  d <- merge(irr, non, by = FE)
  d$ecart_log <- d$log_rendement - d$log_non_irrigue
  d
}
d <- merge(pairs(subset(long, echantillon_principal)), lst[, c(FE, "lst_ja")], by = FE)
stopifnot(nrow(d) == 435)
cat(sprintf("LST manquante : %d paires sur 435\n", sum(is.na(d$lst_ja))))
d <- subset(d, !is.na(lst_ja))

# (a) corrélations
within <- function(v, g) v - ave(v, g)
cors <- data.frame(correlation_brute = cor(d$lst_ja, d$dd_32_ja),
                   correlation_intra_departement = cor(within(d$lst_ja, d$dep_code), within(d$dd_32_ja, d$dep_code)),
                   n = nrow(d))

# (b) A1 avec la LST à la place des degrés-jours
qb <- d
qb$dd_32_ja <- qb$lst_ja                       # seule la mesure de chaleur change
b <- summarise_term(fit(qb, c("dd_32_ja", "swi_ja"), y = "ecart_log"), qb, "dd_32_ja", c("dd_32_ja", "swi_ja"),
                    label = "A1 avec LST de juillet-août (°C) à la place de dd_32_ja", y = "ecart_log")
b$terme <- "lst_ja"
b$p_wcb_annee_unilateral_droite <- 1 - b$p_wcb_annee_unilateral_gauche

# (c) refroidissement : pente de la LST sur la chaleur de l'air selon la part irriguée, 38 départements
all <- merge(pairs(long), lst[, c(FE, "lst_ja")], by = FE)
all <- merge(subset(all, !is.na(lst_ja)), cov[, c("dep_code", "part_irriguee")], by = "dep_code")
all$part_irr_c <- all$part_irriguee - mean(cov$part_irriguee)
all$dd32_x_part_irr <- all$dd_32_ja * all$part_irr_c
rhs_c <- c("dd_32_ja", "dd32_x_part_irr", "swi_ja")
c1 <- summarise_term(fit(all, rhs_c, y = "lst_ja"), all, "dd32_x_part_irr", rhs_c,
                     label = "LST ~ chaleur x part irriguée (38 départements)", y = "lst_ja")
c0 <- summarise_term(fit(all, rhs_c, y = "lst_ja"), all, "dd_32_ja", rhs_c,
                     label = "pente de la LST sur la chaleur, part irriguée moyenne", y = "lst_ja")
for (s in list("c0", "c1")) assign(s, transform(get(s), p_wcb_annee_unilateral_droite = NA))

res <- rbind(b, c0, c1)
res <- cbind(res, cors[rep(1, nrow(res)), ])
write.csv(res, "reports/tables/phase7_lst.csv", row.names = FALSE)
print(cors, row.names = FALSE)
print(res[, c("specification", "terme", "estimation", "p_wcb_annee", "p_wcb_annee_unilateral_droite", "n")], row.names = FALSE)
