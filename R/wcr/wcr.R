# wcr.R — wild cluster bootstrap restreint (WCR) pour un modèle à effets fixes estimé avec fixest,
# et simulation placebo de la taille d'un test. Fichier autonome : seule dépendance, le paquet fixest.
#
# Pourquoi : dans un panel où les chocs sont communs à toutes les unités une même période (météo,
# prix, politique nationale), les erreurs-types usuelles (cluster par unité, Conley) peuvent rejeter
# à tort bien plus souvent que le niveau nominal. Avec peu de grappes, le bootstrap par période est
# en général plus fiable s'il est restreint et utilise les poids de Webb (Cameron, Gelbach & Miller
# 2008 ; Webb 2023), sans garantie avec très peu de grappes ou des grappes déséquilibrées. Ce fichier
# fournit ce test et un moyen de VÉRIFIER sa taille sur vos propres données (placebo_size).
#
# Principe du WCR (Frisch-Waugh-Lovell, MCO pondérés) :
#   1. on retire les effets fixes de y, x et des autres régresseurs z (fixest::demean, pondéré) ;
#   2. on régresse y et x sur z : résidus y_t et x_t ;
#   3. sous H0 (beta = 0), le résidu restreint est y_t ; on tire y* = y_t * v_g, v_g étant un poids
#      de Webb par grappe ;
#   4. y* n'est plus orthogonal aux effets fixes ni à z (v_g varie d'une grappe à l'autre) : on le
#      RE-PROJETTE (demean + résidu sur z) à chaque tirage, comme si l'on réestimait le modèle complet ;
#   5. on compare t = beta / se(grappes) à la distribution des t*.
# Le facteur de petit échantillon du CR1 étant identique pour t et t*, il est omis (il se simplifie).
# Démoyennage : tolérance DEMEAN_TOL (1e-12) au lieu de 1e-6 par défaut dans fixest, pour que la re-projection
# coïncide avec une réestimation complète à la précision machine (contrôle : tests/test_r_inference.R).
# Graine : les tirages utilisent `seed` sans toucher à l'état du générateur de l'appelant (with_seed).
#
# Fonctions :
#   wcr_pvalue()      test d'un coefficient (p bilatérale, unilatérale à gauche et à droite)
#   wcr_wald_pvalue() test joint de plusieurs coefficients (Wald)
#   placebo_size()    taille empirique d'un test : exposition réelle, périodes permutées
# Exemple autonome sur données simulées : R/wcr/exemple.R ; mode d'emploi : R/wcr/README.md.

DEMEAN_TOL <- 1e-12

# Évalue `expr` après set.seed(seed), puis restaure l'état du générateur aléatoire de l'appelant : appeler
# wcr_pvalue() dans une boucle de simulation ne modifie donc pas la suite des tirages de la boucle.
with_seed <- function(seed, expr) {
  old <- if (exists(".Random.seed", envir = globalenv())) get(".Random.seed", envir = globalenv()) else NULL
  on.exit(if (is.null(old)) rm(".Random.seed", envir = globalenv())
          else assign(".Random.seed", old, envir = globalenv()))
  set.seed(seed)
  expr
}

webb_weights <- function(G) {
  sample(c(-sqrt(3 / 2), -1, -sqrt(1 / 2), sqrt(1 / 2), 1, sqrt(3 / 2)), G, replace = TRUE)
}

# data     : data.frame ; y, x : noms de la variable expliquée et du régresseur testé ;
# z        : autres régresseurs (vecteur de noms, éventuellement vide) ; fe : noms des effets fixes ;
# cluster  : nom de la variable de grappe ; weights : nom de la colonne de poids (mettre une colonne
#            de 1 pour des MCO non pondérés) ; B : nombre de tirages ; seed : graine.
# Retour   : t observé, p bilatérale (symétrique), p_left (H1 : beta < 0), p_right (H1 : beta > 0),
#            nombre de grappes G et B. p est la part des B tirages au moins aussi extrêmes que t,
#            sans la convention (1 + #)/(B + 1) : p = 0 signifie qu'aucun tirage ne l'atteint, à lire
#            p < 1/B (ex. p < 1/9 999).
wcr_pvalue <- function(data, y, x, z, fe, cluster, weights, B = 9999, seed = 123) {
  w <- data[[weights]]
  X <- as.matrix(data[, c(y, x, z)])
  dm <- fixest::demean(X, data[, fe], weights = w, tol = DEMEAN_TOL)
  zt <- dm[, z, drop = FALSE]
  resid_on_z <- function(v) {
    if (ncol(zt) == 0) return(v)
    v - zt %*% solve(crossprod(zt, w * zt), crossprod(zt, w * v))
  }
  y_t <- as.vector(resid_on_z(dm[, y]))
  x_t <- as.vector(resid_on_z(dm[, x]))
  g <- as.integer(factor(data[[cluster]]))
  G <- max(g)
  sxx <- sum(w * x_t^2)

  # Statistiques t pour une matrice de variables expliquées déjà projetées (une colonne par tirage).
  t_stats <- function(Y) {
    b <- colSums(w * x_t * Y) / sxx
    E <- Y - outer(x_t, b)
    score <- rowsum(w * x_t * E, g)
    b / sqrt(colSums(score^2) / sxx^2)
  }
  t0 <- t_stats(matrix(y_t))
  t_star <- with_seed(seed, {
    t_star <- numeric(0)
    for (start in seq(1, B, by = 1000)) {
      n_b <- min(1000, B - start + 1)
      V <- vapply(seq_len(n_b), function(i) webb_weights(G)[g], numeric(length(g)))
      Ystar <- fixest::demean(y_t * V, data[, fe], weights = w, tol = DEMEAN_TOL)  # re-projection sur les effets fixes
      Ystar <- resid_on_z(Ystar)                                                   # puis sur les autres régresseurs
      t_star <- c(t_star, t_stats(Ystar))
    }
    t_star
  })
  list(t = t0, p = mean(abs(t_star) >= abs(t0)), p_left = mean(t_star <= t0),
       p_right = mean(t_star >= t0), G = G, B = B)
}


