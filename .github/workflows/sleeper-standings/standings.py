#!/usr/bin/env python3
"""
Pull a Sleeper fantasy football league and calculate custom standings.

Uses only the Python standard library, so there is nothing to pip install.
Sleeper's API is public and read-only: no API key needed, just your league ID.

Usage:
    python standings.py                   # uses config.json
    python standings.py --config my.json  # use a different config file
    SLEEPER_LEAGUE_ID=123 python standings.py   # env var overrides config
"""
import argparse
import datetime
import json
import os
import statistics
import sys
import time
import urllib.error
import urllib.request
from collections import defaultdict

API = "https://api.sleeper.app/v1"


# --------------------------------------------------------------------------
# Sleeper API
# --------------------------------------------------------------------------
def get(path, retries=3):
    """GET a Sleeper endpoint and return parsed JSON, retrying on hiccups."""
    url = f"{API}{path}"
    req = urllib.request.Request(url, headers={"User-Agent": "sleeper-custom-standings"})
    for attempt in range(1, retries + 1):
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.load(resp)
        except (urllib.error.URLError, TimeoutError) as err:
            if attempt == retries:
                sys.exit(f"Failed to fetch {url}: {err}")
            time.sleep(2 * attempt)


# --------------------------------------------------------------------------
# Config
# --------------------------------------------------------------------------
DEFAULTS = {
    "league_id": "",
    "output_dir": "standings",
    "start_week": None,          # None = league's start week
    "through_week": None,        # None = auto-detect last completed week
    "include_current_week": False,
    "scoring": {
        "h2h_win": 1.0,          # win your actual matchup
        "h2h_tie": 0.5,
        "median_win": 1.0,       # score above the league median that week
        "median_tie": 0.5,
        "all_play_win": 0.0,     # per team you outscored that week (incl. opponent)
        "non_opponent_win": 0.0, # per team you outscored, NOT counting your opponent
        "non_opponent_tie": 0.0, # per non-opponent you tied
        "top_n": 0,              # bonus for finishing top N in weekly scoring
        "top_n_bonus": 0.0,
        "high_score_bonus": 0.0, # bonus for the week's highest score
        "points_for_multiplier": 0.0  # e.g. 0.01 = 1 standings pt per 100 fantasy pts
    },
    "tiebreakers": ["custom_points", "points_for", "all_play_pct", "h2h_wins"]
}


def load_config(path):
    cfg = json.loads(json.dumps(DEFAULTS))  # deep copy
    if os.path.exists(path):
        with open(path) as f:
            user = json.load(f)
        scoring = user.pop("scoring", {})
        cfg.update(user)
        cfg["scoring"].update(scoring)
    cfg["league_id"] = os.environ.get("SLEEPER_LEAGUE_ID") or str(cfg["league_id"] or "")
    if not cfg["league_id"]:
        sys.exit("No league ID. Set league_id in config.json or the SLEEPER_LEAGUE_ID env var.")
    return cfg


# --------------------------------------------------------------------------
# Which weeks count
# --------------------------------------------------------------------------
def weeks_to_score(league, cfg):
    settings = league.get("settings", {})
    first = cfg["start_week"] or settings.get("start_week", 1)
    last_regular = settings.get("playoff_week_start", 15) - 1

    if cfg["through_week"]:
        last = min(int(cfg["through_week"]), last_regular)
    elif league.get("status") == "complete":
        last = last_regular
    else:
        state = get("/state/nfl")
        if str(state.get("season")) != str(league.get("season")):
            last = 0 if league.get("status") in ("pre_draft", "drafting") else last_regular
        elif state.get("season_type") == "pre":
            last = 0
        elif state.get("season_type") == "post":
            last = last_regular
        else:
            current = int(state.get("week") or 0)
            last = current if cfg["include_current_week"] else current - 1
            last = min(last, last_regular)

    return list(range(first, last + 1))


# --------------------------------------------------------------------------
# Standings math
# --------------------------------------------------------------------------
def team_names(users, rosters):
    by_user = {u["user_id"]: u for u in users}
    names = {}
    for r in rosters:
        u = by_user.get(r.get("owner_id"))
        if u:
            team = (u.get("metadata") or {}).get("team_name") or u.get("display_name")
            names[r["roster_id"]] = {"team": team, "manager": u.get("display_name", "")}
        else:
            names[r["roster_id"]] = {"team": f"Team {r['roster_id']}", "manager": "(orphan)"}
    return names


