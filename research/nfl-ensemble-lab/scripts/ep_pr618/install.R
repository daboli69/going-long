lib <- "C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/data/cache/rlib"
.libPaths(c(lib, .libPaths()))
options(repos=c(CRAN="https://cloud.r-project.org"))
print(rownames(installed.packages(lib.loc=lib))[1:5])
if (!requireNamespace("fastrmodels", quietly=TRUE)) remotes::install_github("nflverse/fastrmodels", lib=lib, upgrade="never", INSTALL_opts="--no-multiarch")
if (!requireNamespace("nflfastR", quietly=TRUE)) remotes::install_github("nflverse/nflfastR#618", lib=lib, upgrade="never", dependencies=TRUE)
print(packageVersion("nflfastR")); print(packageVersion("fastrmodels"))
