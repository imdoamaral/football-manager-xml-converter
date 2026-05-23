# FM Retro Database 2001/02 — Project Context

## Objective
Split the FM 2021 patch file into separate XMLs by country (italy.xml, spain.xml, etc.)
and convert them to the FM 2024 format.

## Project structure
```
fm-retro/
├── split_fm_xml.py       # Step 1: generates output/fm21/<country>.xml from the FM 2021 master
├── convert_to_fm24.py    # Step 2: converts FM 2021 → FM 2024 (output/fm24/<country>_fm24_final.xml)
├── output/
│   ├── fm21/             # XMLs for the FM 2021 editor
│   └── fm24/             # XMLs for the FM 2024 editor
└── reference/            # Investigation and reference files (not used in production)
    ├── fm2024_one_att_change.xml
    ├── The 2007 08 DB.xml
```

---

## Source file (read-only)
- **Path**: `football-manager-xml-converter\The 2001 02 DB MASTER.xml`
- **Size**: 483 MB · 13,102,216 lines · 1,141,867 records
- **Format**: FM 2021 differential patch — contains only changes on top of the standard database,
  not a full dump. The editor loads the standard database and applies the patch on top.
- **NEVER modify this file.**

---

## Step 1 — split_fm_xml.py (FM 2021)

Two streaming read passes (never loads everything into RAM).

```
# To generate a country:
# python split_fm_xml.py <country>
# Output: output/fm21/<country>.xml
```

### Architecture — Step 1 (lookups)
Reads the entire file and builds lightweight lookup dictionaries in RAM:

| Dictionary | Source (FourCC / prop ID) | Contents |
|---|---|---|
| `uid_ttea` | Pcti · 1348695145 | person uid → current club Ttea (from new_value) |
| `uid_prev_ttea` | Pcti · 1348695145 | person uid → previous club Ttea (from odvl — departure tracking) |
| `uid_nnat` | Pnti · 1349416041 | person uid → nationality (Nnat) |
| `ttea_nation` | Plhs · 1349281907 | club Ttea → nation (via competition) |
| `ttea_best_year` | Plhs · 1349281907 | club Ttea → best year (recency tie-break) |
| `club_uid_nation` | Cdvi · 1130657385 | club db_unique_id → nation |
| `club_clhs_entries` | Clhs · 1131178099 | club uid → {year: comp_id} (for synthetic Cdvi) |

**CRITICAL — null-Pcti pattern**: some Pcti records have `<null id="new_value"/>` (contract deleted).
These have only ONE Ttea in the blob (the `odvl` Ttea).
`NEWVAL_TTEA_RE` and `ODVL_TTEA_RE` parse them separately to avoid the odvl Ttea
being mistakenly assigned as the new club. Never use `TTEA_RE.findall(blob)` length
to distinguish these cases.

### Architecture — Step 2 (filter and write)
Re-reads the file and copies to the output XML only the records whose `db_unique_id`
belongs to a person, club, competition, or nation from the TARGET.
Header (lines 1–16) and footer (`\t</list>\n</record>`) are copied verbatim.
Synthetic Cdvi/Cldi records (Fix 2) are appended before the footer.

### Inclusion criteria (implemented, in priority order)
1. **Person with contract at a TARGET club** → Pcti → new_value.Ttea → Plhs competition → COMP_NATION
2. **Club in a TARGET division** → Cdvi → competition → COMP_NATION
3. **Fallback: nationality** → Pnti → Nnat → NNAT_NATION
4. **Award/history record** with a `Pers` field pointing to a TARGET person
5. **Departure records (Fix 3)** — persons whose *previous* club (Pcti odvl.Ttea) was a TARGET club
   but whose new club is non-TARGET (e.g. a foreign coach leaving Roma for a foreign club).
   Without these, the FM base state (e.g. Fonseca at Roma) is never overridden.
   Source: `uid_prev_ttea` → departure_uids frozenset.
6. **Clubs without Cdvi in patch (Fix 1)** — clubs known via Ttea (ttea_nation) but with no
   Cdvi record in the MASTER (already in the correct division in the FM 2021 base).
   Their uid is synthesised as `int(ttea) * MULT` and added to `club_uid_nation`.
