# Coaching Staff Investigation — Confirmed Mod Limitation (2026-05-17)

## Context — how MASTER.xml was generated
MASTER.xml is not hand-written by the mod author. The user loaded the mod's `.fmf` file in
the FM 2021 editor and exported the differential patch as XML. Therefore MASTER.xml faithfully
reflects what is in the `.fmf`: if a Pcti contract record is absent from MASTER.xml, it was
never included in the mod's `.fmf` file.

## Root cause
Coaching staff contracts (managers, coaches) are **not in the mod's `.fmf` / MASTER.xml**.
The 2001/02 coach entities are visible in the FM 2021 editor (created inside the `.fmf`)
but their Pcti contract records were never added to the mod.

## Confirmed via diagnostics — exhaustive investigation

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

## FM editor fields — clarified
- **"ID Único"** (e.g. 2000068860): the entity_id used in `db_unique_id = entity_id * (2^32+1)`.
- **"ID Aleatório"** (e.g. 25837371): FM's internal `random_uid`, assigned in the FM 2021 base
  database. It does **not** appear in MASTER.xml in any form and has no use for our script.
- **"Tipo Pessoa: Não Jogador"**: non-player staff use the identical Pcti mechanism as players.
  The person type does not change the XML structure or property IDs involved.

## Pacl (1348559724) — clarified
`Pacl` = "Person Achievement Club" — records of specific achievements (e.g. cup finals won)
at a specific club on a specific date. NOT a current-contract property. Has its own UID and
contains `olvl.team.Ttea`, `competition`, `date`, `ajob` (job type: 1=player, 20=manager).
Multiple records per person (one per achievement).

## Consequences in FM 2021 editor (Italy XML)
- Clubs where the FM 2021 base manager is Italian (e.g. Pirlo was Juventus manager →
  converted to player in retro → departure record captured → **club ends up with NO manager**).
- Clubs where the FM 2021 base manager is foreign (e.g. Fonseca at Roma) and has no
  departure record in MASTER → **old manager persists from FM 2021 base**.

## Action required
- Nothing to fix in `split_fm_xml.py` — the script is working correctly.
- Pcti contract records for 2001/02 coaches must be added to the mod's `.fmf` by the mod author.
- Workaround: assign managers manually in the FM editor after importing the XML.