def score_of(entry):
    """Commissioner-overridden custom_points win over the calculated points."""
    pts = entry.get("custom_points")
    if pts is None:
        pts = entry.get("points")
    return float(pts or 0)


def blank_record():
    return {
        "custom_points": 0.0,
        "h2h_wins": 0, "h2h_losses": 0, "h2h_ties": 0,
        "median_wins": 0, "median_losses": 0, "median_ties": 0,
        "all_play_wins": 0, "all_play_losses": 0, "all_play_ties": 0,
        "non_opp_wins": 0, "non_opp_losses": 0, "non_opp_ties": 0,
        "top_n_finishes": 0, "high_scores": 0,
        "points_for": 0.0, "points_against": 0.0,
        "weekly": []
    }


def compute(league_id, weeks, roster_ids, sc):
    rec = {rid: blank_record() for rid in roster_ids}
    weeks_played = []

    for wk in weeks:
        matchups = get(f"/league/{league_id}/matchups/{wk}") or []
        scores = {m["roster_id"]: score_of(m) for m in matchups if m["roster_id"] in rec}
        if not scores or not any(scores.values()):
            continue  # week not played yet
        weeks_played.append(wk)

        median = statistics.median(scores.values())
        high = max(scores.values())
        ranked = sorted(scores.values(), reverse=True)
        top_cut = ranked[sc["top_n"] - 1] if sc["top_n"] and sc["top_n"] <= len(ranked) else None

        # Group actual head-to-head pairings
        pairs = defaultdict(list)
        for m in matchups:
            if m.get("matchup_id") is not None and m["roster_id"] in rec:
                pairs[m["matchup_id"]].append(m["roster_id"])
        opponent = {}
        for ids in pairs.values():
            if len(ids) == 2:
                a, b = ids
                opponent[a], opponent[b] = b, a

        for rid, pts in scores.items():
            r = rec[rid]
            gained = 0.0
            r["points_for"] += pts

            # Head-to-head
            opp = opponent.get(rid)
            result = None
            if opp is not None:
                opp_pts = scores.get(opp, 0.0)
                r["points_against"] += opp_pts
                if pts > opp_pts:
                    r["h2h_wins"] += 1; gained += sc["h2h_win"]; result = "W"
                elif pts < opp_pts:
                    r["h2h_losses"] += 1; result = "L"
                else:
                    r["h2h_ties"] += 1; gained += sc["h2h_tie"]; result = "T"

            # Versus the median
            if pts > median:
                r["median_wins"] += 1; gained += sc["median_win"]
            elif pts < median:
                r["median_losses"] += 1
            else:
                r["median_ties"] += 1; gained += sc["median_tie"]

            # All-play (your score vs. every other team that week)
            others = [p for o, p in scores.items() if o != rid]
            w = sum(pts > p for p in others)
            t = sum(pts == p for p in others)
            r["all_play_wins"] += w
            r["all_play_ties"] += t
            r["all_play_losses"] += len(others) - w - t
            gained += w * sc["all_play_win"]

            # Non-opponent all-play (everyone except this week's opponent)
            non_opp = [p for o, p in scores.items() if o not in (rid, opp)]
            nw = sum(pts > p for p in non_opp)
            nt = sum(pts == p for p in non_opp)
            r["non_opp_wins"] += nw
            r["non_opp_ties"] += nt
            r["non_opp_losses"] += len(non_opp) - nw - nt
            gained += nw * sc["non_opponent_win"] + nt * sc["non_opponent_tie"]

            # Bonuses
            if top_cut is not None and pts >= top_cut:
                r["top_n_finishes"] += 1; gained += sc["top_n_bonus"]
            if pts == high:
                r["high_scores"] += 1; gained += sc["high_score_bonus"]
            gained += pts * sc["points_for_multiplier"]

            r["custom_points"] += gained
            r["weekly"].append({"week": wk, "points": round(pts, 2), "result": result,
                                "median": round(median, 2), "standings_points": round(gained, 3)})

    return rec, weeks_played


