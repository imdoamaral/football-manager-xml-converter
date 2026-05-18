"""
split_fm_xml.py
Two-pass streaming split of the FM 2021 XML patch file.

Pass 1: scan the entire file to build uid->nation lookup dicts.
Pass 2: re-scan and write only records belonging to the TARGET nation.

See CLAUDE.md for the full inclusion criteria (9 rules) and architecture details.
Output: output/fm21/<country>.xml
"""

import re
import os
import sys
import random

BASE_DIR   = os.path.dirname(os.path.abspath(__file__))
filepath   = os.path.join(BASE_DIR, "The 2001 02 DB MASTER.xml")
output_dir = os.path.join(BASE_DIR, "output", "fm21")

if len(sys.argv) < 2:
    print("Usage: python split_fm_xml.py <country|region>  (e.g.: italy, south_america)")
    sys.exit(1)
TARGET = sys.argv[1].lower()

# ── Regex patterns ────────────────────────────────────────────────
TYPE_RE = re.compile(r'<integer id="database_table_type" value="(\d+)"')
PROP_RE = re.compile(r'<unsigned id="property" value="(\d+)"')
UID_RE  = re.compile(r'<large id="db_unique_id" value="(\d+)"')
TTEA_RE        = re.compile(r'<integer id="Ttea" value="(\d+)"')
COMP_RE        = re.compile(r'<integer id="competition" value="(\d+)"')
NNAT_RE        = re.compile(r'<integer id="Nnat" value="(\d+)"')
PERS_RE        = re.compile(r'<integer id="Pers" value="(\d+)"')
YEAR_RE        = re.compile(r'<(?:unsigned|integer) id="year" value="(\d+)"')
# Parse new_value / odvl Ttea separately to handle <null id="new_value"/> cases
NEWVAL_TTEA_RE = re.compile(r'<record id="new_value">[\s\S]*?<integer id="Ttea" value="(\d+)"', re.DOTALL)
ODVL_TTEA_RE   = re.compile(r'<record id="odvl">[\s\S]*?<integer id="Ttea" value="(\d+)"', re.DOTALL)

# FourCC property IDs (unsigned integer form)
PCTI_PROP      = "1348695145"   # current club contract  → Ttea
PNTI_PROP      = "1349416041"   # nationality            → Nnat
PLHS_PROP      = "1349281907"   # league history         → Ttea + competition + year
CDVI_PROP      = "1130657385"   # club current division  → competition
FREE_AGENT_TTEA = "1171"        # virtual free-agents team (skip for club lookup)
MULT            = 2**32 + 1      # db_unique_id = entity_id * MULT
CLHS_PROP       = "1131178099"   # club league history season  → competition + year
CLDI_PROP       = "1131177065"   # club last division          → competition
SEASON_END_YEAR = 2002           # 2001/02 season ends in calendar year 2002

