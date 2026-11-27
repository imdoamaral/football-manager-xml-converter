"""
build_checklist.py
Writes output/fm24/<country>_checklist.md: what the user must check or do BY HAND in the FM24
editor after importing <country>_fm24_final.xml (user decision 2026-11-26: deletes of FM24-only
content are manual; creation/alteration is automated).

Inputs: output/fm21/<country>.xml, output/fm24/<country>_fm24_final.xml,
        reference/club_history/<country>.json (optional, from build_club_history.py),
        anexos-claude/fm21_*.rtf (optional FM21 export, for names).

Usage:
    python build_checklist.py italy
"""

import glob
import json
import os
import re
import struct
import sys
from collections import Counter, defaultdict

TARGET   = sys.argv[1] if len(sys.argv) > 1 else "italy"
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FM21     = os.path.join(BASE_DIR, "output", "fm21", f"{TARGET}.xml")
FM24     = os.path.join(BASE_DIR, "output", "fm24", f"{TARGET}_fm24_final.xml")
HIST     = os.path.join(BASE_DIR, "reference", "club_history", f"{TARGET}.json")
OUT      = os.path.join(BASE_DIR, "output", "fm24", f"{TARGET}_checklist.md")
MULT     = 2**32 + 1
LOW32    = 0xFFFFFFFF

CDVI, CHST, PLHS, PCTI = "1130657385", "1667789684", "1349281907", "1348695145"
CLGL, CICL = "1131177836", "1128883052"
NAME_PROPS = ("1348890209", "1349742177", "1348693601")
CLUB_NAME_PROPS = ("1131307373", "1131638381")   # Cnam, Csnm
FREE_AGENT = 1171

# Competition names known per country (CLAUDE.md tables + ids learned in build_club_history.py).
# "old" = 2001-era format competitions, probably inactive in FM24.
COMP_NAMES = {
    "italy": {
        32: "Serie A", 33: "Serie B", 43127172: "Serie C – Grupo A", 43127173: "Serie C – Grupo B",
        43127174: "Serie C – Grupo C", 1400408: "Serie D – Girone I", 34: "Serie C1/A (formato antigo)",
        35: "Serie C1/B (formato antigo)", 36: "Serie C2/A (formato antigo)", 37: "Serie C2/B (formato antigo)",
        38: "Serie C2/C (formato antigo)", 39: "Serie C1/C (formato antigo)", 1301412: "Coppa Italia",
        1301414: "Supercoppa Italiana",
    },
}
# Ids seen in club divisions that belong to other countries (foreign clubs present in the file).
FOREIGN_HINT = {16: "Ligue 1", 67: "LaLiga", 68: "Segunda División", 72: "Segunda B4", 109201: "National League",
                129650: "Super League Greece"}


def fcc(p):
    return struct.pack(">I", int(p)).decode("latin1")


def records(path):
    buf = None
    for line in open(path, encoding="utf-8"):
        s = line.rstrip("\n")
        if buf is None:
            if s == "\t\t<record>":
                buf = [s]
            continue
        buf.append(s)
        if s == "\t\t</record>":
            yield "\n".join(buf)
            buf = None


def load_export():
    names = {}
    for path in sorted(glob.glob(os.path.join(BASE_DIR, "anexos-claude", "fm21_*.rtf"))):
        hdr = None
        for line in open(path, encoding="utf-8"):
            if not line.startswith("|") or set(line.strip()) <= set("|- "):
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            if hdr is None:
                hdr = cells
                continue
            r = dict(zip(hdr, cells))
            if r.get("IDU", "").isdigit():
                names.setdefault(int(r["IDU"]), re.sub(r"\s+-\s+\S+$", "", r.get("Nome", "")).strip())
    return names