def rank(rec, tiebreakers):
    def all_play_pct(r):
        games = r["all_play_wins"] + r["all_play_losses"] + r["all_play_ties"]
        return (r["all_play_wins"] + 0.5 * r["all_play_ties"]) / games if games else 0.0

    for r in rec.values():
        r["all_play_pct"] = round(all_play_pct(r), 4)
        r["custom_points"] = round(r["custom_points"], 3)
        r["points_for"] = round(r["points_for"], 2)
        r["points_against"] = round(r["points_against"], 2)

    return sorted(rec.items(), key=lambda kv: tuple(kv[1][t] for t in tiebreakers), reverse=True)


# --------------------------------------------------------------------------
# Output
# --------------------------------------------------------------------------
def fmt_rec(w, l, t):
    return f"{w}-{l}" + (f"-{t}" if t else "")


def write_outputs(cfg, league, names, ordered, weeks_played):
    out = cfg["output_dir"]
    os.makedirs(out, exist_ok=True)
    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    through = f"Week {weeks_played[-1]}" if weeks_played else "no completed weeks yet"

    rows = []
    for place, (rid, r) in enumerate(ordered, 1):
        rows.append({"rank": place, "roster_id": rid, **names[rid], **r})

    with open(os.path.join(out, "standings.json"), "w") as f:
        json.dump({"league": league.get("name"), "season": league.get("season"),
                   "weeks": weeks_played, "updated": now,
                   "scoring": cfg["scoring"], "standings": rows}, f, indent=2)

    sc = cfg["scoring"]
    show_median = bool(sc["median_win"] or sc["median_tie"])
    show_non_opp = bool(sc["non_opponent_win"] or sc["non_opponent_tie"])

    header = ["#", "Team", "Manager", "VP", "H2H"]
    align = ["---", "------", "---------", "---:", ":---:"]
    if show_median:
        header += ["vs Median", "Combined"]; align += [":---:", ":---:"]
    if show_non_opp:
        header += ["Non-Opp"]; align += [":---:"]
    header += ["All-Play", "AP %", "PF", "PA"]
    align += [":---:", "---:", "---:", "---:"]

    lines = [
        f"# {league.get('name', 'League')} — {league.get('season')} Custom Standings",
        "",
        f"Through **{through}** · updated {now}",
        "",
        "| " + " | ".join(header) + " |",
        "|" + "|".join(align) + "|",
    ]
    for row in rows:
        cells = [str(row["rank"]), row["team"], row["manager"], f"{row['custom_points']:g}",
                 fmt_rec(row["h2h_wins"], row["h2h_losses"], row["h2h_ties"])]
        if show_median:
            cells.append(fmt_rec(row["median_wins"], row["median_losses"], row["median_ties"]))
            cells.append(fmt_rec(row["h2h_wins"] + row["median_wins"],
                                 row["h2h_losses"] + row["median_losses"],
                                 row["h2h_ties"] + row["median_ties"]))
        if show_non_opp:
            cells.append(fmt_rec(row["non_opp_wins"], row["non_opp_losses"], row["non_opp_ties"]))
        cells += [fmt_rec(row["all_play_wins"], row["all_play_losses"], row["all_play_ties"]),
                  f"{row['all_play_pct']:.3f}", f"{row['points_for']:.2f}", f"{row['points_against']:.2f}"]
        lines.append("| " + " | ".join(cells) + " |")

    rules = [f"- {k.replace('_', ' ')}: {v}" for k, v in sc.items() if v]
    lines += ["", "## Scoring rules", "", *rules,
              "", f"Tiebreakers, in order: {', '.join(cfg['tiebreakers'])}", ""]

    with open(os.path.join(out, "STANDINGS.md"), "w") as f:
        f.write("\n".join(lines))

    print("\n".join(lines))


# --------------------------------------------------------------------------
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="config.json")
    cfg = load_config(ap.parse_args().config)

    lid = cfg["league_id"]
    league = get(f"/league/{lid}")
    if not league:
        sys.exit(f"League {lid} not found. Double-check the ID.")
    users = get(f"/league/{lid}/users") or []
    rosters = get(f"/league/{lid}/rosters") or []

    names = team_names(users, rosters)
    weeks = weeks_to_score(league, cfg)
    rec, played = compute(lid, weeks, [r["roster_id"] for r in rosters], cfg["scoring"])
    ordered = rank(rec, cfg["tiebreakers"])
    write_outputs(cfg, league, names, ordered, played)


if __name__ == "__main__":
    main()
