# Tests de l'inférence R : WCR (R/wcr/wcr.R), jackknife par année CV3 (R/30, R/28) et graines aléatoires.
# Référence de chaque preuve : une réestimation complète (indicatrices ou feols(subset = ...)) comparée au code.
# Usage (depuis la racine du dépôt) : Rscript tests/test_r_inference.R
# Code de sortie non nul si un test échoue. Les tests sur le maïs sont sautés si le panel traité est absent.
# Dépendances : fixest, nanoparquet (déjà requises par R/common.R) ; pas de testthat.

source("R/common.R")

n_fail <- 0
check <- function(label, ok, detail = "") {
  cat(sprintf("[%s] %s%s\n", if (isTRUE(ok)) "OK  " else "ÉCHEC", label, if (nzchar(detail)) paste0(" — ", detail) else ""))
  if (!isTRUE(ok)) n_fail <<- n_fail + 1
}
# Évalue, sans exécuter le script, les définitions de fonctions `names` d'un script R.
load_fns <- function(path, names) {
  for (e in parse(path)) {
    if (is.call(e) && identical(e[[1]], as.name("<-")) && is.name(e[[2]]) && as.character(e[[2]]) %in% names) {
      eval(e, globalenv())
    }
  }
}
cr0 <- ssc(K.adj = FALSE, G.adj = FALSE)   # CR0 : la statistique de wcr_pvalue omet le facteur de petit échantillon

# =====================================================================================================
# 1. WCR : partiallisation pondérée et re-projection des tirages (wcr_pvalue)
# =====================================================================================================
# Panel simulé non cylindré, poids très inégaux, effets fixes unité + année, grappes par année.
set.seed(1)
sim <- expand.grid(u = 1:30, yr = 1:12)
sim <- sim[runif(nrow(sim)) > 0.15, ]
sim$x <- rnorm(nrow(sim)) + 0.3 * sim$yr + rnorm(12)[sim$yr]
sim$z <- rnorm(nrow(sim)) + 0.5 * sim$x
sim$w <- exp(rnorm(nrow(sim)))
sim$y <- 0.2 * sim$z + rnorm(30)[sim$u] + rnorm(12)[sim$yr] + rnorm(nrow(sim))
B <- 199

# Tirages bootstrap internes de wcr_pvalue, capturés sans modifier le module.
run_wcr <- function(tol = NULL) {
  if (!is.null(tol)) {
    tr <- bquote(tol <- .(tol))
    suppressMessages(trace(fixest::demean, tracer = tr, where = asNamespace("fixest"), print = FALSE))
    on.exit(suppressMessages(untrace(fixest::demean, where = asNamespace("fixest"))))
  }
  suppressMessages(trace(wcr_pvalue, exit = quote(assign(".t_star", t_star, envir = globalenv())), print = FALSE))
  res <- wcr_pvalue(sim, "y", "x", "z", c("u", "yr"), "yr", "w", B = B, seed = 7)
  suppressMessages(untrace(wcr_pvalue))
  res$t_star <- .t_star
  res
}

# Référence : modèle COMPLET réestimé à chaque tirage, effets fixes en indicatrices (aucun démoyennage itératif).
# y* = ajusté restreint + résidu restreint × v_g, avec les mêmes poids de Webb (même graine, même ordre de tirage).
restr <- feols(y ~ z + factor(u) + factor(yr), sim, weights = ~w)
g <- as.integer(factor(sim$yr))
set.seed(7)
V <- vapply(seq_len(B), function(i) webb_weights(max(g))[g], numeric(nrow(sim)))
t_full <- function(v, weighted = TRUE) {
  sim$ys <- fitted(restr) + resid(restr) * v
  m <- feols(ys ~ x + z + factor(u) + factor(yr), sim, weights = if (weighted) ~w else NULL, vcov = ~yr, ssc = cr0)
  tstat(m)[["x"]]
}
t_ref <- apply(V, 2, t_full)
t0_ref <- tstat(feols(y ~ x + z + factor(u) + factor(yr), sim, weights = ~w, vcov = ~yr, ssc = cr0))[["x"]]

# (a) wcr_pvalue tel qu'utilisé par les scripts (DEMEAN_TOL = 1e-12) : l'écart doit être < 1e-12.
exact <- run_wcr()
check("1a t observé WCR = feols complet pondéré (CR0)", abs(exact$t - t0_ref) < 1e-12,
      sprintf("écart %.1e", abs(exact$t - t0_ref)))
