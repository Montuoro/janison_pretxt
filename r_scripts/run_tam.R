#!/usr/bin/env Rscript
# TAM analysis: item params, fit, WLE, reliability
# Usage: Rscript run_tam.R <input_csv> <output_dir>

args <- commandArgs(trailingOnly = TRUE)
if (length(args) < 2) {
  stop("Usage: Rscript run_tam.R <input_csv> <output_dir>")
}

input_csv <- args[1]
output_dir <- args[2]

suppressPackageStartupMessages(library(TAM))
suppressPackageStartupMessages(library(jsonlite))

# Read data
resp <- read.csv(input_csv, check.names = FALSE)
resp <- as.matrix(resp)

# Ensure numeric
resp <- apply(resp, 2, as.numeric)

# Remove items with zero variance
item_vars <- apply(resp, 2, var, na.rm = TRUE)
valid_items <- item_vars > 0
if (sum(valid_items) < 2) {
  stop("Fewer than 2 items with non-zero variance.")
}
resp <- resp[, valid_items]

# Run TAM MML
mod <- tam.mml(resp, verbose = FALSE)

# Item parameters
item_params <- data.frame(
  item = colnames(resp),
  xsi = mod$xsi$xsi,
  se_xsi = mod$xsi$se.xsi
)

# Fit statistics
fit <- tam.fit(mod, progress = FALSE)
fit_stats <- data.frame(
  item = colnames(resp),
  Infit = fit$itemfit$Infit,
  Infit_t = fit$itemfit$Infit_t,
  Outfit = fit$itemfit$Outfit,
  Outfit_t = fit$itemfit$Outfit_t
)

# Person parameters (WLE)
wle <- tam.wle(mod, progress = FALSE)
person_params <- data.frame(
  theta = wle$theta,
  se = wle$error
)

# Reliability
eap_rel <- mod$EAP.rel
wle_rel <- WLErel(wle$theta, wle$error)

# Cronbach's alpha (simple)
k <- ncol(resp)
item_var_sum <- sum(apply(resp, 2, var, na.rm = TRUE))
total_var <- var(rowSums(resp, na.rm = TRUE))
cronbach_alpha <- (k / (k - 1)) * (1 - item_var_sum / total_var)

# Assemble results
results <- list(
  item_params = item_params,
  fit_stats = fit_stats,
  person_params = person_params,
  reliability = list(
    eap_rel = eap_rel,
    wle_rel = wle_rel,
    cronbach_alpha = cronbach_alpha
  ),
  n_items = ncol(resp),
  n_persons = nrow(resp)
)

# Write JSON
output_file <- file.path(output_dir, "tam_results.json")
write(toJSON(results, auto_unbox = TRUE, pretty = TRUE, na = "null"), output_file)

cat("TAM analysis complete. Results written to:", output_file, "\n")