7. **Synthetic Cdvi/Cldi (Fix 2)** — for Fix-1 clubs that have Clhs data: synthetic
   `Cdvi` and `Cldi` records are written at end of Pass 2 using the most recent
   year ≤ 2002 competition ID from `club_clhs_entries`.
   Without this, FM 2024 places these clubs in their current-era division.
8. **Competition entity records (Fix 4)** — all rtype=25 records for TARGET competition UIDs.
   `target_comp_uids = {str(c * MULT) for c in COMP_NATION if nation==TARGET}`.
   **IMPORTANT**: ALL competition entity records in the MASTER use `rtype=25`, NOT `rtype=3`.
   Includes chst, crep, CFGc, CLRc, and all other competition sub-records.
9. **Nation financial records (Fix 5)** — rtype=9 records for TARGET nation UIDs.
   `target_nation_uids = {str(n * MULT) for n in NNAT_NATION if nation==TARGET}`.
   Captures NTRv (transfer values) and NWGv (wage values) per nation.
   **IMPORTANT**: rtype=9 only — nation shares the same integer with some competition IDs
   (e.g. Italy nation 34 would collide with Serie C1/A comp 34 if not filtered by rtype).

### ID collision — competitions vs nations (confirmed)
Competition IDs and nation IDs share the same integer namespace.
Example: `34 * MULT` = both Serie C1/A (comp) and Morocco (nation).
This is safe because competitions are captured via `rtype=25` and nations via `rtype=9`.
Never add a shared ID to `target_comp_uids` and `target_nation_uids` simultaneously.

---

## Step 2 — convert_to_fm24.py (FM 2024)

Converts the XML generated by `split_fm_xml.py` into the format accepted by the FM 2024 editor.

```
# To convert a country:
# python convert_to_fm24.py italy
# python convert_to_fm24.py spain
# Input:  output/fm21/<country>.xml
# Output: output/fm24/<country>_fm24_final.xml
```

### Transformations applied
| What changes | Detail |
|---|---|
| Header | FM 2021 format → FM 2024 (versions, fields, order) |
| `version` per record | 2959/2961 → 3567 |
| `is_client_field` | Removed; replaced by `<boolean id="odvl" value="false"/>` |
| Problematic IDs | 237 player_ids across all XMLs remapped (see below) |

### ID remapping — formula and context
The retro 2001/02 database was built in FM 2021. Some players did not exist in the FM 2021
base database and were created with new IDs in the range `2,000,040,000–2,000,070,000`.
These IDs do not exist in the FM 2024 base database, which silently ignores them.

**Scope:** 237 unique IDs across all 18 fm21 XMLs fall in this range.
Italy alone has 30. Other countries have not been individually verified yet — handled on demand.

**ID encoding in the XML:**
`db_unique_id = player_id * (2^32 + 1)`

**Default formula:**
`player_id_fm24 = player_id_retro - 60238`

Derived from the Totti case (retro 2000066931 → FM 2024 2000006693).
Works for most players whose mod author deliberately matched FM 2021 retro IDs to FM 2024 entities.

**Exceptions (ID_OVERRIDE in convert_to_fm24.py) — Italy, verified 2026-05-23:**

`None` = keep retro ID unchanged (FM24 entity exists at same ID, or player absent — no harm).

| Retro ID | Behaviour | FM24 ID | Player | Notes |
|---|---|---|---|---|
| 2000045875 | keep retro | 2000045875 | Giuseppe Finocchiaro | FM24 has non-player at same ID |
| 2000066464 | override | 2002041017 | Pierre Womé | retired person in FM24 |
| 2000066648 | keep retro | — | Aldair | does not exist in FM24 |
| 2000066836 | override | 48037335 | Lilian Thuram | non-player in FM24 under different ID |
| 2000066933 | override | 2002041530 | Christian Vieri | retired person in FM24 |
| 2000067028 | override | 2002041627 | Predrag Mijatovic | retired person in FM24 |
| 2000067051 | override | 830573 | Mirko Vucinic | non-player in FM24 under different ID |
| 2000067560 | override | 2002041538 | Roberto Baggio | retired person in FM24 |
| 2000067572 | keep retro | — | Jason Mayélé | formula collides with Boersma, Danny in FM24 |
| 2000067574 | keep retro | — | Vittorio Mero | formula collides with de Vries, Wim in FM24 |