check("1a t* re-projetés = feols complet à chaque tirage", max(abs(exact$t_star - t_ref)) < 1e-12,
      sprintf("écart max %.1e sur %d tirages", max(abs(exact$t_star - t_ref)), B))
check("1a p-valeurs identiques", exact$p == mean(abs(t_ref) >= abs(t0_ref)) && exact$p_left == mean(t_ref <= t0_ref))

# (b) Pourquoi DEMEAN_TOL : à la tolérance par défaut de fixest::demean (1e-6), l'écart est numérique (~1e-7).
loose <- run_wcr(tol = 1e-6)
err_loose <- max(abs(loose$t_star - t_ref))
check("1b à la tolérance 1e-6 de fixest, l'écart dépasse 1e-12 mais reste < 1e-5", err_loose > 1e-12 && err_loose < 1e-5,
      sprintf("écart max %.1e (précision du démoyennage, pas erreur algébrique)", err_loose))

# (c) Contrôles négatifs : le test détecte une re-projection oubliée et des poids ignorés.
dm <- fixest::demean(as.matrix(sim[, c("y", "x", "z")]), sim[, c("u", "yr")], weights = sim$w, tol = 1e-14)
rz <- function(v) v - dm[, "z"] * sum(sim$w * dm[, "z"] * v) / sum(sim$w * dm[, "z"]^2)
yt <- rz(dm[, "y"]); xt <- rz(dm[, "x"])
t_noproj <- apply(V, 2, function(v) {
  ys <- yt * v; b <- sum(sim$w * xt * ys) / sum(sim$w * xt^2); e <- ys - xt * b
  b / sqrt(sum(rowsum(sim$w * xt * e, g)^2) / sum(sim$w * xt^2)^2)
})
check("1c sans re-projection, les t* diffèrent (le test a de la puissance)", max(abs(t_noproj - t_ref)) > 1e-3,
      sprintf("écart max %.2f", max(abs(t_noproj - t_ref))))
t_unw <- apply(V[, 1:20], 2, t_full, weighted = FALSE)
check("1c MCO non pondérés : t* différents (les poids sont bien appliqués)", max(abs(t_unw - t_ref[1:20])) > 1e-3,
      sprintf("écart max %.2f", max(abs(t_unw - t_ref[1:20]))))

