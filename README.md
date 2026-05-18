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
- **ID remapping duplicates**: remapping player IDs to fit the target FM's range can produce duplicate entries for players who also exist in the target FM's base database (e.g. as retired persons). Easy to resolve manually in the editor.
- **Not automatic**: nation and competition IDs must be confirmed in the FM editor for each country before generating an XML. The script cannot discover these automatically.

---

## Contributing

The project includes a `CLAUDE.md` file with the full context behind design decisions: confirmed IDs for nations and competitions, inclusion criteria, ID remapping details, and known limitations per country. Read it before extending the scripts or adding support for a new country or FM version — it will save significant reverse-engineering time.

Bugs and improvements welcome via issues or PRs.
