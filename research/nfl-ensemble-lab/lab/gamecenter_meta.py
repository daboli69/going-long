"""Team names, colors, stat names and the plain-English glossary. Pure data; no Streamlit, so both dashboards share it."""

TEAM_NAMES = {
    "ARI": "Arizona Cardinals", "ATL": "Atlanta Falcons", "BAL": "Baltimore Ravens", "BUF": "Buffalo Bills", "CAR": "Carolina Panthers",
    "CHI": "Chicago Bears", "CIN": "Cincinnati Bengals", "CLE": "Cleveland Browns", "DAL": "Dallas Cowboys", "DEN": "Denver Broncos",
    "DET": "Detroit Lions", "GB": "Green Bay Packers", "HOU": "Houston Texans", "IND": "Indianapolis Colts", "JAX": "Jacksonville Jaguars",
    "KC": "Kansas City Chiefs", "LA": "Los Angeles Rams", "LAC": "Los Angeles Chargers", "LV": "Las Vegas Raiders", "MIA": "Miami Dolphins",
    "MIN": "Minnesota Vikings", "NE": "New England Patriots", "NO": "New Orleans Saints", "NYG": "New York Giants", "NYJ": "New York Jets",
    "PHI": "Philadelphia Eagles", "PIT": "Pittsburgh Steelers", "SEA": "Seattle Seahawks", "SF": "San Francisco 49ers", "TB": "Tampa Bay Buccaneers",
    "TEN": "Tennessee Titans", "WAS": "Washington Commanders",
}
# Display colors tuned for a dark background (team primary colors, lightened where the real color would vanish).
TEAM_COLORS = {
    "ARI": "#c2334f", "ATL": "#d12f46", "BAL": "#7a5ce0", "BUF": "#2f6fed", "CAR": "#1b9bd8", "CHI": "#e0602b", "CIN": "#fb4f14", "CLE": "#ff6a2b",
    "DAL": "#4a7bd8", "DEN": "#fb6b1d", "DET": "#3b9ee6", "GB": "#2e9a55", "HOU": "#e0334c", "IND": "#3b82d6", "JAX": "#17a3a5", "KC": "#e31837",
    "LA": "#4f7cff", "LAC": "#3aa7e8", "LV": "#a5acaf", "MIA": "#1fb5b0", "MIN": "#7b4fc4", "NE": "#4a73d6", "NO": "#d3bc8d", "NYG": "#3b6fd4",
    "NYJ": "#2e9d6e", "PHI": "#2aa08d", "PIT": "#ffb612", "SEA": "#69be28", "SF": "#d4283f", "TB": "#e0343a", "TEN": "#4b92db", "WAS": "#c2455f",
}
STAT_PLAIN = {"pass_yds": "Passing yards", "rush_yds": "Rushing yards", "rec_yds": "Receiving yards", "rec": "Catches"}

# Plain-English glossary used by the guide tab and by help text across the dashboard.
GLOSSARY = [
    ("Win chance", "How likely a team is to win, as a percentage. 60% means that if this exact game were played 10 times, that team would win about 6 of them."),
    ("Spread", "The number of points the favorite is expected to win by. \"Bills -4.5\" means Buffalo is expected to win by about 4 or 5 points. If Buffalo wins by 7, they beat the spread."),
    ("Total (over/under)", "The combined points both teams are expected to score. A total of 47.5 means the market expects about 47 or 48 points in the whole game."),
    ("Betting market (Kalshi)", "Kalshi is an exchange where real people trade on game outcomes. Its prices are the best public guess of what will happen, because people put money behind them. We read its prices but never trade."),
    ("Elo rating", "A simple, well-known team-strength score. A team goes up when it wins and down when it loses, more so against strong opponents. It turns out to be hard to beat."),
    ("Our model", "This lab's own forecast, built from 15 years of NFL results and play-by-play data. Honest summary: it is good, but so far it has not been more accurate than the betting market."),
    ("Projection", "The most typical result we expect for a player or team. It is a middle estimate, not a promise: real games land above or below it."),
    ("Likely range", "The band where we expect the real number to land 8 times out of 10. A wide band means we are less sure."),
    ("No strong opinion", "Our model and the market agree closely, so we simply go with the market. This is the usual case."),
    ("Lean", "A spot where our model disagrees with the market by a meaningful amount. In our tests, leans have not beaten the market, so treat them as something to think about, not advice."),
    ("Out / Doubtful / Questionable", "Injury report labels. Out = will not play. Doubtful = very unlikely to play (about 1 in 20). Questionable = could go either way."),
    ("ESPN FPI", "ESPN's own game forecast, shown for comparison when it is available."),
]
