#!/usr/bin/env python3
"""
Shoulda Coulda Woulda + Performance Awards for a Sleeper league.

Writes two files for the website (default folder: ../static):
  shoulda-coulda-woulda.json   alternate records if each team had another team's schedule
  performance-awards.json      weekly awards for every completed week + season tallies

Reuses the league ID and settings from config.json (same as standings.py).
"""
import datetime
import json
import os
import sys
import urllib.request
from collections import Counter, defaultdict

import standings as S

POSITIONS = ["QB", "RB", "WR", "TE", "K", "DEF"]

# Which player positions can fill each Sleeper lineup slot
SLOT_ELIGIBLE = {
    "QB": {"QB"}, "RB": {"RB"}, "WR": {"WR"}, "TE": {"TE"}, "K": {"K"}, "DEF": {"DEF"},
    "FLEX": {"RB", "WR", "TE"},
    "WRRB_FLEX": {"RB", "WR"},
    "REC_FLEX": {"WR", "TE"},
    "SUPER_FLEX": {"QB", "RB", "WR", "TE"},
    "DL": {"DL", "DE", "DT"}, "LB": {"LB"}, "DB": {"DB", "CB", "S"},
    "IDP_FLEX": {"DL", "DE", "DT", "LB", "DB", "CB", "S"},
}
NOT_STARTING = {"BN", "IR", "TAXI"}

AWARDS = [
    ("money_shot", "💰", "The Money Shot", "Highest-scoring starter of the week"),
    ("taco", "🌮", "The Taco", "Lowest team score of the week"),
    ("best_manager", "🔥", "Best Manager", "Highest share of their best possible lineup"),
    ("worst_manager", "🤔", "Worst Manager", "Lowest share of their best possible lineup"),
    ("blowout", "😂", "Biggest Blowout", "Largest margin of victory"),
    ("narrow", "😱", "Narrow Victory", "Smallest margin of victory"),
    ("overachiever", "🤓", "Overachiever", "Beat their projection by the most"),
    ("below", "💀", "Below Expectation", "Fell furthest short of their projection"),
    *[(f"best_{p.lower()}", "⭐", f"Best {p}", f"Top-scoring starting {p}") for p in POSITIONS],
    *[(f"bench_{p.lower()}", "👀", f"Benchwarmer {p}", f"Top-scoring benched {p}") for p in POSITIONS],
    ("bench_points", "🍆", "The Ron Jeremy Performance Award", "Most points left on the bench"),
]
AWARD_INFO = {k: {"emoji": e, "title": t, "description": d} for k, e, t, d in AWARDS}