**Italy players where formula works correctly (formula ID verified in FM24 editor):**
```
2000066471 → 2000006233   (George Weah)
2000066583 → 2000006345   (Fernando Redondo)
2000066588 → 2000006350   (Gabriel Batistuta)
2000066637 → 2000006399   (Marcos)
2000066658 → 2000006420   (Emerson)
2000066675 → 2000006437   (Antônio Zago)
2000066725 → 2000006487   (Zvonimir Boban)
2000066732 → 2000006494   (Pavel Srnicek)
2000066740 → 2000006502   (Karel Poborsky)
2000066926 → 2000006688   (Dino Zoff — non-player, correct entity)
2000066927 → 2000006689   (Demetrio Albertini)
2000066931 → 2000006693   (Francesco Totti)
2000066932 → 2000006694   (Roberto Bettega — non-player, correct entity)
2000066937 → 2000006699   (Moreno Torricelli)
2000067032 → 2000006794   (Vladimir Jugovic)
2000067039 → 2000006801   (Vedin Music)
2000067127 → 2000006889   (Nils Liedholm — non-player, correct entity)
2000067135 → 2000006897   (Hakan Şükür)
2000067300 → 2000007062   (Fernando Couto)
2000067463 → 2000007225   (Omar Sívori)
```

**Note:** formula may produce duplicate entities in FM 2024 (e.g. a retro player alongside a
retired/non-player version). This is expected and can be resolved manually in the editor.

**When verifying a new country:** search the fm21 XML for all `db_unique_id` values where
`id mod (2^32+1) == 0` and `2,000,040,000 ≤ id/(2^32+1) ≤ 2,000,070,000`, then check each
formula result in the FM24 editor. Add confirmed exceptions to `ID_OVERRIDE` in convert_to_fm24.py.

---

## Critical ID rule
**NEVER guess IDs for competitions, nations, clubs, or any FM entity.**
Always ask the user to confirm in the FM 2021 editor before adding to the script.

---

## Minimum ID standard per nation (required before generating any new XML)

Before generating the XML for a new nation — or regenerating an existing one —
the user **must confirm in the FM 2021 editor** the IDs listed below.
Claude Code must explicitly request these IDs if they are not yet in `COMP_NATION` / `NNAT_NATION`.

### REQUIRED
| Item | Reason |
|---|---|
| Nation ID (`NNAT_NATION`) | Nationality fallback for players without a mapped club |
| Division 1 (top league) | Captures all elite clubs |
| Division 2 | Captures professional second-tier clubs |
| Division 3 | Captures relevant semi-professional clubs; without this, third-tier clubs are missed |
| Main national cup | Captures players in cup history records |

### RECOMMENDED
| Item | Reason |
|---|---|
| Division 4 | Covers the full professional pyramid; common in European retro patches |
| All variants/groups of level 3 | e.g. Serie C1/A, C1/B, C1/C — the database uses different IDs per group |
| All variants/groups of level 4 | e.g. Segunda B1–B5, German regional divisions |
| Super cup / secondary cup | Captures extra competition history records |

### UNNECESSARY (unless there is a specific reason)
- Division 5 and below — semi-professional/amateur, rarely present in the retro patch.
  Including them increases the risk of capturing clubs with colliding IDs without practical benefit.

### Pending IDs by nation
| Country | What still needs confirmation in the editor |
|---|---|
| Greece | 3rd Division - North (level 3) — confirm whether it exists in the database |
| Other countries | All IDs — no new nation should be generated without confirming the minimum required |

---

## IDs confirmed in the FM 2021 editor