# Version jointe : test de Wald de H0 : (beta_1, ..., beta_k) = 0 pour plusieurs régresseurs `xs`
# (ex. une variable et son carré, ou des écarts de pente entre périodes). Statistique W = b' V^{-1} b,
# V en grappes (CR0), même principe restreint.
wcr_wald_pvalue <- function(data, y, xs, z, fe, cluster, weights, B = 9999, seed = 123) {
  w <- data[[weights]]
  dm <- fixest::demean(as.matrix(data[, c(y, xs, z)]), data[, fe], weights = w, tol = DEMEAN_TOL)
  zt <- dm[, z, drop = FALSE]
  resid_on_z <- function(v) {
    if (ncol(zt) == 0) return(v)
    v - zt %*% solve(crossprod(zt, w * zt), crossprod(zt, w * v))
  }
  y_t <- as.vector(resid_on_z(dm[, y]))
  X_t <- resid_on_z(dm[, xs, drop = FALSE])
  g <- as.integer(factor(data[[cluster]]))
  G <- max(g)
  A_inv <- solve(crossprod(X_t, w * X_t))

  wald <- function(yy) {
    b <- A_inv %*% crossprod(X_t, w * yy)
    e <- yy - X_t %*% b
    S <- rowsum(w * X_t * as.vector(e), g)      # scores par grappe (G × k)
    V <- A_inv %*% crossprod(S) %*% A_inv
    as.numeric(t(b) %*% solve(V, b))
  }
  w0 <- wald(y_t)
  w_star <- with_seed(seed, vapply(seq_len(B), function(i) {
    ys <- fixest::demean(matrix(y_t * webb_weights(G)[g]), data[, fe], weights = w, tol = DEMEAN_TOL)
    wald(as.vector(resid_on_z(ys)))
  }, numeric(1)))
  list(wald = w0, p = mean(w_star >= w0), G = G, B = B)
}


# Taille empirique d'un test sous H0, par placebo : on remplace l'exposition `x` par le champ RÉEL
# d'exposition d'une autre période (dérangement des périodes : aucune ne reste à sa place). Le placebo
# conserve la structure spatiale de l'exposition mais n'a, par construction, aucun lien avec y.
# `tests` : liste nommée de fonctions(sim) -> p-valeur, où sim contient la colonne `x_placebo`.
# Retour : taux de rejet au seuil `alpha` pour chaque test (la taille nominale est alpha).
# L'erreur-type de Monte-Carlo de la taille vaut environ sqrt(alpha (1 - alpha) / R) : 1,3 point pour
# R = 300 à 5 % (intervalle à 95 % : ±2,5 points).
# Limites : y reste fixe et les R placebos ne sont que des permutations des T champs observés, donc
# peu nombreux et non indépendants quand T est petit ; la dépendance temporelle de y au sein d'une
# unité n'est donc pas testée. Le test placebo retire la vraie exposition (la passer dans `tests` si
# on veut la garder) : son effet éventuel reste dans l'erreur. Le diagnostic est indicatif, pas une
# preuve.
placebo_size <- function(data, x, unit, period, tests, R = 300, alpha = 0.05, seed = 123) {
  periods <- sort(unique(data[[period]]))
  field <- tapply(data[[x]], list(data[[unit]], data[[period]]), identity)
  # Toutes les permutations sont tirées AVANT les tests, sous une graine locale : un test qui fixe lui-même
  # une graine ne modifie pas la suite des permutations.
  perms <- with_seed(seed, lapply(seq_len(R), function(r) {
    perm <- sample(periods)
    while (any(perm == periods)) perm <- sample(periods)
    perm
  }))
  rej <- setNames(numeric(length(tests)), names(tests))
  for (r in seq_len(R)) {
    perm <- perms[[r]]
    sim <- data
    sim$x_placebo <- field[cbind(as.character(data[[unit]]),
                                 as.character(perm[match(data[[period]], periods)]))]
    sim <- sim[!is.na(sim$x_placebo), ]     # unité absente la période permutée (panel non équilibré)
    p <- vapply(tests, function(f) f(sim), numeric(1))
    rej <- rej + (p < alpha)
  }
  data.frame(test = names(tests), taille = as.numeric(rej) / R, R = R, alpha = alpha,
             permutations_distinctes = length(unique(vapply(perms, paste, "", collapse = "-"))), row.names = NULL)
}
