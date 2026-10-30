# Étape 24 (R) : réplication sur le fourrage, calendrier, variables instrumentales ;
# ajoutés ensuite, exploratoires.
#   - réplication de A1 sur le maïs fourrage irrigué / non irrigué, 2010-2025 (scripts/33_mais_fourrage.py)
#   - falsification par le calendrier (chaleur de juin, de septembre, de l'été suivant et de l'été précédent)
#   - variables instrumentales contre l'erreur de mesure de la chaleur (instruments : E-OBS, LST MODIS)
# Usage : Rscript R/24_q1_fourrage_calendrier_iv.R ; sorties : reports/tables/phase7_fourrage.csv, phase7_calendrier.csv, phase7_iv.csv

source("R/common.R")
FE <- c("dep_code", "annee")
RHS <- c("dd_32_ja", "swi_ja")
one <- function(df, term, rhs, label, y = "ecart_log") {
  s <- summarise_term(fit(df, rhs, y = y), df, term, rhs, label = label, y = y)
  s$p_wcb_annee_unilateral_droite <- 1 - s$p_wcb_annee_unilateral_gauche
  s$n_departements <- length(unique(df$dep_code))
  s$annees <- paste(range(df$annee), collapse = "-")
  s
}

# Taille du test unilatéral à droite par placebo (dérangement des années), permutations tirées d'abord.
placebo_size_right <- function(df, R = 300, B = 399, seed = 123) {
  years <- sort(unique(df$annee))
  field <- tapply(df$dd_32_ja, list(df$dep_code, df$annee), identity)
  set.seed(seed)
  perms <- lapply(seq_len(R), function(r) {
    p <- sample(years)
    while (any(p == years)) p <- sample(years)
    p
  })
  rej <- vapply(seq_len(R), function(r) {
    sim <- df
    sim$x_placebo <- field[cbind(df$dep_code, as.character(perms[[r]][match(df$annee, years)]))]
    sim <- sim[!is.na(sim$x_placebo), ]
    p <- 1 - wcr_pvalue(sim, "ecart_log", "x_placebo", "swi_ja", FE, "annee", "surface_ref_ha", B = B, seed = r)$p_left
    p < 0.05
  }, logical(1))
  mean(rej)
}

# --- maïs fourrage ------------------------------------------------------------------------------
fo <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_fourrage.parquet"))
t1 <- one(fo, "dd_32_ja", RHS, "maïs fourrage, 28 départements, 2010-2025")
t1$taille_placebo <- placebo_size_right(fo)
t1_s1 <- one(subset(fo, statut_irrigue == "1"), "dd_32_ja", RHS, "maïs fourrage, statut 1 (information)")
t1_s1$taille_placebo <- NA
t1$ecart_median_pct <- 100 * (exp(median(fo$ecart_log)) - 1)
t1_s1$ecart_median_pct <- NA
write.csv(rbind(t1, t1_s1), "reports/tables/phase7_fourrage.csv", row.names = FALSE)
print(rbind(t1, t1_s1)[, c("specification", "estimation", "effet_pct_par_unite", "p_wcb_annee_unilateral_droite",
                           "taille_placebo", "n", "n_departements")], row.names = FALSE)

# --- Paires du maïs grain (échantillon A1) -------------------------------------------------------------
long <- as.data.frame(nanoparquet::read_parquet("data/processed/panel_mais_long.parquet"))
long <- subset(long, echantillon_principal)
irr <- subset(long, modalite == "irrigue")
non <- subset(long, modalite == "non_irrigue")[, c(FE, "log_rendement")]
names(non)[3] <- "log_non_irrigue"
d <- merge(irr, non, by = FE)
d$ecart_log <- d$log_rendement - d$log_non_irrigue
stopifnot(nrow(d) == 435)