# =====================================================================================================
# 2. Jackknife par année (CV3) et WCR du CV3, maïs (R/30, R/28, R/22)
# =====================================================================================================
mais_path <- "data/processed/panel_mais_long.parquet"
if (!file.exists(mais_path)) {
  cat("[SAUT] 2 : panel maïs absent (", mais_path, ")\n")
} else {
  long <- as.data.frame(nanoparquet::read_parquet(mais_path))
  irr <- subset(long, modalite == "irrigue")
  non <- subset(long, modalite == "non_irrigue")[, c("dep_code", "annee", "log_rendement")]
  names(non)[3] <- "log_non_irrigue"
  d <- merge(irr, non, by = c("dep_code", "annee"))
  d <- subset(d, echantillon_principal)
  d$ecart_log <- d$log_rendement - d$log_non_irrigue
  d <- d[order(d$annee, d$dep_code), ]
  years <- sort(unique(d$annee))
  G <- length(years)
  FE <- c("dep_code", "annee")
  check("2 échantillon A1 : 435 couples, 26 années", nrow(d) == 435 && G == 26)

  load_fns("R/30_q1_inference.R", c("design", "coef_rows", "jack_rows", "cv3_t", "wcr_cv3"))
  load_fns("R/28_q1_cv3_saa.R", "p_cv3")
  f_a1 <- ecart_log ~ dd_32_ja + swi_ja | dep_code + annee

  # Référence : 26 réestimations complètes (effets fixes départementaux et SWI réestimés sans l'année t).
  b_hat <- coef(feols(f_a1, d, weights = ~surface_ref_ha))[["dd_32_ja"]]
  b_loo <- vapply(years, function(t) coef(feols(f_a1, d, weights = ~surface_ref_ha, subset = d$annee != t,
                                                fixef.tol = 1e-11))[["dd_32_ja"]], numeric(1))
  se_ref <- sqrt((G - 1) / G * sum((b_loo - b_hat)^2))

  J <- jack_rows(d, "dd_32_ja")
  s30 <- cv3_t(J, matrix(d$ecart_log))
  b_loo30 <- vapply(J$loo, function(l) sum(l$a * d$ecart_log[l$idx]), numeric(1))
  check("2a R/30 : beta sans l'année t = feols(subset = annee != t), 26 années", max(abs(b_loo30 - b_loo)) < 1e-12,
        sprintf("écart max %.1e", max(abs(b_loo30 - b_loo))))
  check("2a R/30 : erreur-type CV3 = boucle explicite", abs(s30$se - se_ref) < 1e-12,
        sprintf("se %.6f, écart %.1e", se_ref, abs(s30$se - se_ref)))
  p28 <- p_cv3(d, "dd_32_ja", "ecart_log")
  check("2a R/28 (et R/22, même code) : p CV3 = boucle explicite", abs(p28 - (1 - pt(b_hat / se_ref, G - 1))) < 1e-12,
        sprintf("p unilatérale droite %.4f", p28))

  # Contrôle négatif : leave-one-out sur résidus partiallisés une fois pour toutes sur les 26 années.
  w <- d$surface_ref_ha
  dm <- fixest::demean(as.matrix(d[, c("ecart_log", "dd_32_ja", "swi_ja")]), d[, FE], weights = w, tol = 1e-12)
  rz <- function(v) v - dm[, "swi_ja"] * sum(w * dm[, "swi_ja"] * v) / sum(w * dm[, "swi_ja"]^2)
  xt <- rz(dm[, "dd_32_ja"]); yt <- rz(dm[, "ecart_log"])
  b_wrong <- vapply(years, function(t) { k <- d$annee != t; sum(w[k] * xt[k] * yt[k]) / sum(w[k] * xt[k]^2) }, numeric(1))
  se_wrong <- sqrt((G - 1) / G * sum((b_wrong - b_hat)^2))
  check("2b la version erronée donne un CV3 différent (le test la détecterait)", abs(se_wrong - se_ref) > 1e-4,
        sprintf("erronée %.6f contre %.6f", se_wrong, se_ref))

  # WCR du CV3 : la statistique de chaque tirage doit être celle d'un CV3 recalculé par 26 réestimations.
  restr <- feols(ecart_log ~ swi_ja | dep_code + annee, d, weights = ~surface_ref_ha, fixef.tol = 1e-11)
  check("2c modèle restreint : aucune observation retirée par fixest", nobs(restr) == nrow(d))
  gg <- as.integer(factor(d$annee))
  set.seed(123)
  Vd <- vapply(1:5, function(i) webb_weights(G)[gg], numeric(nrow(d)))
  Ys <- fitted(restr) + resid(restr) * Vd
  t_fast <- cv3_t(J, Ys)$t
  t_slow <- apply(Ys, 2, function(ys) {
    d$ys <- ys
    fs <- ys ~ dd_32_ja + swi_ja | dep_code + annee
    b <- coef(feols(fs, d, weights = ~surface_ref_ha, fixef.tol = 1e-11))[["dd_32_ja"]]
    bl <- vapply(years, function(t) coef(feols(fs, d, weights = ~surface_ref_ha, subset = d$annee != t,
                                               fixef.tol = 1e-11))[["dd_32_ja"]], numeric(1))
    b / sqrt((G - 1) / G * sum((bl - b)^2))
  })
  check("2c WCR-CV3 : t* exacts = 5 tirages × 27 réestimations", max(abs(t_fast - t_slow)) < 1e-9,
        sprintf("écart max %.1e (limité par fixef.tol de la référence)", max(abs(t_fast - t_slow))))

  # =====================================================================================================
  # 3. Graines aléatoires
  # =====================================================================================================
  rng_state <- function() if (exists(".Random.seed", globalenv())) get(".Random.seed", globalenv()) else NULL
  untouched <- function(expr) { set.seed(123); s0 <- rng_state(); force(expr); identical(s0, rng_state()) }
  m_a1 <- fit(d, c("dd_32_ja", "swi_ja"), y = "ecart_log")
  check("3a feols, coeftable, fixest::demean ne touchent pas la graine",
        untouched(coeftable(fit(d, c("dd_32_ja", "swi_ja"), y = "ecart_log"), vcov = ~dep_code)) &&
          untouched(fixest::demean(as.matrix(d[, "ecart_log", drop = FALSE]), d[, FE])))
  check("3a vcov_conley ne touche pas la graine",
        untouched(suppressWarnings(vcov_conley(m_a1, lat = ~lat_centroide, lon = ~lon_centroide, cutoff = CONLEY_KM))))
  check("3a p_cv3 (R/28) et cv3_t (R/30) ne touchent pas la graine",
        untouched(p_cv3(d, "dd_32_ja", "ecart_log")) && untouched(cv3_t(jack_rows(d, "dd_32_ja"), matrix(d$ecart_log))))

  # Les fonctions de R/wcr/wcr.R et wcr_cv3 (R/30) tirent sous une graine locale et restaurent l'état de l'appelant.
  wcr_a1 <- function(seed, B = 399) wcr_pvalue(d, "ecart_log", "dd_32_ja", "swi_ja", FE, "annee", "surface_ref_ha",
                                               B = B, seed = seed)
  set.seed(1); r1 <- wcr_a1(5)
  set.seed(999); runif(10); r2 <- wcr_a1(5)
  check("3b wcr_pvalue indépendante de l'état antérieur du générateur", identical(r1, r2))
  check("3b wcr_pvalue, wcr_wald_pvalue, wcr_cv3, placebo_size laissent la graine globale intacte",
        untouched(wcr_a1(5)) &&
          untouched(wcr_wald_pvalue(d, "ecart_log", c("dd_32_ja", "swi_ja"), character(0), FE, "annee",
                                    "surface_ref_ha", B = 99)) &&
          untouched(wcr_cv3(d, "dd_32_ja", B = 99, seed = 5)) &&
          untouched(placebo_size(d, "dd_32_ja", "dep_code", "annee", list(t = function(s) 1), R = 5)))
  if (exists(".Random.seed", globalenv())) rm(".Random.seed", envir = globalenv())
  invisible(with_seed(5, runif(1)))
  check("3b with_seed ne crée pas de graine globale s'il n'y en avait pas", !exists(".Random.seed", globalenv()))
  grab <- function(B) {
    suppressMessages(trace(wcr_pvalue, exit = quote(assign(".t_star", t_star, envir = globalenv())), print = FALSE))
    on.exit(suppressMessages(untrace(wcr_pvalue)))
    wcr_a1(5, B = B)
    .t_star
  }
  check("3b le découpage en lots de 1 000 tirages ne change pas la suite aléatoire (B = 399 contre 1 500)",
        identical(grab(399), grab(1500)[1:399]))

  # Rejeu de R/14 : on exécute la boucle de R/14 (seule la partie aléatoire : permutation puis wcr_pvalue(seed = r))
  # et on compare aux permutations tirées d'un coup après set.seed(123) (R/19, R/22, R/28, R/30).
  field <- tapply(d$dd_32_ja, list(d$dep_code, d$annee), identity)
  R_chk <- 4
  set.seed(123)
  perms_r14 <- vector("list", R_chk)
  for (r in seq_len(R_chk)) {
    perm <- sample(years)
    while (any(perm == years)) perm <- sample(years)
    perms_r14[[r]] <- perm
    s <- d
    s$x_placebo <- field[cbind(d$dep_code, as.character(perm[match(d$annee, years)]))]
    s <- s[!is.na(s$x_placebo), ]
    wcr_pvalue(s, "ecart_log", "x_placebo", "swi_ja", FE, "annee", "surface_ref_ha", B = 399, seed = r)
  }
  set.seed(123)
  perms_replay <- lapply(seq_len(R_chk), function(r) {
    perm <- sample(years)
    while (any(perm == years)) perm <- sample(years)
    perm
  })
  check("3c permutations de R/14 = rejeu de R/19, R/22, R/28 et R/30 (4 premières)", identical(perms_r14, perms_replay))

  # placebo_size tire toutes ses permutations avant les tests : un test qui réinitialise la graine ne les change pas.
  stat <- function(s) { m <- fit(s, c("x_placebo", "swi_ja"), y = "ecart_log"); pnorm(-abs(tstat(m)[["x_placebo"]])) * 2 }
  ps1 <- placebo_size(d, "dd_32_ja", "dep_code", "annee", list(t = stat), R = 20)
  ps2 <- placebo_size(d, "dd_32_ja", "dep_code", "annee", list(t = function(s) { set.seed(1); runif(5); stat(s) }), R = 20)
  check("3d placebo_size insensible aux graines fixées par les tests", identical(ps1, ps2) && ps1$permutations_distinctes == 20)
}