# ── Nation mapping tables ─────────────────────────────────────────
# IDs confirmed in the FM 2021 editor.
#
# MINIMUM STANDARD before generating the XML for any new nation:
#   REQUIRED     — nation (NNAT_NATION) + divisions 1, 2, 3 + main national cup
#   RECOMMENDED  — division 4 + all variants/groups of levels 3 and 4 + super cup
#   UNNECESSARY  — division 5+ (semi-professional/amateur, rarely in retro patch)
# NEVER guess IDs — always confirm in the FM 2021 editor.
COMP_NATION = {
    # Italy (IDs confirmed in the editor)
    32: "italy",        # Serie A
    33: "italy",        # Serie B
    34: "italy",        # Serie C1/A
    35: "italy",        # Serie C1/B
    36: "italy",        # Serie C2/A
    37: "italy",        # Serie C2/B
    38: "italy",        # Serie C2/C
    39: "italy",        # Serie C1/C
    145429: "italy",    # Serie C1
    145430: "italy",    # Serie C2
    1301412: "italy",   # Coppa Italia
    1301414: "italy",   # Supercoppa Italiana
    23127172: "italy",  # Serie C/A (v1)
    43121712: "italy",  # Serie C/A (v2)
    43121713: "italy",  # Serie C/B (v1)
    43127173: "italy",  # Serie C/B (v2)
    43127171: "italy",  # Serie C
    43127174: "italy",  # Serie C/C
    # Spain (IDs confirmed in the editor)
    67: "spain",          # Primera División
    68: "spain",          # Segunda División
    69: "spain",          # Segunda B1
    70: "spain",          # Segunda B2
    71: "spain",          # Segunda B3
    72: "spain",          # Segunda B4
    121091: "spain",      # Segunda B (generic)
    1301422: "spain",     # Copa del Rey
    1301423: "spain",     # Supercopa de España
    20000032789: "spain", # Segunda B5
    20000048840: "spain", # Second Division Pro
    20000048844: "spain", # Second Division Pro A
    20000048846: "spain", # Second Division Pro B
    # England (IDs confirmed in the editor)
    11: "england",        # Premier League
    12: "england",        # Sky Bet Championship
    13: "england",        # Sky Bet League One
    14: "england",        # Sky Bet League Two
    109201: "england",    # Vanarama National League
    109202: "england",    # FA Trophy
    1301426: "england",   # FA Cup
    1301427: "england",   # Carabao Cup
    1301428: "england",   # FA Community Shield
    1301429: "england",   # Papa John's Trophy
    # Germany (IDs confirmed in the editor)
    22: "germany",        # Bundesliga
    23: "germany",        # 2. Bundesliga
    26: "germany",        # Regionalliga North
    27: "germany",        # Regionalliga Southeast
    146957: "germany",    # Regionalliga (generic)
    35010926: "germany",  # 3. Liga
    1301410: "germany",   # DFB-Pokal
    91107110: "germany",  # Regionalliga Northeast
    91107111: "germany",  # Regionalliga Southwest
    92030194: "germany",  # DFL-Supercup
    # Scotland (IDs confirmed in the editor)
    45: "scotland",       # Scottish Premiership      (level 1)
    46: "scotland",       # Scottish Championship     (level 2)
    47: "scotland",       # Scottish League One       (level 3)
    48: "scotland",       # Scottish League Two       (level 4)
    120798: "scotland",   # SPFL Trust Trophy
    1301430: "scotland",  # Scottish Cup
    1301431: "scotland",  # Betfred Cup
    # France (IDs confirmed in the editor)
    16: "france",         # Ligue 1                  (level 1)
    17: "france",         # Ligue 2                  (level 2)
    18: "france",         # Championnat National     (level 3)
    19: "france",         # National 2 - A           (level 4)
    145438: "france",     # National 2 (generic)     (level 4)
    914522: "france",     # National 2 - B           (level 4)
    914523: "france",     # National 2 - C           (level 4)
    914524: "france",     # National 2 - D           (level 4)
    109288: "france",     # Trophée des Champions
    1301407: "france",    # Coupe de France
    1301408: "france",    # Coupe de la Ligue BKT
    # Portugal (IDs confirmed in the editor)
    60: "portugal",         # Primeira Liga             (level 1)
    61: "portugal",         # Segunda Liga              (level 2)
    2000015975: "portugal", # 3rd Division              (level 3)
    1301421: "portugal",    # Taça de Portugal
    55006606: "portugal",   # Taça da Liga
    11505: "portugal",      # Supertaça Cândido de Oliveira
    # Netherlands (IDs confirmed in the editor)
    29: "netherlands",        # Eredivisie                      (level 1)
    30: "netherlands",        # Keuken Kampioen Divisie         (level 2)
    37059991: "netherlands",  # Tweede Divisie                  (level 3)
    37059992: "netherlands",  # Derde Divisie - Saturday        (level 4)
    37059993: "netherlands",  # Derde Divisie - Sunday          (level 4)
    1301411: "netherlands",   # KNVB Cup
    120861: "netherlands",    # Johan Cruyff Shield
    # Turkey (IDs confirmed in the editor)
    130286: "turkey",     # Süper Lig                        (level 1)
    463479: "turkey",     # PTT 1. League                    (level 2)
    463481: "turkey",     # Spor Toto 2. League (generic)    (level 3)
    463485: "turkey",     # Spor Toto 2. League Group 1      (level 3)
    463486: "turkey",     # Spor Toto 2. League Group 2      (level 3)
    130284: "turkey",     # Ziraat Turkish Cup
    155007: "turkey",     # TFF Super Cup
    # TFF 3. Lig (level 4) not confirmed — recommended, not required
    # Denmark (IDs confirmed in the editor)
    6: "denmark",           # SAS Ligaen                      (level 1)
    7: "denmark",           # 1. Division                     (level 2)
    8: "denmark",           # 2. Division                     (level 3)
    2000016262: "denmark",  # 3rd Division                    (level 4)
    1301406: "denmark",     # DBU Pokalen
    920953: "denmark",      # Danish Super Cup (defunct in database — included for historical records)
    # Greece (IDs confirmed in the editor)
    129650: "greece",     # Super League Greece              (level 1)
    129651: "greece",     # Football League (2nd div)        (level 2)
    690094: "greece",     # Gamma Ethniki (generic)          (level 3)
    694365: "greece",     # Gamma Ethniki - South            (level 3)
    129649: "greece",     # Greek Cup
    # TODO: confirm in the editor — Gamma Ethniki - North (level 3), if it exists in the database
    # Super cup and level 4 not confirmed — recommended, not required
    # Brazil (IDs confirmed in the editor)
    102423: "brazil",     # Brasileirão Série A              (level 1)
    107191: "brazil",     # Brasileirão Série B              (level 2)
    107192: "brazil",     # Brasileirão Série C              (level 3)
    19127222: "brazil",   # Brasileirão Série D              (level 4)
    102427: "brazil",     # Copa do Brasil
    19106793: "brazil",   # Supercopa do Brasil
    102426: "brazil",     # Campeonato Paulista
    102424: "brazil",     # Campeonato Carioca
    309682: "brazil",     # Campeonato Mineiro
    302205: "brazil",     # Campeonato Gaúcho
    309678: "brazil",     # Campeonato Baiano
    309688: "brazil",     # Campeonato Catarinense
    309697: "brazil",     # Copa do Nordeste
    # Uruguay (IDs confirmed in the editor)
    80: "uruguay",          # D1 (variant)             (level 1)
    81: "uruguay",          # D1 (variant)             (level 1)
    215831: "uruguay",      # D1 (variant)             (level 1)
    5512770: "uruguay",     # D1 (variant)             (level 1)
    5512771: "uruguay",     # D2                       (level 2)
    78102476: "uruguay",    # Copa Uruguay
    # Chile (IDs confirmed in the editor)
    83: "chile",            # D1 (variant)             (level 1)
    217965: "chile",        # D1 (variant)             (level 1)
    82: "chile",            # D1 (variant)             (level 1)
    5250792: "chile",       # D1 (generic)             (level 1)
    5250793: "chile",       # D2                       (level 2)
    5251645: "chile",       # Copa Chile
    # Colombia (IDs confirmed in the editor)
    77: "colombia",         # D1 (variant)             (level 1)
    76: "colombia",         # D1 (variant)             (level 1)
    5260948: "colombia",    # D1 (generic)             (level 1)
    79: "colombia",         # D2 (variant)             (level 2)
    5260950: "colombia",    # D2 (generic)             (level 2)
    157425: "colombia",     # Copa Colombia
    # Paraguay (IDs confirmed in the editor)
    79010950: "paraguay",   # D1                       (level 1)
    79010962: "paraguay",   # D2                       (level 2)
    79032895: "paraguay",   # Copa Paraguay
    # Peru (IDs confirmed in the editor)
    5290551: "peru",        # D1 (generic)             (level 1)
    215854: "peru",         # D1 (variant)             (level 1)
    215853: "peru",         # D1 (variant)             (level 1)
    215852: "peru",         # D1 (variant)             (level 1)
    5290553: "peru",        # D2                       (level 2)
    77062856: "peru",       # Copa Perú
    # Bolivia (IDs confirmed in the editor)
    86000000: "bolivia",    # D1                       (level 1)
    86009019: "bolivia",    # D2                       (level 2)
    86019125: "bolivia",    # Copa Bolivia
    # Ecuador (IDs confirmed in the editor)
    80000566: "ecuador",    # D1                       (level 1)
    80000567: "ecuador",    # D2                       (level 2)
    2000015109: "ecuador",  # Copa Ecuador
    # Venezuela (IDs confirmed in the editor)
    86000001: "venezuela",  # D1                       (level 1)
    86000002: "venezuela",  # D2                       (level 2)
    19166135: "venezuela",  # Copa Venezuela
    # Argentina (IDs confirmed in the editor)
    102421: "argentina",  # Primera División (generic)        (level 1)
    74: "argentina",      # Primera División - Apertura       (level 1)
    75: "argentina",      # Primera División - Clausura       (level 1)
    102422: "argentina",  # Segunda División                  (level 2)
    108508: "argentina",  # Liga Metropolitana B              (level 3)
    108573: "argentina",  # Third Division (generic)          (level 3)
    108509: "argentina",  # Liga Interior A                   (level 3/4 regional)
    14037261: "argentina",# Liga Interior B                   (level 4 regional)
    14043892: "argentina",# Copa Argentina
    223470: "argentina",  # Copa de la Superliga
    216347: "argentina",  # Pre-Libertadores Argentina
    14063636: "argentina",# Supercopa Argentina
    # ── UNCONFIRMED IDs — commented out until validated in the editor ──────
    # Netherlands level 5+ discarded by default (semi-professional)
    # Belgium:    40
    # Switzerland:      50
}

