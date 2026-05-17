# FM XML Converter

**TL;DR:** Two Python scripts that split a Football Manager XML patch file by country and convert it between FM versions. Built for the FM 2001/02 retro database (FM 2021 → FM 2024), but the architecture generalises to any FM version pair — [see how to adapt](#adapting-for-other-fm-versions).

---

## Contents

- [What this is](#what-this-is)
- [Source file](#source-file)
- [Architecture](#architecture)
- [Usage](#usage)
- [Adapting for other FM versions](#adapting-for-other-fm-versions)
- [Project structure](#project-structure)
- [Generation status](#generation-status)
- [Contributing](#contributing)

---

## What this is

This is not a plug-and-play tool — it is a **model**: a working reference implementation that demonstrates how to approach XML splitting and format conversion between FM versions. The scripts target the FM 2001/02 retro database (FM 2021 → FM 2024), but the architecture and patterns generalise to any FM version pair.

> **Using a different FM version?** See [Adapting for other FM versions](#adapting-for-other-fm-versions) for a step-by-step checklist of what needs to be rediscovered for your specific version pair.

Two problems are solved here that will reappear in any similar project:

1. **Streaming a 400+ MB XML file** without loading it into memory — standard parsers fail at this scale.
2. **Resolving which records belong to which nation** through a multi-step lookup chain, since the patch format does not store nationality directly on every record.

The scripts are the contribution. Anyone converting a different retro database to a different FM version will need to adapt the lookup tables and header format — but the structural approach stays the same.

---

## Source file

The source patch is the **FM 2001/02 Retro Database** by The Mad Scientist:

- Steam Workshop: https://steamcommunity.com/sharedfiles/filedetails/?id=2450017250
- **To obtain the XML**: Open it in the FM 2021 editor, then export as XML. The exported file is the input for `split_fm_xml.py`.
- **XML Format**: FM 2021 differential patch — contains only changes on top of the standard database, not a full dump. The editor loads the base database and applies the patch on top.
- **Never modify the source file.**

---

## Architecture

### Step 1 — Two-pass streaming (`split_fm_xml.py`)

Loading a 400+ MB XML into memory with a standard parser is not viable. The script uses two sequential passes over the file, keeping only lightweight lookup dictionaries in RAM.

**Pass 1 — build lookup dictionaries:**

| Dictionary | Source (FourCC / prop ID) | Contents |
|---|---|---|
| `uid_ttea` | Pcti · 1348695145 | player uid → current club Ttea |
| `uid_nnat` | Pnti · 1349416041 | player uid → nationality (Nnat) |
| `ttea_nation` | Plhs · 1349281907 | club Ttea → nation (via competition) |
| `club_uid_nation` | Cdvi · 1130657385 | club db_unique_id → nation |

**Pass 2 — filter and write:**
Re-reads the file and copies to the output XML only the records whose `db_unique_id` belongs to a player or club from the target nation.

**Inclusion criteria (by priority):**
1. Player with contract at a club in the target nation → Pcti → Ttea → Plhs competition → COMP_NATION
2. Club currently in a division of the target nation → Cdvi → competition → COMP_NATION
3. Fallback: player with nationality of the target nation → Pnti → Nnat → NNAT_NATION
4. Award/history record with a `Pers` field pointing to a player in the target nation

### Step 2 — Format conversion (`convert_to_fm24.py`)

Converts the FM 2021 XML into the format accepted by the FM 2024 editor. Three things change between versions:

| What changes | Detail |
|---|---|
| Header | The first ~16 lines before `<list id="db_changes">` have a different structure |
| `version` per record | Each record carries a version number; 2959/2961 (FM21) → 3567 (FM24) |
| Removed fields | `is_client_field` was removed in FM 2024, replaced by `odvl` |

### `db_unique_id` encoding formula

The FM database encodes player IDs in the XML as:

```
db_unique_id = player_id × (2³² + 1)
```

This is not documented anywhere officially. It was reverse-engineered by observing that `db_unique_id mod (2³² + 1) == 0` for all valid player records, with the quotient being the actual player ID. This formula is used in `convert_to_fm24.py` to identify and remap problematic IDs.

### ID remapping

The retro database was built in FM 2021. Some players did not exist in the FM 2021 base database and were created with new IDs in the range `2,000,045,xxx`–`2,000,067,xxx`. These IDs do not exist in the FM 2024 base database, which silently ignores them on import.

**Remapping formula:**
```
player_id_fm24 = player_id_retro - 60238
```

The offset 60238 was derived from a single known case (Totti: retro 2000066931 → FM 2024 2000006693) and verified against 46 players across Italy and Spain. The conversion script applies this automatically to any ID in the problematic range.

---

## Usage

**Requirements:** Python 3.8+, standard library only — no `pip install` needed.

### Step 1 — Split by country

```bash
python split_fm_xml.py italy
python split_fm_xml.py england
python split_fm_xml.py south_america   # regional bundles are also supported
```

Output: `output/fm21/<country>.xml`

Available targets:

| Individual countries | Regional bundles |
|---|---|
| `italy`, `spain`, `england`, `germany` | `south_america` |
| `scotland`, `france`, `portugal`, `netherlands` | `north_america` |
| `turkey`, `denmark`, `greece`, `brazil`, `argentina` | `europe_other`, `asia`, `africa` |

### Step 2 — Convert to FM 2024

```bash
python convert_to_fm24.py italy
python convert_to_fm24.py england
```

Output: `output/fm24/<country>_fm24_final.xml`

The generated file can be imported directly in the FM 2024 editor.

---

## Adapting for other FM versions

To adapt these scripts for a different FM version pair (FM X → FM Y), here is what needs to be rediscovered:

**From the source FM (FM X):**
- [ ] **Header format**: the lines before `<list id="db_changes">` in the XML — count them and copy verbatim in your output
- [ ] **Record version numbers**: grep the source XML for `id="version"` to find what values appear
- [ ] **FourCC property IDs**: the integer codes for current contract (Pcti), nationality (Pnti), league history (Plhs), and club division (Cdvi) — these may differ between FM versions; confirm by inspecting records in the FM editor
- [ ] **Free agent team ID** (`FREE_AGENT_TTEA`): the virtual team that holds uncontracted players; must be excluded from club lookups

**From the target FM (FM Y):**
- [ ] **Header format**: open any FM Y patch file and inspect the first ~20 lines
- [ ] **Record version number**: same approach — grep for `id="version"`
- [ ] **Removed or renamed fields**: compare a sample record in FM X vs FM Y; fields appear and disappear between versions (e.g., `is_client_field` was removed in FM 2024)

**ID remapping:**
- [ ] Import a country's XML into the target FM editor; records that fail to appear are likely in the problematic ID range
- [ ] Find one known player who exists in both the retro patch and the target FM's base database; compare the two `player_id` values to derive the offset
- [ ] Verify the offset with at least 5–10 other players before applying it globally
- [ ] The `db_unique_id = player_id × (2³² + 1)` encoding may also vary — verify it holds for your FM version

**Nation and competition IDs:**
- [ ] Must be confirmed in the FM X editor — never guess. IDs for the same competition can differ between FM versions.
- [ ] Follow the minimum standard: nation ID + divisions 1–3 + main cup are required before generating any country XML

---

## Project structure

```
fm-database-converter/
├── split_fm_xml.py             # Step 1: split master XML by country (FM 2021 format)
├── convert_to_fm24.py          # Step 2: convert FM 2021 → FM 2024
├── output/
│   ├── fm21/                   # Generated XMLs for the FM 2021 editor (gitignored)
│   └── fm24/                   # Generated XMLs for the FM 2024 editor (gitignored)
└── reference/
    ├── mapeamento_ids.csv          # ID mapping investigation (initial)
    └── mapeamento_ids_filled.csv   # ID mapping with player names (verified)
```

The `output/` directories are gitignored — all files there are generated artifacts. Run the scripts to reproduce them.

---

## Generation status

| Country | FM 2021 | FM 2024 | Records |
|---|---|---|---|
| Italy | ✅ tested | ✅ tested (all 28 remapped players imported) | 113,953 |
| Spain | ✅ tested | ⏳ pending test | 91,597 |
| England | ✅ tested | ⏳ pending test | 144,808 |
| Germany | ✅ tested | ⏳ pending test | 38,862 |
| Scotland | ✅ tested | ⏳ pending test | 34,592 |
| France | ✅ tested | ⏳ pending test | 45,309 |
| Portugal, Netherlands, Turkey, Denmark, Greece | ✅ generated | ⏳ pending test | — |
| Brazil, Argentina, South America, North America | ✅ generated | ⏳ pending test | — |
| Europe Other, Asia, Africa | ✅ generated | ⏳ pending test | — |

---

## Contributing

The project includes a `CLAUDE.md` file with the full context behind design decisions: confirmed IDs for nations and competitions, inclusion criteria, ID remapping details, and generation status per country. If you want to extend the scripts or add support for a new country or FM version, read `CLAUDE.md` first — it will save significant reverse-engineering time.

Bugs and improvements welcome via issues or PRs.

---

**TL;DR:** Two Python scripts — one splits a 400+ MB FM XML patch file by country without loading it into memory, the other converts the output between FM versions. Built for FM 2001/02 (FM 2021 → FM 2024). Adapting to a different version pair requires rediscovering header formats, version numbers, and ID offsets — see [Adapting for other FM versions](#adapting-for-other-fm-versions).