### Nations (Nnat field / NNAT_NATION)
| Nation | ID |
|---|---|
| Italy | 776 |
| Spain | 796 |
| England | 765 |
| Scotland | 793 |
| Portugal | 788 |
| Netherlands | 784 |
| Turkey | 799 |
| Denmark | 764 |
| Greece | 772 |
| Brazil | 1651 |
| Argentina | 1649 |
| Chile | 1652 |
| Colombia | 1653 |
| Uruguay | 1657 |
| Paraguay | 1655 |
| Peru | 156 |
| Bolivia | 1650 |
| Ecuador | 1654 |
| Venezuela | 1658 |
| Mexico | 379 |
| USA | 390 |
| Costa Rica | 366 |
| Honduras | 376 |
| Panama | 382 |
| Jamaica | 377 |
| Haiti | 375 |
| Trinidad and Tobago | 389 |
| Canada | 364 |
| Belgium | 757 | Switzerland | 798 | Austria | 755 |
| Russia | 791 | Poland | 787 | Sweden | 797 |
| Czech Republic | 763 | Slovakia | 794 | Hungary | 773 |
| Romania | 790 | Bulgaria | 760 | Croatia | 761 |
| Serbia | 802 | Slovenia | 795 | Bosnia | 759 |
| Ukraine | 800 | Belarus | 758 | Moldova | 783 |
| Ireland | 789 | Northern Ireland | 785 | Wales | 801 |
| Norway | 786 | Finland | 768 | Iceland | 774 |
| Faroe Islands | 767 | Albania | 752 | Kosovo | 217945 |
| Montenegro | 62002127 | North Macedonia | 781 | Cyprus | 762 |
| Malta | 782 | Gibraltar | 214394 | Crimea | 215446 |
| Georgia | 770 | Armenia | 754 | Azerbaijan | 756 |
| Kazakhstan | 119 | Estonia | 766 | Latvia | 777 |
| Lithuania | 779 | Israel | 775 | Andorra | 753 |
| Liechtenstein | 778 | Luxembourg | 780 | San Marino | 792 |
| Others | **not confirmed** — ask the user |

> **Recorded corrections:**
> - ID 1655 was labelled "uruguay" — confirmed as Paraguay. Uruguay = 1657.
> - ID 785 was labelled "norway" — confirmed as Northern Ireland. Norway = 786.
> - ID 789 was labelled "scotland" — confirmed as Ireland. Scotland = 793.
> - ID 781 was labelled "ireland" — confirmed as North Macedonia. Ireland = 789.

### Competitions — Italy
| Competition | ID |
|---|---|
| Serie A | 32 |
| Serie B | 33 |
| Serie C1/A | 34 |
| Serie C1/B | 35 |
| Serie C2/A | 36 |
| Serie C2/B | 37 |
| Serie C2/C | 38 |
| Serie C1/C | 39 |
| Serie C1 | 145429 |
| Serie C2 | 145430 |
| Coppa Italia | 1301412 |
| Supercoppa Italiana | 1301414 |
| Serie C/A (v1) | 23127172 |
| Serie C/A (v2) | 43121712 |
| Serie C/B (v1) | 43121713 |
| Serie C/B (v2) | 43127173 |
| Serie C | 43127171 |
| Serie C/C | 43127174 |

### Competitions — France
| Competition | ID | Level |
|---|---|---|
| Ligue 1 | 16 | 1 |
| Ligue 2 | 17 | 2 |
| Championnat National (N1) | 18 | 3 |
| National 2 - A | 19 | 4 |
| National 2 (generic) | 145438 | 4 |
| National 2 - B | 914522 | 4 |
| National 2 - C | 914523 | 4 |
| National 2 - D | 914524 | 4 |
| Trophée des Champions | 109288 | cup |
| Coupe de France | 1301407 | cup |
| Coupe de la Ligue BKT | 1301408 | cup |

### Competitions — Scotland
| Competition | ID | Level |
|---|---|---|
| Scottish Premiership | 45 | 1 |
| Scottish Championship | 46 | 2 |
| Scottish League One | 47 | 3 |
| Scottish League Two | 48 | 4 |
| SPFL Trust Trophy | 120798 | cup |
| Scottish Cup | 1301430 | cup |
| Betfred Cup | 1301431 | cup |

*Note: Scotland has no super cup in this database (confirmed in the editor).*

### Competitions — Germany
| Competition | ID |
|---|---|
| Bundesliga | 22 |
| 2. Bundesliga | 23 |
| Regionalliga North | 26 |
| Regionalliga Southeast | 27 |
| Regionalliga (generic) | 146957 |
| 3. Liga | 35010926 |
| DFB-Pokal | 1301410 |
| Regionalliga Northeast | 91107110 |
| Regionalliga Southwest | 91107111 |
| DFL-Supercup | 92030194 |

### Competitions — England
| Competition | ID |
|---|---|
| Premier League | 11 |
| Sky Bet Championship | 12 |
| Sky Bet League One | 13 |
| Sky Bet League Two | 14 |
| Vanarama National League | 109201 |
| FA Trophy | 109202 |
| FA Cup | 1301426 |
| Carabao Cup | 1301427 |
| FA Community Shield | 1301428 |
| Papa John's Trophy | 1301429 |

