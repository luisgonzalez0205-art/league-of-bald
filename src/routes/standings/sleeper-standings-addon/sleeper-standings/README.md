# Sleeper Custom Standings

Pulls your league from the public [Sleeper API](https://docs.sleeper.com/) and ranks
teams using your own rules (head-to-head + median wins, all-play, weekly bonuses, and
so on). A GitHub Action runs it every week and commits the results to
`sleeper-standings/standings/STANDINGS.md` (renders as a table on GitHub) and `sleeper-standings/standings/standings.json`.

No API key or dependencies are needed. Python 3.8+ standard library only.

## Setup

1. **Find your league ID.** Open the league on sleeper.com; it's the long number in the
   URL: `sleeper.com/leagues/<LEAGUE_ID>/...`
2. **Add to your repo:** the `sleeper-standings/` folder goes at the repo root, and
   `sleeper-standings.yml` goes in `.github/workflows/` at the repo root.
3. **Set the league ID**, either by editing `league_id` in `config.json`, or by adding a
   repository variable named `SLEEPER_LEAGUE_ID` (Settings → Secrets and variables →
   Actions → Variables).
4. **Allow the workflow to push:** Settings → Actions → General → Workflow permissions →
   "Read and write permissions."
5. **Run it once by hand:** Actions tab → "Update Sleeper standings" → Run workflow.
   After that it runs every Wednesday morning automatically.

To run locally: `cd sleeper-standings && python standings.py`

## Scoring (`config.json`)

Every week, each team earns standings points:

| Setting | Meaning |
|---|---|
| `h2h_win` / `h2h_tie` | Points for winning or tying your actual matchup |
| `median_win` / `median_tie` | Points for scoring above the league median that week |
| `all_play_win` | Points per team you outscored that week (including your opponent) |
| `non_opponent_win` / `non_opponent_tie` | Points per team you outscored or tied, not counting your opponent |
| `top_n` + `top_n_bonus` | Bonus for finishing in the week's top N scorers |
| `high_score_bonus` | Bonus for the week's highest score |
| `points_for_multiplier` | Standings points per fantasy point (e.g. `0.01` = 1 pt per 100) |

Set anything to `0` to turn it off. `tiebreakers` is applied in order and can use any
field in `standings.json`, like `custom_points`, `points_for`, `all_play_pct`,
`h2h_wins`, `median_wins`, `high_scores`, or `points_against`.

Other options:
- `through_week`: force the standings through a specific week (useful for re-running
  past weeks or if auto-detection is off).
- `include_current_week`: `true` counts the in-progress week as live scores.
- `start_week`: skip early weeks.

Only regular-season weeks are counted (it stops before your league's playoff start week).

## Notes

- If your league already has Sleeper's built-in "extra win vs. median" setting on,
  Sleeper's own W-L will already include it. This script calculates everything from
  weekly scores itself, so its numbers don't depend on that setting.
- Commissioner score overrides (`custom_points` in Sleeper) are respected.
- For stat corrections, add a second cron line (e.g. Friday) to the workflow so the
  standings refresh after late adjustments.
