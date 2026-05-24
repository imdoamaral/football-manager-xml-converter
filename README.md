# FM XML Converter

Two Python scripts that split a Football Manager XML patch file by country and convert it between FM versions. Built for the FM 2001/02 retro database (FM 2021 → FM 2024), but the architecture generalises to any FM version pair.

This is not a plug-and-play tool — it is a **reference implementation**. The scripts are the contribution; adapting them to a different version pair requires rediscovering header formats, version numbers, and ID offsets specific to your FM versions.

---

## Adapting for other FM versions

To adapt for a different FM version pair (FM X → FM Y):

**From the source FM (FM X):**
- [ ] Header format: the lines before `<list id="db_changes">` — count and copy verbatim
- [ ] Record version numbers: grep for `id="version"` in the source XML
- [ ] FourCC property IDs for Pcti, Pnti, Plhs, Cdvi — confirm in the FM editor; may differ between versions
- [ ] Free agent team ID: the virtual team for uncontracted players; must be excluded from club lookups

**From the target FM (FM Y):**
- [ ] Header format: inspect the first ~20 lines of any FM Y patch file
- [ ] Record version number: same — grep for `id="version"`
- [ ] Removed or renamed fields: compare a sample record in FM X vs FM Y

**ID remapping:**
- [ ] Import a country's XML into the target FM; records that fail to appear are likely in the problematic ID range
- [ ] Find one known player in both the retro patch and the target FM base database; compare `player_id` values to derive the offset
- [ ] Verify with at least 5–10 other players before applying globally

**Nation and competition IDs:**
- [ ] Must be confirmed in the FM X editor — never guess
- [ ] Minimum required: nation ID + divisions 1–3 + main cup, per country

---

## Limitations

- **Coaching staff**: manager and coach contracts simply do not exist in the source XML. Workaround: assign managers manually in the FM editor after importing.
- **Competition record display**: some competition fields (e.g. all-time record scorer) may show current-era players despite the retro patch including a clearing record. This is an FM engine display artefact, not a script bug — cosmetic only, does not affect gameplay.
- **ID remapping — formula exceptions**: the default offset formula (`retro_id − 60238`) works for most retro-created players, but has three categories of exception, all handled via `ID_OVERRIDE` in `convert_to_fm24.py`:
  - *Formula ID exists but is a different person in FM24* (collision): remap is blocked; retro data for that player is silently dropped.
  - *Formula ID does not exist and player has a different FM24 ID* (retired person / non-player): overridden to the correct FM24 entity ID.
  - *Formula ID does not exist and player has no FM24 entity at all*: retro data is silently dropped — that player will not appear in FM24.
  Exceptions verified for Italy (2026-05-23); other countries handled on demand when issues are found after import.
- **Normal-range entity_ids absent from FM24 base**: beyond the problematic ID range, some players who exist in the FM21 base database also have no matching entity in FM24's base. Their records are present in the converted XML but FM24 silently ignores them on import. Fix requires identifying their correct FM24 entity_ids (if any) and extending `convert_to_fm24.py` with per-record uid recomputation. Confirmed for ~19 Roma players (2026-05-23).
- **Players with no records in the source patch**: if a player was already at their correct club in the FM21 base database and the retro mod made no changes for them, MASTER.xml contains zero records for that player. `split_fm_xml.py` cannot capture them (they appear in no lookup table), so they are absent from the output XML entirely. This is a source-data limitation — not fixable without injecting synthetic record. Direct `.fmf` database manipulation has been investigated and ruled out (proprietary binary, no public tooling).
- **ID remapping duplicates**: for players whose formula ID maps to a retired/non-player entity in FM24, importing creates a second entry alongside the FM24 base version. Easy to resolve manually in the editor.
- **Inherent entity conflicts**: players who exist in both the retro patch and the FM24 base database but with different roles (e.g. a player who became a manager by FM24) will have their FM24 data overwritten by the retro import. This is a limitation of the differential patch format — the retro update cannot distinguish whether the target entity has changed role.
- **Not automatic**: nation and competition IDs must be confirmed in the FM editor for each country before generating an XML. The script cannot discover these automatically.

---

## Contributing

The project includes a `CLAUDE.md` file with the full context behind design decisions: confirmed IDs for nations and competitions, inclusion criteria, ID remapping details, and known limitations per country. Read it before extending the scripts or adding support for a new country or FM version — it will save significant reverse-engineering time.

Bugs and improvements welcome via issues or PRs.