def get_url(url):
    """Fetch any URL; returns None instead of exiting (used for optional data)."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "sleeper-custom-standings"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            return json.load(resp)
    except Exception as err:  # noqa: BLE001
        print(f"Note: couldn't fetch {url} ({err})")
        return None


# --------------------------------------------------------------------------
# Players and projections
# --------------------------------------------------------------------------
def load_players():
    raw = S.get("/players/nfl") or {}
    players = {}
    for pid, p in raw.items():
        pos = p.get("position") or ""
        fpos = set(p.get("fantasy_positions") or ([pos] if pos else []))
        if pos == "DEF":
            name = f"{p.get('first_name', '')} {p.get('last_name', '')}".strip() or pid
            image = f"https://sleepercdn.com/images/team_logos/nfl/{pid.lower()}.png"
        else:
            name = p.get("full_name") or f"{p.get('first_name', '')} {p.get('last_name', '')}".strip()
            image = f"https://sleepercdn.com/content/nfl/players/thumb/{pid}.jpg"
        players[pid] = {"name": name or pid, "position": pos, "eligible": fpos,
                        "nfl_team": p.get("team"), "image": image}
    return players


def player_info(players, pid):
    p = players.get(pid)
    if not p:
        return {"id": pid, "name": pid, "position": "", "nfl_team": None, "image": None}
    return {"id": pid, "name": p["name"], "position": p["position"],
            "nfl_team": p["nfl_team"], "image": p["image"]}


def projection_key(league):
    rec = (league.get("scoring_settings") or {}).get("rec", 0) or 0
    return "pts_ppr" if rec >= 1 else "pts_half_ppr" if rec >= 0.5 else "pts_std"


def load_projections(season, week, key):
    """Sleeper's projections endpoint isn't officially documented; if it fails,
    the projection awards are skipped for that week."""
    pos_q = "".join(f"&position[]={p}" for p in POSITIONS)
    data = get_url(f"https://api.sleeper.com/projections/nfl/{season}/{week}?season_type=regular{pos_q}")
    out = {}
    if isinstance(data, list):
        for row in data:
            pid = row.get("player_id")
            stats = row.get("stats") or {}
            if pid and stats.get(key) is not None:
                out[str(pid)] = float(stats[key])
    elif isinstance(data, dict):
        for pid, stats in data.items():
            if isinstance(stats, dict) and stats.get(key) is not None:
                out[str(pid)] = float(stats[key])
    return out


# --------------------------------------------------------------------------
# Lineup math
# --------------------------------------------------------------------------
def optimal_points(slots, player_pts, players):
    """Best possible lineup: fill the most restrictive slots first."""
    avail = dict(player_pts)
    total = 0.0
    for slot in sorted(slots, key=lambda s: len(SLOT_ELIGIBLE.get(s, {s}))):
        elig = SLOT_ELIGIBLE.get(slot, {slot})
        best = None
        for pid, pts in avail.items():
            if players.get(pid, {}).get("eligible", set()) & elig:
                if best is None or pts > best[0]:
                    best = (pts, pid)
        if best:
            total += best[0]
            del avail[best[1]]
    return total


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------
def main():
    cfg = S.load_config("config.json")
    out_dir = cfg.get("tools_json_dir") or "../static"
    lid = cfg["league_id"]

    league = S.get(f"/league/{lid}")
    users = S.get(f"/league/{lid}/users") or []
    rosters = S.get(f"/league/{lid}/rosters") or []
    names = S.team_names(users, rosters)
    rids = [r["roster_id"] for r in rosters]
    slots = [s for s in (league.get("roster_positions") or []) if s not in NOT_STARTING]
    pkey = projection_key(league)
    season = league.get("season")

    players = load_players()

    scores, opp, weeks = {}, {}, []
    week_rows = {}
    for wk in S.weeks_to_score(league, cfg):
        m = S.get(f"/league/{lid}/matchups/{wk}") or []
        sc = {x["roster_id"]: S.score_of(x) for x in m if x["roster_id"] in names}
        if not sc or not any(sc.values()):
            continue
        weeks.append(wk)
        scores[wk] = sc
        pairs = defaultdict(list)
        for x in m:
            if x.get("matchup_id") is not None:
                pairs[x["matchup_id"]].append(x["roster_id"])
        opp[wk] = {}
        for ids in pairs.values():
            if len(ids) == 2:
                opp[wk][ids[0]], opp[wk][ids[1]] = ids[1], ids[0]
        week_rows[wk] = m

    now = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    team_list = [{"roster_id": r, **names[r]} for r in rids]
    os.makedirs(out_dir, exist_ok=True)

    # ---------------- Shoulda Coulda Woulda ----------------
    def record(a, b):
        w = l = t = 0
        for wk in weeks:
            o = opp[wk].get(b)
            if o is None:
                continue
            if o == a:          # b's opponent was a itself, so a faces b instead
                o = b
            if o == a:
                continue
            sa, so = scores[wk].get(a, 0), scores[wk].get(o, 0)
            if sa > so:
                w += 1
            elif sa < so:
                l += 1
            else:
                t += 1
        return {"w": w, "l": l, "t": t}

    matrix = {a: {b: record(a, b) for b in rids} for a in rids}
    summary = []
    for a in rids:
        actual = matrix[a][a]
        others = [(b, matrix[a][b]) for b in rids if b != a]
        avg_w = sum(r["w"] + 0.5 * r["t"] for _, r in others) / len(others) if others else 0
        best_b, best_r = max(others, key=lambda br: (br[1]["w"], br[1]["t"])) if others else (a, actual)
        worst_b, worst_r = min(others, key=lambda br: (br[1]["w"], br[1]["t"])) if others else (a, actual)
        opp_pts = [scores[wk][opp[wk][a]] for wk in weeks if a in opp[wk]]
        summary.append({
            "roster_id": a, **names[a],
            "actual": actual,
            "expected_wins": round(avg_w, 2),
            "luck": round(actual["w"] + 0.5 * actual["t"] - avg_w, 2),
            "best_schedule": {"roster_id": best_b, "team": names[best_b]["team"], **best_r},
            "worst_schedule": {"roster_id": worst_b, "team": names[worst_b]["team"], **worst_r},
            "opp_avg_points": round(sum(opp_pts) / len(opp_pts), 2) if opp_pts else 0,
            "points_for": round(sum(scores[wk].get(a, 0) for wk in weeks), 2),
        })
    for rank, row in enumerate(sorted(summary, key=lambda r: -r["opp_avg_points"]), 1):
        row["sos_rank"] = rank  # 1 = toughest schedule
    summary.sort(key=lambda r: (-(r["actual"]["w"] + 0.5 * r["actual"]["t"]), -r["points_for"]))
    order = [r["roster_id"] for r in summary]

    with open(os.path.join(out_dir, "shoulda-coulda-woulda.json"), "w") as f:
        json.dump({
            "league": league.get("name"), "season": season, "weeks": weeks, "updated": now,
            "teams": [next(t for t in team_list if t["roster_id"] == r) for r in order],
            "matrix": [{"roster_id": a, "cells": [{"schedule_of": b, **matrix[a][b]} for b in order]}
                       for a in order],
            "summary": summary,
        }, f, indent=1)

    # ---------------- Performance Awards ----------------
    tallies = defaultdict(Counter)
    weekly = []
    for wk in weeks:
        proj = load_projections(season, wk, pkey)
        awards = []

        def give(key, rid, value, detail="", player=None):
            awards.append({"key": key, **AWARD_INFO[key], "roster_id": rid, **names[rid],
                           "value": value, "detail": detail, "player": player})
            tallies[rid][key] += 1

        teams = {}
        for x in week_rows[wk]:
            rid = x["roster_id"]
            if rid not in names:
                continue
            pp = {str(k): float(v or 0) for k, v in (x.get("players_points") or {}).items()}
            starters = [str(p) for p in (x.get("starters") or []) if p and str(p) != "0"]
            bench = [p for p in (x.get("players") or []) if str(p) not in starters]
            bench = [str(p) for p in bench]
            actual = scores[wk][rid]
            best = optimal_points(slots, pp, players) if slots else actual
            teams[rid] = {
                "pp": pp, "starters": starters, "bench": bench, "score": actual,
                "optimal": best,
                "eff": (actual / best * 100) if best else 100.0,
                "bench_pts": sum(pp.get(p, 0) for p in bench),
                "proj": sum(proj.get(p, 0) for p in starters) if proj else None,
            }

        # Money Shot: best single starter
        tops = [(t["pp"].get(p, 0), rid, p) for rid, t in teams.items() for p in t["starters"]]
        if tops:
            pts, rid, pid = max(tops)
            give("money_shot", rid, f"{pts:.2f} pts", player=player_info(players, pid))

        # The Taco
        rid = min(teams, key=lambda r: teams[r]["score"])
        give("taco", rid, f"{teams[rid]['score']:.2f} pts")

        # Best / worst manager
        rid = max(teams, key=lambda r: teams[r]["eff"])
        t = teams[rid]
        give("best_manager", rid, f"{t['eff']:.1f}%", f"{t['score']:.2f} of a possible {t['optimal']:.2f}")
        rid = min(teams, key=lambda r: teams[r]["eff"])
        t = teams[rid]
        give("worst_manager", rid, f"{t['eff']:.1f}%", f"{t['score']:.2f} of a possible {t['optimal']:.2f}")

        # Blowout / narrow victory
        margins = []
        for a, b in opp[wk].items():
            diff = scores[wk][a] - scores[wk][b]
            if diff > 0:
                margins.append((diff, a, b))
        if margins:
            d, a, b = max(margins)
            give("blowout", a, f"+{d:.2f}", f"Beat {names[b]['team']} {scores[wk][a]:.2f} to {scores[wk][b]:.2f}")
            d, a, b = min(margins)
            give("narrow", a, f"+{d:.2f}", f"Beat {names[b]['team']} {scores[wk][a]:.2f} to {scores[wk][b]:.2f}")

        # Projections
        if proj and any(t["proj"] for t in teams.values()):
            diffs = {r: t["score"] - t["proj"] for r, t in teams.items()}
            rid = max(diffs, key=diffs.get)
            give("overachiever", rid, f"{diffs[rid]:+.2f}",
                 f"Scored {teams[rid]['score']:.2f}, projected {teams[rid]['proj']:.2f}")
            rid = min(diffs, key=diffs.get)
            give("below", rid, f"{diffs[rid]:+.2f}",
                 f"Scored {teams[rid]['score']:.2f}, projected {teams[rid]['proj']:.2f}")

        # Position + benchwarmer awards
        for group, prefix in (("starters", "best_"), ("bench", "bench_")):
            for pos in POSITIONS:
                cands = [(t["pp"].get(p, 0), rid, p) for rid, t in teams.items() for p in t[group]
                         if players.get(p, {}).get("position") == pos]
                if cands:
                    pts, rid, pid = max(cands)
                    if pts > 0:
                        give(f"{prefix}{pos.lower()}", rid, f"{pts:.2f} pts",
                             player=player_info(players, pid))

        # Ron Jeremy
        rid = max(teams, key=lambda r: teams[r]["bench_pts"])
        give("bench_points", rid, f"{teams[rid]['bench_pts']:.2f} pts on the bench")

        weekly.append({"week": wk, "awards": awards,
                       "projections_available": bool(proj)})

    tally_rows = []
    for r in rids:
        c = tallies[r]
        tally_rows.append({"roster_id": r, **names[r], "total": sum(c.values()), "counts": dict(c)})
    tally_rows.sort(key=lambda r: -r["total"])

    with open(os.path.join(out_dir, "performance-awards.json"), "w") as f:
        json.dump({
            "league": league.get("name"), "season": season, "weeks": weeks, "updated": now,
            "award_types": [{"key": k, "emoji": e, "title": t, "description": d}
                            for k, e, t, d in AWARDS],
            "weekly": weekly, "tallies": tally_rows,
        }, f, indent=1)

    print(f"Wrote shoulda-coulda-woulda.json and performance-awards.json to {out_dir} "
          f"({len(weeks)} weeks)")


if __name__ == "__main__":
    main()
