"""Pull FPL data for the group and compute every metric the site shows.

Usage: python pipeline/build.py [--refresh]
Writes data/site.json. Finished gameweeks are cached in data/raw; --refresh refetches everything.
"""
import json
import math
import statistics
import sys
import time
import urllib.request
from datetime import datetime, timezone
from itertools import combinations
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
OUT = ROOT / "data" / "site.json"
API = "https://fantasy.premierleague.com/api/"
LEAGUE_ID = 36352
MANAGERS = {4785042: "Jim", 6216297: "Ash", 169793: "Haz", 418825: "Cal", 3550467: "Dez", 475671: "Jack"}
REFRESH = "--refresh" in sys.argv

GOAL_PTS = {1: 6, 2: 6, 3: 5, 4: 4}
CS_PTS = {1: 4, 2: 4, 3: 1, 4: 0}


def fetch(path, name, fresh=False):
    f = RAW / f"{name}.json"
    if f.exists() and not (fresh or REFRESH):
        return json.loads(f.read_text(encoding="utf-8"))
    req = urllib.request.Request(API + path, headers={"User-Agent": "Mozilla/5.0"})
    data = json.load(urllib.request.urlopen(req, timeout=30))
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    time.sleep(0.25)
    return data


def poisson(k, lam):
    return math.exp(-lam) * lam**k / math.factorial(k)


