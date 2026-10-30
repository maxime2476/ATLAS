# Étape 32 (R) : partage irrigué / non irrigué de la SAA
# Ajoutée ensuite, exploratoire.
#   - A1 sans les paires où le rendement non irrigué est dérivé de la production ;
#   - A1 sur ces seules paires ;
#   - A1 + chaleur x indicateur dérivé (WCR bilatéral sur l'interaction) ;
#   - rendement total des deux modes, chaleur x part irriguée moyenne du département (sans utiliser le partage) ;
#   - fourrage dont le rapport irrigué / non irrigué reprend celui du grain ; réplication fourrage sans ces couples.
# Usage : Rscript R/32_q1_partage.R (après scripts/48_partage_saa.py) ; sortie : reports/tables/phase7_partage_saa.csv

source("R/common.R")
FE <- c("dep_code", "annee")
RHS <- c("dd_32_ja", "swi_ja")
one <- function(df, term, rhs, label, y = "ecart_log") {
  s <- summarise_term(fit(df, rhs, y = y), df, term, rhs, label = label, y = y)
  s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche
  s$n_departements <- length(unique(df$dep_code))
  s
}

long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement", "rendement_q_ha", "surface_ha")]
names(non)[3:5] <- c("log_non_irrigue", "rdt_non_irrigue", "surface_non_irrigue")
pairs <- merge(irr, non, by = c("dep_code", "annee"))
pairs$ecart_log <- pairs$log_rendement - pairs$log_non_irrigue
part <- as.data.frame(nanoparquet::read_parquet("data/processed/maize_partage_saa.parquet"))
pairs <- merge(pairs, part[, c("dep_code", "annee", "derive_non_irrigue")], by = c("dep_code", "annee"))
stopifnot(nrow(pairs) == 981, !anyNA(pairs$derive_non_irrigue))
d <- subset(pairs, echantillon_principal)
stopifnot(nrow(d) == 435)
d$derive <- as.numeric(d$derive_non_irrigue)
d$dd_x_derive <- d$dd_32_ja * d$derive

a1 <- one(d, "dd_32_ja", RHS, "A1 (référence)")
z1 <- one(subset(d, derive == 0), "dd_32_ja", RHS, "A1 sans non irrigué dérivé")
z2 <- one(subset(d, derive == 1), "dd_32_ja", RHS, "A1, non irrigué dérivé seulement")
z3 <- one(d, "dd_x_derive", c("dd_32_ja", "swi_ja", "derive", "dd_x_derive"), "interaction chaleur x dérivé (bilatéral)")

# rendement total = production des deux modes / surface totale ; part irriguée moyenne du département, centrée.
d$surface_totale <- d$surface_ha + d$surface_non_irrigue
d$log_total <- log((d$rendement_q_ha * d$surface_ha + d$rdt_non_irrigue * d$surface_non_irrigue) / d$surface_totale)
part_dep <- tapply(d$surface_ha / d$surface_totale, d$dep_code, mean)
w_dep <- tapply(d$surface_ref_ha, d$dep_code, mean)
d$part_irr_c <- part_dep[d$dep_code] - weighted.mean(part_dep, w_dep[names(part_dep)])
d$dd_x_part <- d$dd_32_ja * d$part_irr_c
z4 <- one(d, "dd_x_part", c("dd_32_ja", "dd_x_part", "swi_ja"), "rendement total, chaleur x part irriguée", y = "log_total")

# couples fourrage / grain dont le rapport irrigué / non irrigué arrondi au centième est identique.
fo <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_fourrage.parquet"))
grain <- data.frame(dep_code = pairs$dep_code, annee = pairs$annee,
                    r_grain = round(pairs$rendement_q_ha / pairs$rdt_non_irrigue, 2))
fg <- merge(fo, grain, by = c("dep_code", "annee"))
fg$r_fourrage <- round(fg$irrigue / fg$non_irrigue, 2)
same <- fg$r_fourrage == fg$r_grain
set.seed(123)
ref <- vapply(seq_len(2000), function(k) {
  r_perm <- ave(fg$r_fourrage, fg$dep_code, FUN = function(v) v[sample.int(length(v))])
  sum(r_perm == fg$r_grain)
}, numeric(1))
fo$same_grain <- paste(fo$dep_code, fo$annee) %in% paste(fg$dep_code, fg$annee)[same]
t1 <- one(fo, "dd_32_ja", RHS, "maïs fourrage (référence)")
z5 <- one(subset(fo, !same_grain), "dd_32_ja", RHS, "maïs fourrage sans les couples au rapport identique au grain")

out <- rbind(a1, z1, z2, z3, z4, t1, z5)
out$part_non_irrigue_derive_2000_2009 <- mean(d$derive[d$annee <= 2009])
out$part_non_irrigue_derive_2010_2025 <- mean(d$derive[d$annee >= 2010])
out$z5_couples_communs <- nrow(fg)
out$z5_rapport_identique <- sum(same)
out$z5_ref_mediane <- median(ref)
out$z5_ref_p95 <- unname(quantile(ref, 0.95))
write.csv(out, "reports/tables/phase7_partage_saa.csv", row.names = FALSE)
print(out[, c("specification", "estimation", "p_wcb_annee", "p_wcb_annee_unilateral_droite", "n", "n_departements")],
      row.names = FALSE)
cat(sprintf("Non irrigué dérivé : %.3f (2000-2009), %.3f (2010-2025)\n", mean(d$derive[d$annee <= 2009]),
            mean(d$derive[d$annee >= 2010])))
cat(sprintf("Fourrage : %d couples communs, %d au rapport identique ; référence médiane %.1f, 95e centile %.1f\n",
            nrow(fg), sum(same), median(ref), quantile(ref, 0.95)))