# =====================================================================================================
# 4. Rétrécissement des pentes avec covariance complète (eb_moments ; R/22)
# =====================================================================================================
local({
  set.seed(7)
  k <- 12
  b <- rnorm(k, 0.015, 0.008)
  se <- runif(k, 0.004, 0.012)
  # (a) V diagonale : formules scalaires de DerSimonian-Laird (ancienne version de R/22).
  wi <- 1 / se^2
  mu_fe <- sum(wi * b) / sum(wi)
  Q <- sum(wi * (b - mu_fe)^2)
  tau2 <- max(0, (Q - (k - 1)) / (sum(wi) - sum(wi^2) / sum(wi)))
  mu <- sum(b / (se^2 + tau2)) / sum(1 / (se^2 + tau2))
  e <- eb_moments(b, diag(se^2))
  check("4a eb_moments avec V diagonale = DerSimonian-Laird scalaire",
        abs(e$Q - Q) < 1e-9 && abs(e$tau2 - tau2) < 1e-12 && abs(e$mu - mu) < 1e-12 &&
          max(abs(e$shrunk - (mu + tau2 / (tau2 + se^2) * (b - mu)))) < 1e-12)
  # (b) V corrélée : E[Q] = (k - 1) + tau^2 tr(P), vérifié par simulation (tau connu).
  R <- 0.6 ^ abs(outer(1:k, 1:k, "-"))
  V <- diag(se) %*% R %*% diag(se)
  tau <- 0.006
  L <- t(chol(V + tau^2 * diag(k)))
  Qs <- replicate(4000, eb_moments(as.vector(0.015 + L %*% rnorm(k)), V)$Q)
  Vi <- solve(V); P <- Vi - tcrossprod(Vi %*% rep(1, k)) / sum(Vi)
  expected <- (k - 1) + tau^2 * sum(diag(P))
  check("4b E[Q] = (k - 1) + tau^2 tr(P) avec V corrélée", abs(mean(Qs) / expected - 1) < 0.03,
        sprintf("moyenne %.2f, attendu %.2f", mean(Qs), expected))
})