# --- calendrier -------------------------------------------------------------------------------------
wm <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_month_maize.parquet"))
month_dd <- function(m, name) setNames(subset(wm, month %in% m)[, c("dep_code", "year", "dd_32")], c("dep_code", "annee", name))
ja <- aggregate(dd_32 ~ dep_code + year, data = subset(wm, month %in% 7:8), FUN = sum)
names(ja) <- c("dep_code", "annee", "ja_controle")
d2 <- merge(d, ja, by = FE)
stopifnot(nrow(d2) == 435, max(abs(d2$ja_controle - d2$dd_32_ja)) < 1e-9)   # même construction que dd_32_ja
d2 <- merge(d2, month_dd(6, "dd_32_juin"), by = FE)
d2 <- merge(d2, month_dd(9, "dd_32_sept"), by = FE)
lead <- transform(ja, annee = annee - 1); names(lead)[3] <- "dd_32_ja_suivant"
lag <- transform(ja, annee = annee + 1); names(lag)[3] <- "dd_32_ja_precedent"
d2 <- merge(d2, lead, by = FE, all.x = TRUE)
d2 <- merge(d2, lag, by = FE, all.x = TRUE)
stopifnot(nrow(d2) == 435)
rhs_a <- c("dd_32_juin", "dd_32_ja", "dd_32_sept", "swi_ja")
t2a <- do.call(rbind, lapply(c("dd_32_juin", "dd_32_ja", "dd_32_sept"), function(v)
  one(d2, v, rhs_a, paste("juin + juillet-août + septembre :", v))))
dl <- subset(d2, !is.na(dd_32_ja_suivant))
t2b <- rbind(one(dl, "dd_32_ja_suivant", c(RHS, "dd_32_ja_suivant"), "A1 + chaleur de l'été suivant (2000-2024)"),
             one(d2, "dd_32_ja_precedent", c(RHS, "dd_32_ja_precedent"), "A1 + chaleur de l'été précédent"))
t2b_main <- rbind(one(dl, "dd_32_ja", c(RHS, "dd_32_ja_suivant"), "A1 (avec été suivant) : terme principal"),
                  one(d2, "dd_32_ja", c(RHS, "dd_32_ja_precedent"), "A1 (avec été précédent) : terme principal"))
t2 <- rbind(t2a, t2b, t2b_main)
t2$moyenne_exposition <- c(sapply(c("dd_32_juin", "dd_32_ja", "dd_32_sept"), function(v) weighted.mean(d2[[v]], d2$surface_ref_ha)),
                           NA, NA, NA, NA)
write.csv(t2, "reports/tables/phase7_calendrier.csv", row.names = FALSE)
print(t2[, c("specification", "estimation", "p_wcb_annee", "p_wcb_annee_unilateral_droite", "n")], row.names = FALSE)

# --- variables instrumentales ----------------------------------------------------------------------
eobs <- as.data.frame(nanoparquet::read_parquet("data/processed/weather_dep_eobs_ja.parquet"))
lst <- as.data.frame(nanoparquet::read_parquet("data/processed/lst_dep_ja.parquet"))[, c(FE, "lst_ja")]
d3 <- merge(merge(d, eobs, by = FE), lst, by = FE, all.x = TRUE)
stopifnot(nrow(d3) == 435)
iv_row <- function(df, instr, label) {
  df <- df[!is.na(df[[instr]]), ]
  f_iv <- as.formula(paste("ecart_log ~ swi_ja | dep_code + annee | dd_32_ja ~", instr))
  m <- feols(f_iv, data = df, weights = ~surface_ref_ha)
  fs <- feols(as.formula(paste("dd_32_ja ~", instr, "+ swi_ja | dep_code + annee")), data = df,
              weights = ~surface_ref_ha, vcov = ~annee)
  ols <- coef(fit(df, RHS, y = "ecart_log"))[["dd_32_ja"]]
  rf <- one(df, instr, c(instr, "swi_ja"), paste(label, ": forme réduite"))
  data.frame(specification = label, instrument = instr, beta_iv = coef(m)[["fit_dd_32_ja"]], beta_mco = ols,
             rapport_iv_mco = coef(m)[["fit_dd_32_ja"]] / ols,
             f_premiere_etape_cluster_annee = unname(coeftable(fs)[instr, "t value"]^2),
             forme_reduite = rf$estimation, p_forme_reduite_wcr_unilaterale = rf$p_wcb_annee_unilateral_droite,
             n = nobs(m))
}
t3 <- rbind(iv_row(d3, "dd_32_ja_eobs", "IV par E-OBS"), iv_row(d3, "lst_ja", "IV par LST MODIS"))
write.csv(t3, "reports/tables/phase7_iv.csv", row.names = FALSE)
print(t3, row.names = FALSE)
