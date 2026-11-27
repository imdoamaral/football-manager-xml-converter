# FM XML Converter

Python scripts that split a Football Manager XML patch file by country and convert it between FM versions. Built for the FM 2001/02 retro database (FM 2021 → FM 2024), but the approach generalises to any FM version pair.

This is not a plug-and-play tool — it is a **reference implementation**. The scripts are the contribution; adapting them to a different version pair requires rediscovering record formats, version numbers and IDs specific to your FM versions (see `CLAUDE.md`).

---

## Scripts

| Script | What it does |
|---|---|
| `split_fm_xml.py <country>` | Streams the FM 2021 master patch and writes `output/fm21/<country>.xml` with the records of that country's persons, clubs and competitions (including `ADDR` creation records). |
| `convert_to_fm24.py <country>` | Converts it to `output/fm24/<country>_fm24_final.xml` for the FM 2024 editor (record format, references, history, dates, person creation — see below). `--auto-deletes` also deletes FM24-only history/legend rows (off by default). |
| `build_checklist.py <country>` | Writes `output/fm24/<country>_checklist.md`: what to check and what to delete by hand in the FM 2024 editor after importing. |
| `build_club_history.py <country>` | Optional. Builds the FM24-only club/competition history rows (seasons 2020/21–2022/23) from real league tables on Wikipedia → `reference/club_history/<country>.json`; used by the checklist and by `--auto-deletes`. |

## Workflow per country

1. Confirm in the FM 2021 editor the minimum IDs: nation + divisions 1–3 + main cup (never guess IDs).
2. `python split_fm_xml.py <country>` → `python convert_to_fm24.py <country>` → `python build_checklist.py <country>`.
3. Import `<country>_fm24_final.xml` in the FM 2024 editor, check a few squads, then work through the checklist.

**FM 2021 export (recommended):** start a game in FM 2021 with the retro database, and save with Ctrl+P (text) the player search and the staff search with all players/staff, using a view with the *Unique ID*, *Name* and *Nationality* columns, as `anexos-claude/fm21_*.rtf`. The club you manage in that game is excluded from the searches — export its squad and staff screens too. The converter uses it to name persons the patch only partially describes.

## What the converter does (FM 2021 → FM 2024)

- **Record format**: version 3569, header/footer as saved by the FM 2024 editor; entity references become `<large>` uid + `DBID` (no `DBID` in old-value blocks).
- **Mod-created persons**: copied with their `ADDR` creation record (they include players and staff such as managers).
- **Persons that exist only in the FM 2021 base**: a creation record is added for every FM 2021 base person in the patch — harmless for persons that already exist in FM 2024, and it creates the ones FM 2024 removed. Missing name/nationality are filled from the FM 2021 export.
- **Player history**: FM 2024 list format (`trib` field); histories the mod builds from scratch are cleared first.
- **Dates**: the mod shifts person dates +19 years so FM 2021's 2020 start represents 2001; the converter adds +3 years for FM 2024's 2023 start.
- **Club relations**: favourite/disliked person lists that the mod edits are cleared (FM 2024's entries are modern-era).

## Limitations

- **Manual deletes**: FM 2024's base contains content that did not exist in FM 2021 (club and competition history 2021–2023, newer legends/icons) or that changed (some history rows, legend ratings). The mod's row-by-row deletes cannot match it, so leftovers remain; deleting is quick in the editor and the checklist lists them.
- **Pre-2001 history of recreated persons**: for FM 2021 base persons that FM 2024 removed, the patch only holds what the mod changed, so their career history before 2001 is not recreated. Persons with no name anywhere (patch or export) are not created.
- **Competition record display**: some competition records (e.g. all-time top scorer) may show current-era players. Cosmetic.
- **ID remapping (legacy)**: FM 2021 base persons with IDs 2,000,040,000–2,000,070,000 are mapped to FM 2024 with `retro_id − 60238` plus `ID_OVERRIDE` exceptions (verified for Italy). Formula collisions are blocked.
- **Inherent entity conflicts**: a person who exists in both databases with a different role (e.g. player who became a manager) gets the retro data applied over the FM 2024 entity.
- **Not automatic**: nation and competition IDs must be confirmed in the FM editor for each country.
- **Not handled yet**: award history shared by all countries (Ballon d'Or etc.), cup competition history.

---

## Adapting for other FM versions

**From the source FM (FM X):** header lines, record version numbers, FourCC property IDs (Pcti, Pnti, Plhs, Cdvi…), free-agent team ID.

**From the target FM (FM Y):** create a minimal patch in both editors (one new player with name, date of birth, nationality, club contract, one attribute and one history row; one new manager) and diff them — this reveals the creation record, reference format and list formats. Then compare editor samples whenever something fails: the FM Y editor shows a *Success* column for every change.

**Nation and competition IDs:** must be confirmed in the FM X editor — never guess.

---

## Contributing

`CLAUDE.md` holds the full context behind design decisions: confirmed IDs for nations and competitions, record formats verified in both editors, test results and next steps. Read it before extending the scripts or adding a new country or FM version.

Bugs and improvements welcome via issues or PRs.