# Nation IDs confirmed in the FM 2021 editor.
# NEVER guess — always confirm in the editor before adding.
NNAT_NATION = {
    764: "denmark",      # confirmed in the editor
    772: "greece",       # confirmed in the editor
    776: "italy",        # confirmed in the editor
    # confirmed in this session:
    119: "kazakhstan",
    752: "albania",
    753: "andorra",
    754: "armenia",
    755: "austria",
    756: "azerbaijan",
    757: "belgium",
    758: "belarus",
    759: "bosnia",
    760: "bulgaria",
    761: "croatia",
    762: "cyprus",
    763: "czech_republic",
    765: "england",
    766: "estonia",
    767: "faroe_islands",
    768: "finland",
    769: "france",           # confirmed in the editor
    770: "georgia",
    771: "germany",
    773: "hungary",
    774: "iceland",
    775: "israel",
    777: "latvia",
    778: "liechtenstein",
    779: "lithuania",
    780: "luxembourg",
    781: "macedonia",        # confirmed in the editor (was "ireland" — incorrect)
    782: "malta",
    783: "moldova",
    784: "netherlands",      # confirmed in the editor
    785: "northern_ireland", # confirmed in the editor (was "norway" — incorrect; Norway = 786)
    786: "norway",           # confirmed in the editor
    787: "poland",
    788: "portugal",         # confirmed in the editor
    789: "ireland",          # confirmed in the editor (was "scotland" — incorrect; Scotland = 793)
    790: "romania",
    791: "russia",
    792: "san_marino",
    793: "scotland",         # confirmed in the editor
    794: "slovakia",
    795: "slovenia",
    796: "spain",
    797: "sweden",
    798: "switzerland",
    799: "turkey",           # confirmed in the editor
    800: "ukraine",
    801: "wales",
    802: "serbia",
    62002127: "montenegro",
    214394: "gibraltar",
    215446: "crimea",
    217945: "kosovo",
    # Africa (IDs confirmed in the editor)
    5: "algeria",
    6: "angola",
    9: "burkina_faso",
    11: "cameroon",
    16: "egypt",
    21: "ghana",
    24: "ivory_coast",
    31: "mali",
    34: "morocco",
    38: "nigeria",
    41: "senegal",
    45: "south_africa",
    49: "congo",
    51: "tunisia",
    53: "dr_congo",
    54: "zambia",
    # Asia (IDs confirmed in the editor)
    106: "afghanistan",
    107: "bahrain",
    108: "bangladesh",
    109: "brunei",
    110: "china",
    111: "hong_kong",
    112: "india",
    113: "indonesia",
    114: "iran",
    115: "iraq",
    116: "japan",
    117: "jordan",
    118: "cambodia",
    120: "kuwait",
    121: "kyrgyzstan",
    123: "lebanon",
    124: "macau",
    125: "malaysia",
    126: "maldives",
    127: "myanmar",
    128: "nepal",
    129: "north_korea",
    130: "oman",
    131: "pakistan",
    132: "qatar",
    133: "saudi_arabia",
    134: "singapore",
    135: "south_korea",
    136: "sri_lanka",
    137: "syria",
    138: "chinese_taipei",
    139: "tajikistan",
    140: "thailand",
    141: "philippines",
    142: "turkmenistan",
    143: "uae",
    144: "uzbekistan",
    145: "vietnam",
    146: "yemen",
    1435: "australia",
    1662: "palestine",
    5626837: "timor_leste",
    129505: "mongolia",
    129508: "guam",
    131012: "bhutan",
    23008660: "northern_mariana_islands",
    156: "peru",            # confirmed in the editor
    1649: "argentina",      # confirmed in the editor
    1650: "bolivia",        # confirmed in the editor
    1651: "brazil",         # confirmed in the editor
    1652: "chile",          # confirmed in the editor
    1653: "colombia",       # confirmed in the editor
    1654: "ecuador",        # confirmed in the editor
    1655: "paraguay",       # confirmed in the editor (was "uruguay" — incorrect)
    1657: "uruguay",        # confirmed in the editor
    1658: "venezuela",      # confirmed in the editor
    364: "canada",          # confirmed in the editor
    366: "costa_rica",      # confirmed in the editor
    375: "haiti",           # confirmed in the editor
    376: "honduras",        # confirmed in the editor
    377: "jamaica",         # confirmed in the editor
    379: "mexico",          # confirmed in the editor
    382: "panama",          # confirmed in the editor
    389: "trinidad_tobago", # confirmed in the editor
    390: "usa",             # confirmed in the editor
}

