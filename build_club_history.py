"""
build_club_history.py
Builds the FM24-only club league-history rows (seasons 2020/21–2022/23, Clhs years 2021–2023)
for the clubs whose post-2001 history the retro mod wipes, so convert_to_fm24.py can delete them.

Why: FM24's base has club history rows for 2021–2023 that FM21's base (and therefore the mod's
row-by-row deletes) never had. A delete only succeeds when olvl matches the stored row exactly,
and FM24 stores the real final league tables (verified: Roma 2021–2023, Sucesso = Sim).

How:
  1. Read output/fm21/<country>.xml: clubs with Clhs deletes (lsop=2) — the mod's intent to wipe
     their modern history. Their 2020 row (season 2019/20: competition, position, points)
     identifies the club in the real 2019/20 table.
  2. Follow the club (by its Wikipedia article link) through the 2020/21–2022/23 tables.
  3. Write reference/club_history/<country>.json: {club_entity_id: [row, ...]}.

Tables come from Wikipedia "Template:<season> <league> table" pages (Sports table module).

Usage:
    python build_club_history.py italy
"""

import json
import os
import re
import sys
import urllib.parse
import urllib.request
from collections import Counter

TARGET   = sys.argv[1] if len(sys.argv) > 1 else "italy"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FM21_XML = os.path.join(BASE_DIR, "output", "fm21", f"{TARGET}.xml")
OUT_DIR  = os.path.join(BASE_DIR, "reference", "club_history")
CACHE    = os.path.join(BASE_DIR, "reference", "club_history", "wiki_cache")
MULT     = 2**32 + 1
CLHS     = "1131178099"

SEASONS = {2020: "2019–20", 2021: "2020–21", 2022: "2021–22", 2023: "2022–23"}   # Clhs year → season

# League tables per country: (Wikipedia template suffix, FM competition id or None).
# None = competition id learned from the mod's own 2020 rows (group → id), never guessed.
#   "Serie A table"            → page "Template:<season> Serie A table"
#   "Serie D|Girone I/Group I" → section "== Girone I ==" (or "== Group I ==") of the article "<season> Serie D"
LEAGUES = {
    "italy": [
        ("Serie A table", 32),
        ("Serie B table", 33),
        ("Serie C Group A table", None),
        ("Serie C Group B table", None),
        ("Serie C Group C table", None),
        # Serie D: only Girone I is confirmed (1400408: Palermo 2019/20 in MASTER, Catania 2022/23 in an
        # FM24 editor sample). Other groups: too few clubs in the mod's data to learn their ids safely.
        ("Serie D|Girone I/Group I", 1400408),
    ],
}


# ── Wikipedia tables ─────────────────────────────────────────────────────────

def fetch(title):
    os.makedirs(CACHE, exist_ok=True)
    path = os.path.join(CACHE, re.sub(r'[^\w\- ]', '_', title) + ".txt")
    if os.path.exists(path):
        return open(path, encoding="utf-8").read()
    url = "https://en.wikipedia.org/w/index.php?" + urllib.parse.urlencode({"title": title, "action": "raw"})
    req = urllib.request.Request(url, headers={"User-Agent": "fm-history-research/1.0"})
    text = urllib.request.urlopen(req, timeout=30).read().decode("utf-8")
    open(path, "w", encoding="utf-8").write(text)
    return text


def canonical_titles(titles):
    """Resolve Wikipedia redirects so a club keeps one identity across seasons
    ('A.S. Roma' → 'AS Roma', old names of renamed clubs → current article). Cached."""
    path = os.path.join(CACHE, "_canonical.json")
    cache = json.load(open(path, encoding="utf-8")) if os.path.exists(path) else {}
    todo = sorted(t for t in set(titles) if t not in cache)
    for i in range(0, len(todo), 50):
        batch = todo[i:i + 50]
        url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
            {"action": "query", "titles": "|".join(batch), "redirects": 1, "format": "json"})
        req = urllib.request.Request(url, headers={"User-Agent": "fm-history-research/1.0"})
        q = json.loads(urllib.request.urlopen(req, timeout=30).read().decode("utf-8"))["query"]
        norm = {n["from"]: n["to"] for n in q.get("normalized", [])}
        redir = {r["from"]: r["to"] for r in q.get("redirects", [])}
        for t in batch:
            n = norm.get(t, t)
            cache[t] = redir.get(n, n)
    json.dump(cache, open(path, "w", encoding="utf-8"), ensure_ascii=False, indent=0)
    return cache