# =====================================================================================================
# 5. Test d'homogénéité des pentes (R/22) : Wald des écarts de pente = Q généralisé de eb_moments
# =====================================================================================================
local({
  set.seed(11)
  sim <- expand.grid(u = sprintf("u%02d", 1:6), t = 2000:2019, stringsAsFactors = FALSE)
  sim$x <- rnorm(nrow(sim)) + rnorm(20)[sim$t - 1999]
  sim$z <- rnorm(nrow(sim))
  sim$w <- runif(nrow(sim), 0.5, 3)
  sim$y <- 0.02 * sim$x + 0.01 * sim$z + rnorm(20, 0, 0.05)[sim$t - 1999] + rnorm(nrow(sim), 0, 0.05)
  lv <- sort(unique(sim$u))
  for (k in lv[-1]) sim[[paste0("hx_", k)]] <- sim$x * (sim$u == k)
  wr <- wcr_wald_pvalue(sim, "y", paste0("hx_", lv[-1]), c("x", "z"), c("u", "t"), "t", "w", B = 19)
  m <- feols(y ~ x:u + z | u + t, data = sim, weights = ~w)
  k <- grepl("^x:u", names(coef(m)))
  Q0 <- eb_moments(coef(m)[k], vcov(m, cluster = ~t, ssc = cr0)[k, k])$Q
  check("5 Wald WCR des 5 écarts de pente = Q généralisé (même covariance CR0 par période)",
        abs(wr$wald / Q0 - 1) < 1e-8, sprintf("Wald %.6f, Q %.6f", wr$wald, Q0))
})

cat(sprintf("\n%s : %d échec(s)\n", if (n_fail == 0) "SUCCÈS" else "ÉCHEC", n_fail))
quit(status = if (n_fail == 0) 0 else 1)