# ── Regions ───────────────────────────────────────────────────────
# Brazil and Argentina are excluded — generated separately as individual countries.
# To add a new region: list nation names exactly as they appear in COMP_NATION / NNAT_NATION.
REGIONS = {
    "south_america": [
        "chile", "colombia", "uruguay", "paraguay",
        "peru", "bolivia", "ecuador", "venezuela",
    ],
    "north_america": [
        "mexico", "usa", "canada", "costa_rica",
        "honduras", "panama", "jamaica", "haiti", "trinidad_tobago",
    ],
    "africa": [
        "ivory_coast", "algeria", "ghana", "cameroon", "tunisia",
        "egypt", "nigeria", "south_africa", "morocco", "zambia",
        "senegal", "burkina_faso", "mali", "dr_congo", "congo", "angola",
    ],
    "asia": [
        "japan", "south_korea", "australia", "iran", "saudi_arabia",
        "syria", "uzbekistan", "uae", "kuwait", "china",
        "iraq", "jordan", "thailand", "oman", "north_korea",
        "bahrain", "lebanon", "turkmenistan", "kyrgyzstan", "indonesia",
        "philippines", "vietnam", "malaysia", "palestine", "yemen",
        "hong_kong", "myanmar", "guam", "tajikistan", "india",
        "singapore", "maldives", "qatar", "afghanistan", "bangladesh",
        "chinese_taipei", "pakistan", "sri_lanka", "nepal", "mongolia",
        "cambodia", "timor_leste", "brunei", "macau", "bhutan",
        "northern_mariana_islands",
    ],
    # Excluded: italy, spain, england, germany, scotland, france, portugal,
    #           netherlands, turkey, denmark, greece — generated individually
    "europe_other": [
        "ireland", "northern_ireland", "wales",
        "norway", "sweden", "finland", "iceland", "faroe_islands",
        "belgium", "switzerland", "austria", "luxembourg", "liechtenstein",
        "russia", "ukraine", "belarus", "moldova",
        "poland", "czech_republic", "slovakia", "hungary", "romania", "bulgaria",
        "croatia", "serbia", "slovenia", "bosnia", "montenegro",
        "macedonia", "albania", "kosovo", "cyprus", "malta", "gibraltar",
        "georgia", "armenia", "azerbaijan", "kazakhstan",
        "estonia", "latvia", "lithuania",
        "israel", "andorra", "san_marino", "crimea",
    ],
}