def main():
    names = load_export()
    comp_name = COMP_NAMES.get(TARGET, {})
    club_name = {}
    hist = json.load(open(HIST, encoding="utf-8")) if os.path.exists(HIST) else {"clubs": {}, "competitions": {}}
    for eid, c in hist["clubs"].items():
        club_name[int(eid)] = c["link"]

    div = {}                                  # club eid → 2001/02 competition
    chst_years = defaultdict(set)             # comp eid → years the mod deletes
    legends = []                              # (club, kind, name, ratio)
    plhs_del = defaultdict(set)               # person uid → years the mod deletes
    contract = {}                             # person uid → club eid
    person_name = {}
    for b in records(FM21):
        prop = re.search(r'property" value="(\d+)"', b).group(1)
        uid = int(re.search(r'db_unique_id" value="(\d+)"', b).group(1))
        if prop == CDVI:
            m = re.search(r'<record id="new_value">\s*<integer id="competition" value="(\d+)"', b)
            if m:
                div[uid // MULT] = int(m.group(1))
        elif prop == CHST and 'lsop" value="2"' in b:
            chst_years[uid // MULT].add(int(re.search(r'id="year" value="(\d+)"', b).group(1)))
        elif prop in (CLGL, CICL) and 'lsop" value="2"' in b:
            n = re.search(r'stage_name" value="([^"]*)"', b)
            r = re.search(r'ratio" value="(\d+)"', b)
            legends.append((uid // MULT, "lenda" if prop == CLGL else "ícone", n.group(1) if n else "?",
                            r.group(1) if r else "?"))
        elif prop == PLHS and 'lsop" value="2"' in b and (uid >> 32) == (uid & LOW32):
            y = re.search(r'id="year" value="(\d+)"', b)
            if y and int(y.group(1)) > 2000:
                plhs_del[uid].add(int(y.group(1)))
        elif prop == PCTI:
            m = re.search(r'<record id="new_value">\s*<integer id="Ttea" value="(\d+)"', b)
            if m:
                contract[uid] = int(m.group(1))
        elif prop in NAME_PROPS:
            v = re.search(r'string id="new_value" value="([^"]+)"', b)
            if v:
                person_name.setdefault(uid, v.group(1))
        elif prop in CLUB_NAME_PROPS and 'table_type" value="3"' in b:
            v = re.search(r'string id="new_value" value="([^"]+)"', b) or \
                re.search(r'string id="odvl" value="([^"]+)"', b)
            if v and uid % MULT == 0:
                club_name.setdefault(uid // MULT, v.group(1))

    # what the converter did (from the FM24 file)
    addr = re.findall(r'<unsigned id="dcty" value="(\d)"/>\n\t+<large id="db_unique_id" value="(\d+)"/>',
                      open(FM24, encoding="utf-8").read())
    promoted = sum(1 for _, u in addr if int(u) % MULT == 0)
    created = len(addr) - promoted

    def pname(uid):
        return person_name.get(uid) or names.get(uid & LOW32) or f"id {uid & LOW32}"

    def cname(eid):
        return club_name.get(eid) or f"clube {eid}"

    L = []
    L.append(f"# Conferência manual — {TARGET.capitalize()} (FM24)\n")
    L.append(f"Arquivo: `output/fm24/{TARGET}_fm24_final.xml`. Gerado por `build_checklist.py`.\n")
    L.append("Feito automaticamente: pessoas criadas pelo mod e promovidas da base do FM21 "
             f"({created} + {promoted} registros de criação), nomes/nacionalidades da exportação do FM21, "
             "contratos, divisões dos clubes, histórico de jogadores, datas +3 anos.\n")

    # ── 1. essential ─────────────────────────────────────────────────────────
    L.append("## 1. Essencial — competições onde o patch coloca clubes em 2001/02\n")
    L.append("Confira no editor se cada competição existe e está **ativa** no FM24. "
             "Os números contam só clubes que **mudam** de divisão no patch.\n")
    L.append("| ID | Competição | Clubes | Atenção |\n|---|---|---|---|")
    for comp, n in Counter(div.values()).most_common():
        if comp in FOREIGN_HINT:
            continue
        nm = comp_name.get(comp, "desconhecida")
        warn = "formato antigo — provavelmente inativa" if "antigo" in nm else \
               ("ID desconhecido — conferir" if nm == "desconhecida" else "")
        L.append(f"| {comp} | {nm} | {n} | {warn} |")
    foreign = Counter(c for c in div.values() if c in FOREIGN_HINT)
    if foreign:
        L.append("\nClubes estrangeiros presentes no arquivo (ignorar aqui): " +
                 ", ".join(f"{FOREIGN_HINT[c]} ({n})" for c, n in foreign.items()) + ".\n")

    # ── 2. cosmetic ──────────────────────────────────────────────────────────
    L.append("\n## 2. Cosmético — exclusões à mão\n")
    L.append("### 2.1 Histórico de clubes: temporadas 2021–2023 (só existem no FM24)\n")
    if hist["clubs"]:
        L.append("| Clube (id) | Ano | Competição | Posição | Pontos |\n|---|---|---|---|---|")
        for eid, c in sorted(hist["clubs"].items(), key=lambda x: x[1]["link"]):
            for r in c["rows"]:
                L.append(f"| {c['link']} ({eid}) | {r['year']} | {comp_name.get(r['comp'], r['comp'])} | "
                         f"{r['posi']} | {r['poin']} |")
        L.append("\nAlém disso podem sobrar linhas de 2002–2020 cujo conteúdo mudou no FM24 "
                 "(ex.: Catania 2021).\n")
    else:
        L.append("_Rode `python build_club_history.py " + TARGET + "` para gerar a lista._\n")

    L.append("### 2.2 Histórico de competições\n")
    L.append("O mod exclui as temporadas abaixo; no FM24 podem sobrar **2021–2023** e anos cujo conteúdo o FM24 "
             "corrigiu (Itália: Serie A 2005, 2012, 2016; Serie B 2020 — vencedor do playoff).\n")
    L.append("| ID | Competição | Anos excluídos pelo mod |\n|---|---|---|")
    for comp, ys in sorted(chst_years.items()):
        if comp in FOREIGN_HINT:
            continue
        L.append(f"| {comp} | {comp_name.get(comp, 'desconhecida')} | {min(ys)}–{max(ys)} |")
    L.append("\nCompetições do país que o mod **não** limpa (ex.: Serie C – Grupo A) mantêm todo o histórico "
             "moderno do FM24.\n")

    L.append("### 2.3 Ícones e lendas\n")
    L.append("O mod exclui as entradas abaixo; no FM24 a nota costuma ter mudado (Mertens 85 → 90), então a "
             "exclusão falha e a entrada continua. Há também ícones/lendas que só existem no FM24 "
             "(ex.: Zielinski no Napoli) — esses não aparecem nesta lista.\n")
    L.append("| Clube | Tipo | Nome | Nota no FM21 |\n|---|---|---|---|")
    for club, kind, nm, ratio in sorted(legends, key=lambda x: (cname(x[0]), x[1], x[2])):
        if club in div and div[club] in FOREIGN_HINT:
            continue
        L.append(f"| {cname(club)} | {kind} | {nm} | {ratio} |")

    L.append("\n### 2.4 Histórico de jogadores depois de 2000\n")
    L.append("Jogadores da base do FM21 cujas temporadas depois de 2000 o mod exclui. Quando a linha mudou no "
             "FM24 (datas, empréstimos), a exclusão falha e a temporada continua (ex.: De Rossi 2018, "
             "Montella 2006–2007). Abra o jogador e apague o que sobrar.\n")
    by_club = defaultdict(list)
    for uid, ys in plhs_del.items():
        by_club[contract.get(uid)].append((pname(uid), ys))
    for club in sorted(by_club, key=lambda c: (c is None, cname(c) if c else "")):
        if club == FREE_AGENT:
            label = "Sem clube"
        else:
            label = cname(club) if club else "Sem contrato no patch"
        items = ", ".join(f"{n} ({min(ys)}–{max(ys)})" for n, ys in sorted(by_club[club]))
        L.append(f"- **{label}** ({len(by_club[club])}): {items}")

    L.append("\n### 2.5 Recordes de competição\n")
    L.append("Recordes (maior goleada, artilheiro, público…) podem citar jogadores atuais (ex.: Higuaín na "
             "Serie A). Limpar à mão se incomodar.\n")

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    open(OUT, "w", encoding="utf-8").write("\n".join(L) + "\n")
    print(f"-> {OUT}  ({sum(len(v) for v in by_club.values())} players, {len(legends)} legends/icons, "
          f"{sum(len(c['rows']) for c in hist['clubs'].values())} club history rows)")


if __name__ == "__main__":
    main()