### Competitions — Argentina
| Competition | ID | Type |
|---|---|---|
| Primera División (generic) | 102421 | level 1 |
| Primera División - Apertura | 74 | level 1 |
| Primera División - Clausura | 75 | level 1 |
| Segunda División | 102422 | level 2 |
| Liga Metropolitana B | 108508 | level 3 |
| Third Division (generic) | 108573 | level 3 |
| Liga Interior A | 108509 | level 3/4 regional |
| Liga Interior B | 14037261 | level 4 regional |
| Copa Argentina | 14043892 | cup |
| Copa de la Superliga | 223470 | cup |
| Pre-Libertadores Argentina | 216347 | cup/qualifier |
| Supercopa Argentina | 14063636 | cup |

### Competitions — Brazil
| Competition | ID | Type |
|---|---|---|
| Brasileirão Série A | 102423 | level 1 |
| Brasileirão Série B | 107191 | level 2 |
| Brasileirão Série C | 107192 | level 3 |
| Brasileirão Série D | 19127222 | level 4 |
| Copa do Brasil | 102427 | cup |
| Supercopa do Brasil | 19106793 | cup |
| Campeonato Paulista | 102426 | state |
| Campeonato Carioca | 102424 | state |
| Campeonato Mineiro | 309682 | state |
| Campeonato Gaúcho | 302205 | state |
| Campeonato Baiano | 309678 | state |
| Campeonato Catarinense | 309688 | state |
| Copa do Nordeste | 309697 | regional |

*Note: remaining state championships (PE, CE, PR, GO, etc.) not confirmed — add on demand.*

### Competitions — Greece
| Competition | ID | Level |
|---|---|---|
| Super League Greece | 129650 | 1 |
| Football League (2nd div) | 129651 | 2 |
| Gamma Ethniki (generic) | 690094 | 3 |
| Gamma Ethniki - South | 694365 | 3 |
| Gamma Ethniki - North | **PENDING** | 3 — confirm whether it exists in the database |
| Greek Cup | 129649 | cup |

*Super cup and level 4 not confirmed — recommended, not required.*

### Competitions — Denmark
| Competition | ID | Level |
|---|---|---|
| SAS Ligaen | 6 | 1 |
| 1. Division | 7 | 2 |
| 2. Division | 8 | 3 |
| 3rd Division | 2000016262 | 4 |
| DBU Pokalen | 1301406 | cup |
| Danish Super Cup | 920953 | cup — defunct in database (included for historical records) |

### Competitions — Turkey
| Competition | ID | Level |
|---|---|---|
| Süper Lig | 130286 | 1 |
| PTT 1. League | 463479 | 2 |
| Spor Toto 2. League (generic) | 463481 | 3 |
| Spor Toto 2. League Group 1 | 463485 | 3 |
| Spor Toto 2. League Group 2 | 463486 | 3 |
| Ziraat Turkish Cup | 130284 | cup |
| TFF Super Cup | 155007 | cup |

*TFF 3. Lig (level 4) not confirmed — recommended, not required.*

### Competitions — Netherlands
| Competition | ID | Level |
|---|---|---|
| Eredivisie | 29 | 1 |
| Keuken Kampioen Divisie | 30 | 2 |
| Tweede Divisie | 37059991 | 3 |
| Derde Divisie - Saturday | 37059992 | 4 |
| Derde Divisie - Sunday | 37059993 | 4 |
| KNVB Cup | 1301411 | cup |
| Johan Cruyff Shield | 120861 | cup |

### Competitions — Portugal
| Competition | ID | Level |
|---|---|---|
| Primeira Liga | 60 | 1 |
| Segunda Liga | 61 | 2 |
| 3rd Division | 2000015975 | 3 |
| Taça de Portugal | 1301421 | cup |
| Taça da Liga | 55006606 | cup |
| Supertaça Cândido de Oliveira | 11505 | cup |

### Competitions — Spain
| Competition | ID |
|---|---|
| Primera División | 67 |
| Segunda División | 68 |
| Segunda B1 | 69 |
| Segunda B2 | 70 |
| Segunda B3 | 71 |
| Segunda B4 | 72 |
| Segunda B (generic) | 121091 |
| Copa del Rey | 1301422 |
| Supercopa de España | 1301423 |
| Segunda B5 | 20000032789 |
| Second Division Pro | 20000048840 |
| Second Division Pro A | 20000048844 |
| Second Division Pro B | 20000048846 |