TARGET_NATIONS = frozenset(REGIONS[TARGET]) if TARGET in REGIONS else frozenset([TARGET])

# ── Record streamer ───────────────────────────────────────────────
def stream_records(fpath):
    """Yield (rec_type, prop, uid, blob) for every top-level <record> block."""
    in_rec = False
    depth  = 0
    rtype = prop = uid = None
    lines = []

    with open(fpath, "r", encoding="utf-8", errors="replace") as f:
        for line in f:
            content = line.rstrip("\n\r")

            if not in_rec:
                if content == "\t\t<record>":
                    in_rec = True
                    depth  = 0
                    rtype = prop = uid = None
                    lines = [content]
                continue

            lines.append(content)
            s = content.strip()

            if rtype is None:
                m = TYPE_RE.search(content)
                if m: rtype = m.group(1)
            if prop is None:
                m = PROP_RE.search(content)
                if m: prop = m.group(1)
            if uid is None:
                m = UID_RE.search(content)
                if m: uid = m.group(1)

            if re.match(r"<record[\s>]", s) and not s.endswith("/>"):
                depth += 1
            elif s == "</record>":
                if depth > 0:
                    depth -= 1
                else:
                    yield rtype, prop, uid, "\n".join(lines)
                    in_rec = False
                    lines  = []