def league_table(season, league):
    """Raw Sports-table wikitext for one league/group of one season (None if absent)."""
    try:
        if "|" not in league:
            return fetch(f"Template:{season} {league}")
        article, heading = league.split("|")
        text = fetch(f"{season} {article}")
    except Exception:
        return None
    for h in heading.split("/"):            # heading variants ("Girone I" / "Group I")
        m = re.search(rf'^==\s*{re.escape(h)}\s*==\s*$(.*?)(?=^==[^=])', text + "\n== END ==", re.S | re.M)
        if m:
            break
    if not m:
        return None
    t = m.group(1)
    start = t.find("{{#invoke:Sports table")
    return t[start:] if start >= 0 else None


def parse_table(text):
    """Sports-table wikitext → list of rows in final order."""
    text = re.sub(r'<!--.*?-->', '', text, flags=re.S)
    m = re.search(r'\|\s*team_order\s*=([^|]*)', text)
    if m:
        order = [c.strip() for c in m.group(1).split(",") if c.strip()]
    else:   # alternative syntax: |team1 = BEN |team2 = CRO ...
        order = [c for _, c in sorted((int(n), c) for n, c in re.findall(r'\|\s*team(\d+)\s*=\s*(\w+)', text))]
    def num(key, code, default=0):
        m = re.search(rf'\|\s*{key}_{re.escape(code)}\s*=\s*(-?\d+)', text)
        return int(m.group(1)) if m else default
    # Teams excluded during the season (status D): FM24 sometimes counts them in
    # maximum_number_teams (Catania 2021/22) and sometimes not (Trapani 2020/21) → both variants.
    excluded = set(re.findall(r'\|\s*status_(\w+)\s*=\s*[^|\n]*\bD\b', text)) & set(order)
    teams_alt = len(order) - len(excluded) if excluded else None
    rows = []
    for pos, code in enumerate(order, 1):
        nm = re.search(rf'\|\s*name_{re.escape(code)}\s*=\s*\[\[([^\]|]+)', text)
        w, d, l = num("win", code), num("draw", code), num("loss", code)
        st = re.search(rf'\|\s*status_{re.escape(code)}\s*=\s*([A-Z, ]*)', text)
        rows.append({
            "code": code, "link": nm.group(1).strip() if nm else code,
            "status": re.sub(r'[ ,]', '', st.group(1)) if st else "",
            "posi": pos, "wins": w, "draw": d, "lost": l, "play": w + d + l,
            "gfor": num("gf", code), "gaga": num("ga", code),
            "poin": 3 * w + d + num("adjust_points", code) + num("startpoints", code),
            "teams": len(order), "teams_alt": teams_alt,
        })
    return rows


# ── mod's 2020 rows ──────────────────────────────────────────────────────────

def wiped_clubs(path):
    """club entity id → 2020 row {comp, posi, poin} for clubs with Clhs deletes."""
    clubs, buf = {}, None
    for line in open(path, encoding="utf-8"):
        s = line.rstrip("\n")
        if buf is None:
            if s == "\t\t<record>":
                buf = [s]
            continue
        buf.append(s)
        if s != "\t\t</record>":
            continue
        b, buf = "\n".join(buf), None
        if f'property" value="{CLHS}"' not in b or 'lsop" value="2"' not in b:
            continue
        eid = int(re.search(r'db_unique_id" value="(\d+)"', b).group(1)) // MULT
        clubs.setdefault(eid, None)
        if re.search(r'id="year" value="2020"', b):
            g = lambda k: int(re.search(rf'id="{k}" value="(-?\d+)"', b).group(1))
            clubs[eid] = {"comp": g("competition"), "posi": g("posi"), "poin": g("poin")}
    return clubs