---

## Generation status
| Country | FM 2021 | FM 2024 | Records | Notes |
|---|---|---|---|---|
| Italy | ✅ tested (v3) | ⏳ needs re-run | 119,264 | v3 adds nation+comp+departure records; staff issue open |
| Spain | ✅ generated | ⏳ pending | 91,597 | generated before Fixes 1–5; needs regeneration |
| England | ✅ generated | ⏳ pending | 144,808 | same — needs regeneration |
| Germany | ✅ generated | ⏳ pending | 38,862 | same — needs regeneration |
| Scotland | ✅ generated | ⏳ pending | 34,592 | League Two mapped since last gen; needs regeneration |
| France | ✅ generated | ⏳ pending | 45,309 | National 2 fully mapped since last gen; needs regeneration |
| Other countries | ⏳ pending | ⏳ pending | — | — |

### Italy v3 — confirmed in FM 2021 editor (2026-05-17)
- ✅ Nation records working: Italy transfer values and wage values (NTRv, NWGv) now appear
- ✅ Competition entity records captured (18 Italian comp UIDs, all rtype=25)
- ⚠️ Competition "record" fields (best scorer, etc.) may show current-era players (e.g. Higuaín
  in Serie A goals record). Root cause: the MASTER.xml doesn't always clear these reference fields
  when updating competition data for the retro era. **This is a mod-level issue, not a script bug.**
  The fields themselves appear empty (value=0, club=blank) but the player reference is retained
  from the FM 2021 base. Can be cleared manually in the editor if needed.
- ⚠️ **Staff issue open**: coaching staff (managers, coaches) not loading correctly.
  Fonseca still shows as Roma manager (should be Capello in 2001/02).
  Juventus has no manager (should be Lippi). See section below.

---

## Coaching staff issue — CONFIRMED MOD LIMITATION (2026-05-17)

### Context — how MASTER.xml was generated
MASTER.xml is not hand-written by the mod author. The user loaded the mod's `.fmf` file in
the FM 2021 editor and exported the differential patch as XML. Therefore MASTER.xml faithfully
reflects what is in the `.fmf`: if a Pcti contract record is absent from MASTER.xml, it was
never included in the mod's `.fmf` file.

### Root cause
Coaching staff contracts (managers, coaches) are **not in the mod's `.fmf` / MASTER.xml**.
The 2001/02 coach entities are visible in the FM 2021 editor (created inside the `.fmf`)
but their Pcti contract records were never added to the mod.

### Confirmed via diagnostics — exhaustive investigation
**Person-side (rtype=1):**
- `diag_staff_properties.py`: no coaching-specific FourCC property found. Staff contracts
  use the same `Pcti` (1348695145) as players. Our script captures these correctly.
  Other properties found: `Plhs` (history), `Pacl` (achievement records), `PLcl` (loans) — none are current-contract fields.
- `diag_coaches.py`: targeted search for Capello (2000068860) and Lippi (2000068809) in
  MASTER.xml by db_unique_id → **0 records for both**. IDs in the 2,000,068,xxx range.
- Supplemental searches: raw entity IDs "2000068860"/"2000068809" as plain integers — 0 hits.
  "ID Aleatório" value 25837371 and its db_unique_id encoding — 0 hits.