# ═══════════════════════════════════════════════════════════════════
# PASS 1 — build lookup dicts
# ═══════════════════════════════════════════════════════════════════
print("Pass 1: scanning for nation lookups...", flush=True)

uid_ttea          = {}   # uid str  → Ttea str           (from Pcti new_value)
uid_prev_ttea     = {}   # uid str  → prev Ttea str      (from Pcti odvl — departure tracking)
uid_nnat          = {}   # uid str  → Nnat int            (from Pnti)
ttea_nation       = {}   # Ttea str → nation str          (from Plhs × COMP_NATION)
ttea_best_year    = {}   # Ttea str → best year int       (for recency tie-break)
club_uid_nation   = {}   # club db_unique_id → nation str  (from Cdvi)
club_clhs_entries = {}   # club uid → {year: comp_id}        (from Clhs)

n = 0
for rtype, prop, uid, blob in stream_records(filepath):
    n += 1
    if n % 300_000 == 0:
        print(f"  {n:>9,} recs | uid_ttea={len(uid_ttea):,}"
              f"  ttea_nat={len(ttea_nation):,}"
              f"  clubs={len(club_uid_nation):,}", flush=True)

    if rtype == "1":
        if prop == PCTI_PROP:
            if uid:
                # Parse new_value and odvl separately so <null id="new_value"/> cases
                # (contract deletion) don't accidentally inherit the odvl Ttea as new club.
                nv_m = NEWVAL_TTEA_RE.search(blob)
                if nv_m and nv_m.group(1) != FREE_AGENT_TTEA:
                    uid_ttea[uid] = nv_m.group(1)
                od_m = ODVL_TTEA_RE.search(blob)
                if od_m and od_m.group(1) != FREE_AGENT_TTEA:
                    uid_prev_ttea[uid] = od_m.group(1)

        elif prop == PNTI_PROP:
            ns = NNAT_RE.findall(blob)
            if ns and uid:
                uid_nnat[uid] = int(ns[0])

        elif prop == PLHS_PROP:
            ts = TTEA_RE.findall(blob)
            cs = COMP_RE.findall(blob)
            ys = YEAR_RE.findall(blob)
            if ts and cs:
                t = ts[0]
                y = int(ys[0]) if ys else 0
                for c_s in cs:
                    c = int(c_s)
                    if c in COMP_NATION:
                        if t not in ttea_best_year or y > ttea_best_year[t]:
                            ttea_best_year[t] = y
                            ttea_nation[t]    = COMP_NATION[c]
                        break   # first recognised competition per record is enough

    elif rtype == "3" and prop == CDVI_PROP and uid:
        for c_s in COMP_RE.findall(blob):
            c = int(c_s)
            if c in COMP_NATION:
                club_uid_nation[uid] = COMP_NATION[c]
                break

    elif rtype == "3" and prop == CLHS_PROP and uid:
        cs = COMP_RE.findall(blob)
        ys = YEAR_RE.findall(blob)
        if ys and cs:
            comp = int(cs[0])
            if comp in COMP_NATION:
                year = int(ys[0])
                club_clhs_entries.setdefault(uid, {})[year] = comp

print(f"\nPass 1 done. {n:,} records scanned.")
print(f"  uid_ttea:        {len(uid_ttea):,}")
print(f"  uid_nnat:        {len(uid_nnat):,}")
print(f"  ttea_nation:     {len(ttea_nation):,}")
print(f"  club_uid_nation: {len(club_uid_nation):,}")

