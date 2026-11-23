# PlasmaPicks

NBA player-prop engine. `scripts/update.py` runs on a schedule (`.github/workflows/update.yml`):
hoopR box scores → season stats, team defense, defense by position, teammate splits;
SportsGameOdds (free tier) → games, spreads, totals and props from DraftKings (main), FanDuel, Caesars, ESPN BET.
It writes the data into `index.html` and `data/`, and refuses to publish if a game is missing its spread or total.

Secret needed: `ODDS_API_KEY` (Settings › Secrets and variables › Actions).
Manual run: Actions › Update slate › Run workflow.