**Club-side (rtype=3):**
- Full enumeration of all ~70 distinct rtype=3 property types in MASTER.xml confirms that
  **no club-side property references a current manager as a person entity**.
  The closest are `CMOn` (stores old manager's name as a plain **string**) and similar
  `CMO*` / `CYP*` / `COS*` properties — all null or string values, not entity IDs.
- FM stores manager contracts exclusively via `Pcti` on the **person** side. There is no
  club-side equivalent. This avenue has been exhaustively ruled out.

### FM editor fields — clarified
- **"ID Único"** (e.g. 2000068860): the entity_id used in `db_unique_id = entity_id * (2^32+1)`.
- **"ID Aleatório"** (e.g. 25837371): FM's internal `random_uid`, assigned in the FM 2021 base
  database. It does **not** appear in MASTER.xml in any form and has no use for our script.
- **"Tipo Pessoa: Não Jogador"**: non-player staff use the identical Pcti mechanism as players.
  The person type does not change the XML structure or property IDs involved.

### Pacl (1348559724) — clarified
`Pacl` = "Person Achievement Club" — records of specific achievements (e.g. cup finals won)
at a specific club on a specific date. NOT a current-contract property. Has its own UID and
contains `olvl.team.Ttea`, `competition`, `date`, `ajob` (job type: 1=player, 20=manager).
Multiple records per person (one per achievement).

### Consequences in FM 2021 editor (Italy XML)
- Clubs where the FM 2021 base manager is Italian (e.g. Pirlo was Juventus manager →
  converted to player in retro → departure record captured → **club ends up with NO manager**).
- Clubs where the FM 2021 base manager is foreign (e.g. Fonseca at Roma) and has no
  departure record in MASTER → **old manager persists from FM 2021 base**.

### Action required
- Nothing to fix in `split_fm_xml.py` — the script is working correctly.
- Pcti contract records for 2001/02 coaches must be added to the mod's `.fmf` by the mod author.
- Workaround: assign managers manually in the FM editor after importing the XML.

### Known 2001/02 Italian manager entity IDs (for reference when mod is updated)
| Manager | Entity ID | Club | Notes |
|---|---|---|---|
| Fabio Capello | 2000068860 | AS Roma | ID in range → will be remapped in FM 2024 |
| Marcello Lippi | 2000068809 | Juventus | ID in range → will be remapped in FM 2024 |

---

## Competition record display issue — cosmetic (2026-05-17)

### Symptom
When italy.xml is loaded in FM 2021 editor, some competition record fields (e.g. "Record
Goals in Championship" for Serie A) show Higuaín despite the full MASTER.xml showing the
field empty.

### Root cause
The FM 2021 base database has Higuaín as the Serie A all-time record scorer. The MASTER.xml
retro patch includes a clearing record (rtype=25, uid=Serie A * MULT) that nulls this field.
This clearing record IS included in italy.xml.

The residual display of Higuaín appears because:
- The specific sub-field controlling the "first player" UI slot uses a slightly different
  mechanism than expected (possibly aggregated by the FM engine from multiple sub-records).
- `COMP_RE` check added to `is_target()` for rtype=25 was verified to add 0 new records
  for Italy — all Italian rtype=25 records already had the competition's own UID.

### Status
Cosmetic only. Not blocking gameplay. The retro database state is correct; the editor
display is an artifact of how FM aggregates competition history fields.
Fixing this would require identifying the specific sub-record property ID that controls
the "first player" display slot — low priority.

---

## Technical references
- **FREE_AGENT_TTEA**: `1171` — virtual free-agents team; ignore in club lookups
- **Barcelona**: Ttea=1708 → competition=67 (confirmed reference)
- **Real Madrid**: Ttea=1736 → competition=67
- **Arsenal**: db_unique_id=2585570312794

### Source file structure
```
Line 1:        <record>
Lines 2–15:    patch metadata (version, date, etc.)
Line 16:       \t<list id="db_changes">
Lines 17–13,102,214:  records (each in \t\t<record>)
Line 13,102,215: \t</list>
Line 13,102,216: </record>
```

### Relevant database_table_types
| Type | Meaning |
|---|---|
| 0 | Award history |
| 1 | Persons (players, managers, staff) |
| 3 | Clubs and competitions |
| 9 | Financial |
| 21 | Boolean flags |
| 25 | Competition history records |
| 55 | Cross-references |

---

## Next steps
- [ ] **Staff issue**: confirmed mod limitation — nothing to fix in script. Workaround: manual assignment in editor.
- [ ] **Italy v4**: current italy.xml (119,264 records) is the final version pending mod updates. Re-run `convert_to_fm24.py italy`.
- [ ] **Regenerate all countries** with Fixes 1–5 (spain, england, germany, scotland, france)
- [ ] **Scotland**: also has League Two newly mapped — confirm regeneration includes it
- [ ] **France**: also has National 2 fully mapped — confirm regeneration includes it
- [ ] Convert all regenerated countries to FM 2024
- [ ] Generate FM 2021 XMLs for remaining countries (follow minimum standard above before each one)
- [ ] Verify whether the ID remapping (offset 60238) applies equally to other countries