def luck_parts(s, pos):
    """(actual, expected) points from the outcome-driven parts of a score."""
    if s["minutes"] == 0:
        return 0.0, 0.0
    xgc = float(s["expected_goals_conceded"])
    actual = s["goals_scored"] * GOAL_PTS[pos] + s["assists"] * 3
    expected = float(s["expected_goals"]) * GOAL_PTS[pos] + float(s["expected_assists"]) * 3
    if s["minutes"] >= 60:
        actual += s["clean_sheets"] * CS_PTS[pos]
        expected += math.exp(-xgc) * CS_PTS[pos]
    if pos <= 2:
        actual -= s["goals_conceded"] // 2
        expected -= sum(poisson(g, xgc) * (g // 2) for g in range(25))
    return actual, expected


def effective_squad(pk, lv):
    """Who actually counted in a gameweek: starters, auto-subs, bench boost.

    The API already moves the armband (multiplier 2 or 3) to the vice-captain when the captain doesn't play.
    """
    mult = {p["element"]: p["multiplier"] for p in pk["picks"] if p["multiplier"] > 0}
    for s in pk.get("automatic_subs", []):
        mult.pop(s["element_out"], None)
        mult[s["element_in"]] = 1
    armband = next((p for p in pk["picks"] if p["multiplier"] > 1), None)
    if armband:
        cap_el, cap_mult = armband["element"], armband["multiplier"]
    else:  # captain and vice both missed the gameweek
        cap_el, cap_mult = next(p["element"] for p in pk["picks"] if p["is_captain"]), 1
    played = set(mult)
    bench = [p["element"] for p in pk["picks"] if p["position"] > 11 and p["element"] not in played]
    starters = [p["element"] for p in pk["picks"] if p["position"] <= 11]
    return {"mult": mult, "cap": cap_el, "cap_mult": cap_mult, "chip": pk["active_chip"],
            "bench": bench, "starters": starters, "all": [p["element"] for p in pk["picks"]]}


def rank_desc(values, reverse=True):
    return sorted(values.items(), key=lambda kv: kv[1], reverse=reverse)


def main():
    bs = fetch("bootstrap-static/", "bootstrap", fresh=True)
    players = {p["id"]: p for p in bs["elements"]}
    teams = {t["id"]: t for t in bs["teams"]}
    finished = [e["id"] for e in bs["events"] if e["finished"]]
    latest = max(finished)
    nxt = next((e["id"] for e in bs["events"] if not e["finished"]), None)
    name = lambda el: players[el]["web_name"]

    live = {gw: {x["id"]: x["stats"] for x in fetch(f"event/{gw}/live/", f"live_{gw}")["elements"]} for gw in finished}
    pts = lambda el, gw: live[gw][el]["total_points"]

    standings = fetch(f"leagues-classic/{LEAGUE_ID}/standings/", "league", fresh=True)["standings"]["results"]
    team_name = {r["entry"]: r["entry_name"] for r in standings}
    league_total = {r["entry"]: r["total"] for r in standings}
    league_rank = {r["entry"]: r["rank"] for r in standings}  # tie-break: level on points, the league's order wins

    hist, squads = {}, {}
    for e in MANAGERS:
        hist[e] = fetch(f"entry/{e}/history/", f"history_{e}", fresh=True)
        squads[e] = {}
        for gw in finished:
            pk = fetch(f"entry/{e}/event/{gw}/picks/", f"picks_{e}_{gw}")
            sq = effective_squad(pk, live[gw])
            sq["gross"] = pk["entry_history"]["points"]
            sq["hits"] = pk["entry_history"]["event_transfers_cost"]
            squads[e][gw] = sq

    checks = {"points_mismatch": [], "table_mismatch": []}
    for e in MANAGERS:
        for gw in finished:
            sq = squads[e][gw]
            calc = sum(m * pts(el, gw) for el, m in sq["mult"].items())
            if calc != sq["gross"]:
                checks["points_mismatch"].append(f"{MANAGERS[e]} GW{gw}: calc {calc} vs api {sq['gross']}")

    net_gw = {e: {gw: squads[e][gw]["gross"] - squads[e][gw]["hits"] for gw in finished} for e in MANAGERS}
    season = {e: sum(net_gw[e].values()) for e in MANAGERS}
    for e in MANAGERS:
        if season[e] != league_total[e]:
            checks["table_mismatch"].append(f"{MANAGERS[e]}: calc {season[e]} vs league {league_total[e]}")

    # ---- per-manager metrics ----
    m = {e: dict(cap_pts=0, cap_regret=0, bench=0, hits=0, diff_global=0, diff_group=0, template=[], act=0.0, exp=0.0)
         for e in MANAGERS}
    luck_gw = {e: {} for e in MANAGERS}
    luck_players = {e: {} for e in MANAGERS}
    for gw in finished:
        owners = {}
        for e in MANAGERS:
            for el in squads[e][gw]["mult"]:
                owners[el] = owners.get(el, 0) + 1
        for e in MANAGERS:
            sq, r = squads[e][gw], m[e]
            xi = sq["mult"]
            best = max(pts(el, gw) for el in xi)
            r["cap_pts"] += pts(sq["cap"], gw) * sq["cap_mult"]
            r["cap_regret"] += (best - pts(sq["cap"], gw)) * sq["cap_mult"]
            r["hits"] += sq["hits"]
            if sq["chip"] != "bboost":
                r["bench"] += sum(pts(el, gw) for el in sq["bench"])
            gw_a = gw_x = 0.0
            tmpl = []
            for el, mult in xi.items():
                v = pts(el, gw) * mult
                own = float(players[el]["selected_by_percent"])
                tmpl.append(own)
                if own < 10:
                    r["diff_global"] += v
                if owners[el] == 1:
                    r["diff_group"] += v
                a, x = luck_parts(live[gw][el], players[el]["element_type"])
                gw_a += a * mult
                gw_x += x * mult
                luck_players[e][el] = luck_players[e].get(el, 0) + (a - x) * mult
            r["template"].append(sum(tmpl) / len(tmpl))
            r["act"] += gw_a
            r["exp"] += gw_x
            luck_gw[e][gw] = gw_a - gw_x
    avg_luck = statistics.mean(m[e]["act"] - m[e]["exp"] for e in MANAGERS)
    for e in MANAGERS:
        m[e]["luck"] = m[e]["act"] - m[e]["exp"]
        m[e]["luck_vs_group"] = m[e]["luck"] - avg_luck
        m[e]["template"] = statistics.mean(m[e]["template"])
        m[e]["spread"] = statistics.pstdev(squads[e][gw]["gross"] for gw in finished)
        m[e]["points"] = season[e]
    avg_gw = {gw: statistics.mean(luck_gw[e][gw] for e in MANAGERS) for gw in finished}

    # ---- per-gameweek detail and season signature players ----
    weeks, signature = {}, {}
    for e in MANAGERS:
        contrib, rows = {}, {}
        for gw in finished:
            sq = squads[e][gw]
            for el, mult in sq["mult"].items():
                contrib[el] = contrib.get(el, 0) + pts(el, gw) * mult
            # best, second best and worst of the players who counted; a captained flop counts double
            ranked = sorted(sq["mult"], key=lambda el: -pts(el, gw) * sq["mult"][el])
            star, good, flop = ranked[0], ranked[1], ranked[-1]
            rows[gw] = {"points": net_gw[e][gw], "hits": sq["hits"], "chip": sq["chip"],
                        "captain": name(sq["cap"]), "captain_pts": pts(sq["cap"], gw) * sq["cap_mult"],
                        "bench_pts": 0 if sq["chip"] == "bboost" else sum(pts(el, gw) for el in sq["bench"]),
                        "star": name(star), "star_pts": pts(star, gw) * sq["mult"][star],
                        "good": name(good), "good_pts": pts(good, gw) * sq["mult"][good],
                        "flop": name(flop), "flop_pts": pts(flop, gw) * sq["mult"][flop]}
        weeks[MANAGERS[e]] = rows
        signature[MANAGERS[e]] = [{"player": name(el), "pts": v} for el, v in sorted(contrib.items(), key=lambda kv: -kv[1])[:3]]

    # ---- standings, gameweek winners ----
    cum = {e: 0 for e in MANAGERS}
    race = []
    gw_winners = {}
    for gw in finished:
        for e in MANAGERS:
            cum[e] += net_gw[e][gw]
        order = sorted(MANAGERS, key=lambda e: (-cum[e], league_rank[e]))
        race.append({"gw": gw, "totals": {MANAGERS[e]: cum[e] for e in MANAGERS},
                     "ranks": {MANAGERS[e]: order.index(e) + 1 for e in MANAGERS}})
        top = max(net_gw[e][gw] for e in MANAGERS)
        low = min(net_gw[e][gw] for e in MANAGERS)
        gw_winners[gw] = {"winners": [MANAGERS[e] for e in MANAGERS if net_gw[e][gw] == top], "top": top,
                          "spoon": [MANAGERS[e] for e in MANAGERS if net_gw[e][gw] == low], "low": low}

    # ---- transfer regret ----
    transfers = {}
    for e in MANAGERS:
        chips = {c["event"]: c["name"] for c in hist[e]["chips"]}
        trs = [t for t in fetch(f"entry/{e}/transfers/", f"transfers_{e}", fresh=True) if t["event"] in finished]
        trs.sort(key=lambda t: (t["event"], t["time"]))
        rows = []
        for t in trs:
            chip = chips.get(t["event"])
            if chip == "freehit":
                continue
            end = latest
            for u in trs:
                if u["element_out"] == t["element_in"] and u["event"] > t["event"] and chips.get(u["event"]) != "freehit":
                    end = min(end, u["event"] - 1)
            gws = range(t["event"], end + 1)
            p_in = sum(pts(t["element_in"], g) for g in gws)
            p_out = sum(pts(t["element_out"], g) for g in gws)
            rows.append({"gw": t["event"], "in": name(t["element_in"]), "out": name(t["element_out"]),
                         "pts_in": p_in, "pts_out": p_out, "net": p_in - p_out, "chip": chip})
        normal = [r for r in rows if not r["chip"]]
        wc = [r for r in rows if r["chip"] == "wildcard"]
        transfers[MANAGERS[e]] = {
            "normal_net": sum(r["net"] for r in normal), "normal_count": len(normal),
            "wildcard_net": sum(r["net"] for r in wc), "wildcard_count": len(wc),
            "best": max(normal, key=lambda r: r["net"], default=None),
            "worst": min(normal, key=lambda r: r["net"], default=None),
            "all": rows,
        }

    # ---- head to head ----
    h2h = {}
    for a, b in combinations(MANAGERS, 2):
        wins = {a: 0, b: 0, "draw": 0}
        decided = {a: {}, b: {}}
        overlap = []
        for gw in finished:
            na, nb = net_gw[a][gw], net_gw[b][gw]
            wins[a if na > nb else b if nb > na else "draw"] += 1
            xa, xb = squads[a][gw]["mult"], squads[b][gw]["mult"]
            overlap.append(len(set(xa) & set(xb)) / 11)
            for side, mine, other in ((a, xa, xb), (b, xb, xa)):
                for el, mult in mine.items():
                    if el not in other:
                        decided[side][el] = decided[side].get(el, 0) + pts(el, gw) * mult
        top3 = lambda d: [{"player": name(el), "pts": v} for el, v in sorted(d.items(), key=lambda kv: -kv[1])[:3]]
        h2h[f"{MANAGERS[a]}-{MANAGERS[b]}"] = {
            "a": MANAGERS[a], "b": MANAGERS[b],
            "wins": {MANAGERS[a]: wins[a], MANAGERS[b]: wins[b], "draw": wins["draw"]},
            "points": {MANAGERS[a]: season[a], MANAGERS[b]: season[b]},
            "xi_overlap": round(statistics.mean(overlap) * 100),
            "decided_by": {MANAGERS[a]: top3(decided[a]), MANAGERS[b]: top3(decided[b])},
        }

    # ---- JSN report (squad as of last finished gameweek) ----
    has_fixture = {}
    if nxt:
        for f in fetch("fixtures/", "fixtures", fresh=True):
            if f["event"] == nxt:
                for t in (f["team_h"], f["team_a"]):
                    has_fixture[t] = has_fixture.get(t, 0) + 1
    jsn = []
    for e in MANAGERS:
        sq, nick = squads[e][latest], MANAGERS[e]
        for el in sq["all"]:
            p = players[el]
            chance = p["chance_of_playing_next_round"]
            is_cap = el == sq["cap"]
            if p["status"] in ("i", "s", "u", "n") or (chance is not None and chance < 100):
                sev = "out" if p["status"] in ("i", "s", "u", "n") or chance == 0 else "doubt"
                jsn.append({"manager": nick, "kind": "captain_fitness" if is_cap else "fitness", "severity": sev,
                            "player": name(el), "text": p["news"] or f"{chance}% chance of playing", "starter": el in sq["starters"]})
            if nxt and has_fixture.get(p["team"], 0) == 0:
                jsn.append({"manager": nick, "kind": "blank", "severity": "out", "player": name(el),
                            "text": f"{teams[p['team']]['short_name']} have no fixture in GW{nxt}", "starter": el in sq["starters"]})
        for el in sq["starters"]:
            if live[latest][el]["minutes"] == 0:
                jsn.append({"manager": nick, "kind": "dead_weight", "severity": "info", "player": name(el),
                            "text": f"Started in the XI, played 0 minutes in GW{latest}", "starter": True})
        if sq["bench"]:
            top = max(sq["bench"], key=lambda el: pts(el, latest))
            if sq["chip"] != "bboost" and pts(top, latest) >= 6:
                jsn.append({"manager": nick, "kind": "bench_haul", "severity": "info", "player": name(top),
                            "text": f"{name(top)} scored {pts(top, latest)} on the bench in GW{latest}", "starter": False})
    jsn_order = {"out": 0, "doubt": 1, "info": 2}
    jsn.sort(key=lambda i: (jsn_order[i["severity"]], not i["starter"]))

    # ---- awards ----
    def award(key, title, emoji, blurb, values, unit, reverse=True, fmt="{:+.0f}"):
        ranked = rank_desc(values, reverse)
        tied = [MANAGERS[e] for e, v in ranked if abs(v - ranked[0][1]) < 1e-9]
        return {"key": key, "title": title, "emoji": emoji, "blurb": blurb, "winner": tied[0], "winners": tied,
                "value": ranked[0][1], "unit": unit,
                "ranking": [{"manager": MANAGERS[e], "value": v} for e, v in ranked]}

    by_points = sorted(MANAGERS, key=lambda e: (-season[e], league_rank[e]))
    top_half = by_points[: len(by_points) // 2]
    milner_pool = [e for e in top_half if m[e]["hits"] == 0] or top_half
    milner = min(milner_pool, key=lambda e: m[e]["spread"])
    awards = [
        award("differential", "Differential King", "👑", "Most points from players owned by under 10% of managers.",
              {e: m[e]["diff_global"] for e in MANAGERS}, "pts"),
        award("lucky", "Luckiest", "🍀", "Most points above what the chances deserved, versus the group average.",
              {e: m[e]["luck_vs_group"] for e in MANAGERS}, "pts vs group"),
        award("unlucky", "Unluckiest", "💀", "Fewest points relative to the chances their players got.",
              {e: m[e]["luck_vs_group"] for e in MANAGERS}, "pts vs group", reverse=False),
        award("captain", "Captain Fantastic", "🎯", "Most points from the armband.",
              {e: m[e]["cap_pts"] for e in MANAGERS}, "pts"),
        award("regret", "Captain Regret", "🤡", "Most points lost by not captaining the best player in your XI.",
              {e: m[e]["cap_regret"] for e in MANAGERS}, "pts lost"),
        award("bench", "Bench Disaster", "🪑", "Most points left on the bench (Bench Boost weeks excluded).",
              {e: m[e]["bench"] for e in MANAGERS}, "pts"),
        award("template", "Mr Template", "🐑", "Squad most like everyone else's: highest average ownership in the XI.",
              {e: m[e]["template"] for e in MANAGERS}, "% avg owned"),
        {"key": "milner", "title": "The Milner Award", "emoji": "🏅",
         "blurb": "Boring, steady, effective: no hits, lowest weekly spread among the top half of the table.",
         "winner": MANAGERS[milner], "winners": [MANAGERS[milner]], "value": m[milner]["spread"], "unit": "pts weekly spread",
         # eligible managers (top half, no hits) first, lowest spread first; the rest follow, flagged
         "ranking": [{"manager": MANAGERS[e], "value": m[e]["spread"], "eligible": e in milner_pool}
                     for e in sorted(MANAGERS, key=lambda e: (e not in milner_pool, m[e]["spread"]))]},
    ]

    luck_out = {
        MANAGERS[e]: {
            "luck": round(m[e]["luck"], 1), "vs_group": round(m[e]["luck_vs_group"], 1),
            "actual": m[e]["act"], "expected": round(m[e]["exp"], 1),
            "per_gw": {gw: round(luck_gw[e][gw] - avg_gw[gw], 1) for gw in finished},
            "lucky_players": [{"player": name(el), "pts": round(v, 1)} for el, v in sorted(luck_players[e].items(), key=lambda kv: -kv[1])[:3]],
            "unlucky_players": [{"player": name(el), "pts": round(v, 1)} for el, v in sorted(luck_players[e].items(), key=lambda kv: kv[1])[:3]],
        } for e in MANAGERS
    }

    table = [{"manager": MANAGERS[e], "team": team_name[e], "points": season[e], "hits": m[e]["hits"],
              "rank": i + 1, "gw_points": net_gw[e][latest],
              "metrics": {k: round(v, 1) for k, v in m[e].items() if k not in ("act", "exp")}}
             for i, e in enumerate(by_points)]

    out = {
        "meta": {"updated": datetime.now(timezone.utc).isoformat(timespec="seconds"), "latest_gw": latest, "next_gw": nxt,
                 "season": "2026/27", "caveat_ownership": "Differentials use today's global ownership, not per-gameweek."},
        "table": table, "race": race, "gw_winners": gw_winners, "awards": awards, "luck": luck_out,
        "transfers": transfers, "jsn": jsn, "h2h": h2h, "weeks": weeks, "signature": signature, "checks": checks,
    }
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"wrote {OUT} (GW{latest} done, next GW{nxt})")
    print("checks:", "OK" if not any(checks.values()) else checks)


if __name__ == "__main__":
    main()
