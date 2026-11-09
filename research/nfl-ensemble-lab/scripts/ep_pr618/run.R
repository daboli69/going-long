lib <- "C:/Users/travi/OneDrive/Documents/ChatGPT/GOING/research/nfl-ensemble-lab/data/cache/rlib"
.libPaths(c(lib, .libPaths()))
suppressMessages(library(nflfastR))
print(exists("get_kickoff_values", envir=asNamespace("nflfastR")))
args <- commandArgs(trailingOnly=TRUE)
season <- args[1]
pbp <- read.csv(paste0("data/cache/pbp", season, "_for_r.csv"), stringsAsFactors=FALSE, na.strings=c("NA",""))
pbp <- pbp[order(pbp$game_id, pbp$play_id),]
pbp <- nflfastR:::make_model_mutations(pbp)
ch <- function(x) ifelse(is.na(x), "", x)
pbp$field_goal_made <- as.numeric(ch(pbp$field_goal_result) == "made")
for (r in c("good","failed","blocked","aborted")) pbp[[paste0("extra_point_", r)]] <- as.numeric(ch(pbp$extra_point_result) == r)
two_ok <- ch(pbp$two_point_conv_result) == "success"; two_no <- ch(pbp$two_point_conv_result) == "failure"
isp <- !is.na(pbp$pass_attempt) & pbp$pass_attempt == 1; isr <- !is.na(pbp$rush_attempt) & pbp$rush_attempt == 1
pbp$two_point_pass_good <- as.numeric(two_ok & isp); pbp$two_point_pass_reception_good <- pbp$two_point_pass_good
pbp$two_point_pass_failed <- as.numeric(two_no & isp); pbp$two_point_pass_reception_failed <- pbp$two_point_pass_failed
pbp$two_point_rush_good <- as.numeric(two_ok & isr); pbp$two_point_rush_failed <- as.numeric(two_no & isr)
pbp$safety_team <- ifelse(!is.na(pbp$safety) & pbp$safety == 1, pbp$defteam, NA)
pbp$end_game <- as.numeric(grepl("END GAME", ch(pbp$desc)))
old <- pbp[, c("game_id","play_id","ep","epa")]
drop <- c("no_score_prob","opp_fg_prob","opp_safety_prob","opp_td_prob","fg_prob","safety_prob","td_prob","extra_point_prob","two_point_conversion_prob","ep","epa","total_home_epa","total_away_epa","total_home_rush_epa","total_away_rush_epa","total_home_pass_epa","total_away_pass_epa","air_epa","yac_epa","comp_air_epa","comp_yac_epa","xyac_epa")
pbp <- pbp[, !(names(pbp) %in% drop)]
res <- nflfastR:::add_ep_variables(pbp)
out <- res[, c("game_id","play_id","ep","epa")]
names(out) <- c("game_id","play_id","ep_pr","epa_pr")
write.csv(merge(old,out,by=c("game_id","play_id")), paste0("data/cache/ep_pr618_", season, ".csv"), row.names=FALSE)
cat("done", nrow(out), "\n")