# Resolve uid → nation
uid_nation = {}

# Primary: current club chain
for uid, ttea in uid_ttea.items():
    nat = ttea_nation.get(ttea)
    if nat:
        uid_nation[uid] = nat

# Fallback: nationality
for uid, nnat in uid_nnat.items():
    if uid not in uid_nation:
        nat = NNAT_NATION.get(nnat)
        if nat:
            uid_nation[uid] = nat

target_person_uids = frozenset(u for u, nat in uid_nation.items() if nat in TARGET_NATIONS)

# Fix 3 — capture departure records: persons whose prev club (prev_ttea) was a TARGET
# club in the FM 2021 base but whose 2001/02 club is non-TARGET
# (e.g. Fonseca: Roma→Portugal). Without these, FM keeps showing them at their
# old FM 2021 TARGET club.
departure_uids = frozenset(
    u for u, prev_t in uid_prev_ttea.items()
    if prev_t in ttea_nation
    and ttea_nation[prev_t] in TARGET_NATIONS
    and u not in target_person_uids
)
target_person_uids = target_person_uids | departure_uids

# Fix 1 — extend target_club_uids with Ttea-derived UIDs so we capture
# all type=3 club records (reputation, finances, history…) for clubs that
# have no Cdvi record in the patch (they were already in the correct division
# in FM 2021 base, so the patch records no change).
cdvi_club_uids = frozenset(u for u, nat in club_uid_nation.items() if nat in TARGET_NATIONS)
for ttea_str, nat in ttea_nation.items():
    ttea_uid = str(int(ttea_str) * MULT)
    if ttea_uid not in club_uid_nation:
        club_uid_nation[ttea_uid] = nat
target_club_uids = frozenset(u for u, nat in club_uid_nation.items() if nat in TARGET_NATIONS)

# Fix 2 — build synthetic Cdvi/Cldi records for clubs that have no Cdvi
# in the patch but DO have Clhs entries, so FM 2024 places them in the
# correct 2001/02 division instead of the current (2023-24) one.
ttea_only_uids = target_club_uids - cdvi_club_uids
synthetic_cdvi = {}   # uid → (curr_comp, cldi_comp)
for uid in ttea_only_uids:
    entries = club_clhs_entries.get(uid, {})
    valid = {y: c for y, c in entries.items() if y <= SEASON_END_YEAR}
    if not valid:
        continue
    best_year = max(valid)
    curr_comp = valid[best_year]
    prev_valid = {y: c for y, c in valid.items() if y < best_year}
    cldi_comp = prev_valid[max(prev_valid)] if prev_valid else curr_comp
    synthetic_cdvi[uid] = (curr_comp, cldi_comp)

# Competition entity UIDs — only captured for rtype=25 (avoids collision with nation IDs
# that share the same integer, e.g. comp 34=Serie C1/A and nation 34=Morocco).
target_comp_uids = frozenset(
    str(c * MULT) for c, nat in COMP_NATION.items() if nat in TARGET_NATIONS
)

# Nation entity UIDs — only captured for rtype=9 (NTRv/NWGv financial records).
target_nation_uids = frozenset(
    str(n * MULT) for n, nat in NNAT_NATION.items() if nat in TARGET_NATIONS
)

# Summary by nation
from collections import Counter
nat_counts = Counter(uid_nation.values())
print(f"\nuid_nation summary (top 15):")
for nat, cnt in nat_counts.most_common(15):
    marker = " <-- TARGET" if nat in TARGET_NATIONS else ""
    print(f"  {nat:15}  {cnt:>7,}{marker}")

print(f"\nPersons        : {len(target_person_uids):,}  (incl. {len(departure_uids):,} departure records)")
print(f"Clubs (cdvi)   : {len(cdvi_club_uids):,}")
print(f"Clubs (+ttea)  : {len(target_club_uids):,}  (+{len(target_club_uids) - len(cdvi_club_uids):,} via Ttea)")
print(f"Synthetic cdvi : {len(synthetic_cdvi):,}  clubs need synthetic Cdvi/Cldi")
print(f"Comp UIDs      : {len(target_comp_uids):,}  (competition entity records, rtype=25)")
print(f"Nation UIDs    : {len(target_nation_uids):,}  (nation financial records, rtype=9 only)", flush=True)