# Club ids confirmed by the user in the FM21 editor (canonical Wikipedia article → FM club id),
# for clubs that appear in no row of the mod's data. Never guess these.
KNOWN_CLUBS = {
    "italy": {
        "US Cremonese": 1125,
        "Pisa SC": 2215,
        "Frosinone Calcio": 2199,
        "FC Südtirol": 829172,
        "US Catanzaro 1929": 1119,
        "US Avellino 1912": 1108,
        # Virtus Entella: does not exist in the FM21 database (confirmed 2026-11-26)
    },
}

# Leagues whose FM24 competition history stores the promotion play-off winner (plwn):
# verified for Serie B (FM24 sample: Spezia 2020, Cagliari 2023). Wikipedia marks it with
# status O (play-off winner) + P (promoted); O alone is a relegation play-out.
PLAYOFF_WINNER = {"Serie B table"}

CHST = "1667789684"   # competition history (rtype 25): pla1/pla2/pla3 = top 3 of the season


def comp_history_2020(path):
    """competition id → [eid of 1st, 2nd, 3rd] from the mod's 2020 chst delete (season 2019/20)."""
    out, buf = {}, None
    for line in open(path, encoding="utf-8"):
        s = line.rstrip("\n")
        if buf is None:
            if s == "\t\t<record>":
                buf = [s]
            continue
        buf.append(s)
        if s != "\t\t</record>":
            continue
        b, buf = "\n".join(buf), None
        if f'property" value="{CHST}"' in b and 'lsop" value="2"' in b and re.search(r'id="year" value="2020"', b):
            uid = int(re.search(r'db_unique_id" value="(\d+)"', b).group(1))
            pla = [re.search(rf'<record id="pla{i}">\s*<integer id="Ttea" value="(\d+)"', b) for i in (1, 2, 3)]
            out[uid // MULT] = [int(m.group(1)) if m else None for m in pla]
    return out


def main():
    tables = {}   # (year, league) → rows
    for year, season in SEASONS.items():
        for league, _ in LEAGUES[TARGET]:
            text = league_table(season, league)
            if text:
                tables[(year, league)] = parse_table(text)
            else:
                print(f"(table not found: {season} {league})")
    canon = canonical_titles([x["link"] for t in tables.values() for x in t])
    for t in tables.values():
        for x in t:
            x["link"] = canon.get(x["link"], x["link"])

    fixed_comp = {league: comp for league, comp in LEAGUES[TARGET] if comp}
    clubs = wiped_clubs(FM21_XML)
    link_of, report = {}, []

    # candidate matches: 2020 row (position + points) found in a 2019/20 table
    matches = {}
    for eid, r20 in sorted(clubs.items()):
        if not r20:
            report.append(f"{eid}: no 2020 row — skipped")
            continue
        for lg, c in LEAGUES[TARGET]:
            if c is not None and c != r20["comp"]:
                continue
            row = next((x for x in tables.get((2020, lg), []) if x["posi"] == r20["posi"]), None)
            if row and row["poin"] == r20["poin"]:
                matches.setdefault(eid, []).append((lg, row))

    # group leagues: competition id = majority vote among matched clubs (coincidental
    # matches from other countries' clubs are outvoted and dropped below)
    votes = {}
    for eid, ms in matches.items():
        for lg, _ in ms:
            if lg not in fixed_comp:
                votes.setdefault(lg, Counter())[clubs[eid]["comp"]] += 1
    group_comp = {lg: v.most_common(1)[0][0] for lg, v in votes.items()}
    comp_of = {**fixed_comp, **group_comp}

    for eid, r20 in sorted(clubs.items()):
        if not r20:
            continue
        ok = [(lg, row) for lg, row in matches.get(eid, []) if comp_of.get(lg) == r20["comp"]]
        if len(ok) != 1:
            report.append(f"{eid}: 2020 row comp={r20['comp']} posi={r20['posi']} poin={r20['poin']} "
                          f"{'ambiguous' if ok else 'not in tracked tables'} — skipped")
            continue
        link_of[eid] = ok[0][1]["link"]
    result = {}
    for eid, link in link_of.items():
        rows = []
        for year in (2021, 2022, 2023):
            found = [(lg, x) for (y, lg), t in tables.items() if y == year for x in t if x["link"] == link]
            if not found:
                report.append(f"{eid} {link}: no {SEASONS[year]} row in tracked leagues (lower league?)")
                continue
            lg, x = found[0]
            if lg not in comp_of:
                report.append(f"{eid} {link}: {SEASONS[year]} in {lg}, competition id unknown — skipped")
                continue
            rows.append({"year": year, "comp": comp_of[lg], **{k: x[k] for k in
                         ("posi", "poin", "play", "wins", "draw", "lost", "gfor", "gaga", "teams", "teams_alt")}})
        result[eid] = {"link": link, "rows": rows}

    # ── competition history (top 3 per season) ───────────────────────────────
    # club identity: clubs identified above + the top 3 of each league's 2020 chst row
    eid_of = {link: eid for eid, link in link_of.items()}
    known = KNOWN_CLUBS.get(TARGET, {})
    for link, eid in canonical_titles(list(known)).items():
        if link in known:
            eid_of.setdefault(eid, known[link])     # canonical title → id
    ch2020 = comp_history_2020(FM21_XML)
    league_of = {c: lg for lg, c in comp_of.items()}
    for comp, pla in ch2020.items():
        lg = league_of.get(comp)
        if not lg or (2020, lg) not in tables:
            continue
        for i, e in enumerate(pla):
            row = next((x for x in tables[(2020, lg)] if x["posi"] == i + 1), None)
            if e and row:
                eid_of.setdefault(row["link"], e)
    comps = {}
    for comp, lg in league_of.items():
        if comp not in ch2020:
            continue                       # the mod does not wipe this competition's history
        rows = []
        # 2020 is the mod's own row; it is regenerated only when FM24 adds a play-off winner to it
        for year in ((2020, 2021, 2022, 2023) if lg in PLAYOFF_WINNER else (2021, 2022, 2023)):
            t = tables.get((year, lg))
            if not t:
                continue
            top = [next((x for x in t if x["posi"] == p), None) for p in (1, 2, 3)]
            eids = [eid_of.get(x["link"]) if x else None for x in top]
            if None in eids:
                report.append(f"comp {comp} {SEASONS[year]}: top 3 not all identified "
                              f"({', '.join(x['link'] for x in top if x)}) — skipped")
                continue
            row = {"year": year, "pla": eids}
            if lg in PLAYOFF_WINNER:
                pw = [x for x in t if "O" in x["status"] and "P" in x["status"]]
                pw_eid = eid_of.get(pw[0]["link"]) if len(pw) == 1 else None
                if not pw_eid:
                    report.append(f"comp {comp} {SEASONS[year]}: play-off winner not identified — skipped")
                    continue
                row["plwn"] = pw_eid
            rows.append(row)
        comps[comp] = rows

    os.makedirs(OUT_DIR, exist_ok=True)
    out = os.path.join(OUT_DIR, f"{TARGET}.json")
    json.dump({"competition_ids": comp_of, "clubs": result, "competitions": comps},
              open(out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print(f"competition history rows: {sum(len(v) for v in comps.values())} "
          f"({', '.join(f'{c}: {len(v)}' for c, v in comps.items())})")
    print(f"clubs wiped by the mod: {len(clubs)} | identified: {len(link_of)} | "
          f"rows: {sum(len(v['rows']) for v in result.values())}")
    print("competition ids:", comp_of)
    print("\n".join(report))
    print("->", out)


if __name__ == "__main__":
    main()