# ═══════════════════════════════════════════════════════════════════
# PASS 2 — write output file
# ═══════════════════════════════════════════════════════════════════
os.makedirs(output_dir, exist_ok=True)
out_path = os.path.join(output_dir, f"{TARGET}.xml")


def _synth_record(uid, prop_id, new_value_lines):
    parts = [
        "\t\t<record>",
        '\t\t\t<integer id="database_table_type" value="3"/>',
        f'\t\t\t<large id="db_unique_id" value="{uid}"/>',
        f'\t\t\t<unsigned id="property" value="{prop_id}"/>',
    ]
    parts.extend(new_value_lines)
    parts += [
        '\t\t\t<integer id="version" value="2959"/>',
        f'\t\t\t<integer id="db_random_id" value="{random.randint(1, 999_999_999)}"/>',
        '\t\t\t<boolean id="is_client_field" value="true"/>',
        "\t\t</record>",
    ]
    return "\n".join(parts)


def _synth_cdvi(uid, comp_id):
    return _synth_record(uid, CDVI_PROP, [
        '\t\t\t<record id="new_value">',
        f'\t\t\t\t<integer id="competition" value="{comp_id}"/>',
        '\t\t\t</record>',
    ])


def _synth_cldi(uid, comp_id):
    return _synth_record(uid, CLDI_PROP, [
        '\t\t\t<record id="new_value">',
        f'\t\t\t\t<integer id="competition" value="{comp_id}"/>',
        '\t\t\t</record>',
    ])


def is_target(rtype, prop, uid, blob):
    if uid in target_person_uids:
        return True
    if uid in target_club_uids:
        return True
    if rtype == "25":
        # Direct competition entity records (uid IS the competition's own UID)
        if uid in target_comp_uids:
            return True
        # Competition HISTORY records: have their own UID but reference a TARGET
        # competition via an internal <integer id="competition" value="..."/> field.
        # This captures clearing/updating records (e.g. nulling out the record-goals
        # scorer) whose own UID is not the competition's entity UID.
        for c_s in COMP_RE.findall(blob):
            if int(c_s) in COMP_NATION and COMP_NATION[int(c_s)] in TARGET_NATIONS:
                return True
    # Nation financial records (rtype=9 only — NTRv/NWGv)
    if rtype == "9" and uid in target_nation_uids:
        return True
    for p in PERS_RE.findall(blob):
        if p in target_person_uids:
            return True
    return False


print(f"\nPass 2: writing {out_path}...", flush=True)

HEADER_LINES = 16   # lines 1-16 of source (up to and including <list id="db_changes">)

written = skipped = 0
TOTAL_EST = 1_141_867   # approximate, for progress %

with open(out_path, "w", encoding="utf-8") as out:

    # ── Header (copy lines 1-16 verbatim) ────────────────────────
    with open(filepath, "r", encoding="utf-8", errors="replace") as src:
        for i, line in enumerate(src, 1):
            out.write(line)
            if i == HEADER_LINES:
                break

    # ── Records ──────────────────────────────────────────────────
    for rtype, prop, uid, blob in stream_records(filepath):
        if is_target(rtype, prop, uid, blob):
            out.write(blob + "\n")
            written += 1
        else:
            skipped += 1

        done = written + skipped
        if done % 200_000 == 0:
            pct = done * 100 / TOTAL_EST
            print(f"  {done:>9,} ({pct:.0f}%) | written={written:,}  skipped={skipped:,}",
                  flush=True)

    # ── Synthetic division records (Fix 2) ───────────────────────
    for uid, (curr_comp, cldi_comp) in sorted(synthetic_cdvi.items()):
        out.write(_synth_cdvi(uid, curr_comp) + "\n")
        out.write(_synth_cldi(uid, cldi_comp) + "\n")
        written += 2

    # ── Footer ───────────────────────────────────────────────────
    out.write("\t</list>\n</record>\n")

print(f"\nDone.")
print(f"  Written : {written:,} records")
print(f"  Skipped : {skipped:,} records")
print(f"  Output  : {out_path}")
