#!/usr/bin/env python3
"""Read a downloaded translation file for a quality check, then score the review.

Standard library only, so it runs on any machine with Python 3.9+.

  read FILE     parse CSV/TSV/XLSX/PO/XLIFF/JSON into a work folder, run the
                automatic hints, print a JSON summary
  read-server   same, but read one translation from a Weblate server by its
                browser link; the API key comes from $WEBLATE_API_TOKEN
  score         validate the reviewed verdicts, compute the MQM score and grade,
                write the fixes spreadsheet

Exit code 2 with a JSON "error" object means the agent has a decision to make
(which column is the source, a missing source-language file); it is not a crash.
"""

from __future__ import annotations

import argparse
import csv
import json
import os
import re
import sys
import tempfile
import urllib.error
import urllib.parse
import urllib.request
import zipfile
from pathlib import Path
from typing import NoReturn
from xml.etree import ElementTree

CYRILLIC_LANGS = {"ru", "uk", "be", "bg", "sr", "mk", "kk", "ky", "mn", "tg"}
KEY_HEADERS = ("key", "context", "id", "string_id", "name", "ключ")
NOTE_HEADERS = ("explanation", "developer_comments", "comment", "comments", "description", "note", "notes", "пояснение")
LANG_HEADER = re.compile(r"^[a-z]{2,3}([_-][a-z]{2,4})?(@\w+)?$", re.IGNORECASE)
KEYLIKE = re.compile(r"^[A-Za-z0-9_.\-/:]+$")

PLACEHOLDER = re.compile(r"\{[^{}\s]*\}|%[A-Za-z_][A-Za-z0-9_]*%|%(?:\d+\$)?[-+ 0#]*\d*(?:\.\d+)?[sdifuxXeEgGc@]")
TAG = re.compile(r"</?[A-Za-z][^<>]*>")
NUMBER = re.compile(r"\d+(?:[.,]\d+)?")
SEVERITY_WEIGHT = {"neutral": 0, "minor": 1, "major": 5, "critical": 25}
SEVERITY_RU = {"critical": "Критично", "major": "Серьёзно", "minor": "Мелко", "neutral": "Замечание"}
# Russian names shown to the producer; the same table is in references/quality-model.md.
CATEGORY_RU = {
    "accuracy/mistranslation": "Искажён смысл",
    "accuracy/context_hallucination": "Перевод по ключу, а не по тексту",
    "accuracy/omission": "Пропущен смысл",
    "accuracy/addition": "Лишнее в переводе",
    "accuracy/untranslated": "Не переведено",
    "terminology/glossary_violation": "Термин не по глоссарию",
    "terminology/inconsistent_term": "Термин переведён по-разному",
    "terminology/acronym_leak": "Чужое сокращение",
    "terminology/inappropriate_register": "Слово не из той области",
    "fluency/grammar_syntax": "Грамматика",
    "fluency/spelling_orthography": "Орфография",
    "fluency/register_tone": "Сбит тон или обращение",
    "fluency/punctuation": "Пунктуация",
    "fluency/style": "Стилистика",
    "game_engine/broken_placeholder": "Сломана подстановка",
    "game_engine/markup_damage": "Сломана разметка",
    "game_engine/keybinding_format": "Обозначение клавиши",
    "game_engine/line_break": "Сломан перенос строки",
    "game_engine/overflow_risk": "Может не влезть",
}


def fail(code: str, **details) -> NoReturn:
    print(json.dumps({"error": code, **details}, ensure_ascii=False, indent=2))
    sys.exit(2)


def forms(value) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        return [str(v) for v in value]
    return [str(value)]


# --- readers -----------------------------------------------------------------


def unescape_weblate_csv(text: str) -> str:
    # Reverse of Weblate's Excel formula guard: '=SUM' is exported as "'=SUM'".
    if len(text) > 2 and text[0] == "'" and text[-1] == "'" and text[1] in "=+-@\\%":
        return text[1:-1].replace("\\|", "|")
    return text


def read_csv(path: Path) -> dict[str, list[list[str]]]:
    raw = path.read_text(encoding="utf-8-sig")
    if path.suffix.lower() == ".tsv":
        delimiter = "\t"
    else:
        first = raw.split("\n", 1)[0]
        delimiter = max((";", ",", "\t"), key=first.count)
    return {path.stem: [row for row in csv.reader(raw.splitlines(keepends=True), delimiter=delimiter)]}


def read_xlsx(path: Path) -> dict[str, list[list[str]]]:
    ns = {"m": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    rel_ns = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
    with zipfile.ZipFile(path) as z:
        shared: list[str] = []
        if "xl/sharedStrings.xml" in z.namelist():
            root = ElementTree.fromstring(z.read("xl/sharedStrings.xml"))
            shared = ["".join(t.text or "" for t in si.iter(f"{{{ns['m']}}}t")) for si in root.findall("m:si", ns)]
        rels = ElementTree.fromstring(z.read("xl/_rels/workbook.xml.rels"))
        targets = {r.get("Id"): r.get("Target") for r in rels}
        workbook = ElementTree.fromstring(z.read("xl/workbook.xml"))
        sheets: dict[str, list[list[str]]] = {}
        for sheet in workbook.iter(f"{{{ns['m']}}}sheet"):
            target = targets[sheet.get(rel_ns)]
            member = target.lstrip("/") if target.startswith("/") else f"xl/{target}"
            rows: list[list[str]] = []
            for row in ElementTree.fromstring(z.read(member)).iter(f"{{{ns['m']}}}row"):
                cells: dict[int, str] = {}
                for c in row.findall("m:c", ns):
                    letters = re.match(r"[A-Z]+", c.get("r", "A"))[0]
                    col = 0
                    for ch in letters:
                        col = col * 26 + ord(ch) - 64
                    kind = c.get("t")
                    if kind == "inlineStr":
                        value = "".join(t.text or "" for t in c.iter(f"{{{ns['m']}}}t"))
                    else:
                        v = c.find("m:v", ns)
                        value = "" if v is None or v.text is None else v.text
                        if kind == "s" and value:
                            value = shared[int(value)]
                    cells[col - 1] = value
                if cells:
                    rows.append([cells.get(i, "") for i in range(max(cells) + 1)])
            sheets[sheet.get("name")] = rows
    return sheets


def pick(headers: list[str], wanted: str | None, candidates: tuple[str, ...] = ()) -> int | None:
    lowered = [h.strip().lower() for h in headers]
    if wanted:
        if wanted.strip().lower() not in lowered:
            fail("column_not_found", column=wanted, headers=headers)
        return lowered.index(wanted.strip().lower())
    return next((lowered.index(c) for c in candidates if c in lowered), None)


def units_from_table(sheets: dict[str, list[list[str]]], args) -> tuple[list[dict], str | None]:
    names = list(sheets)
    if args.sheet:
        if args.sheet not in sheets:
            fail("sheet_not_found", sheet=args.sheet, sheets=names)
        names = [args.sheet]
    elif len([n for n in names if len(sheets[n]) > 1]) > 1:
        fail("choose_sheet", sheets={n: sheets[n][0] if sheets[n] else [] for n in names})
    name = next(n for n in names if sheets[n])
    rows = sheets[name]
    headers = [h.strip() for h in rows[0]]
    lowered = [h.lower() for h in headers]
    weblate_export = "source" in lowered and "target" in lowered

    key_idx = pick(headers, args.key_col, KEY_HEADERS)
    note_idx = pick(headers, None, NOTE_HEADERS)
    fuzzy_idx = pick(headers, None, ("fuzzy",))
    lang = args.lang
    if weblate_export and not (args.source_col or args.target_col):
        src_idx, tgt_idx = lowered.index("source"), lowered.index("target")
        location_idx = pick(headers, None, ("location",))
    else:
        location_idx = None
        lang_cols = [h for i, h in enumerate(headers) if LANG_HEADER.match(h) and i != key_idx and h.lower() != "id"]
        src_idx = pick(headers, args.source_col)
        if src_idx is None:
            fail("choose_source_column", language_columns=lang_cols, headers=headers)
        tgt_idx = pick(headers, args.target_col)
        if tgt_idx is None and lang:
            tgt_idx = pick(headers, lang)
        if tgt_idx is None:
            others = [h for h in lang_cols if h.lower() != headers[src_idx].lower()]
            if len(others) != 1:
                fail("choose_target_column", language_columns=others, headers=headers)
            tgt_idx = headers.index(others[0])
        lang = lang or headers[tgt_idx]

    def cell(row, idx):
        return unescape_weblate_csv(row[idx]) if idx is not None and idx < len(row) else ""

    units = []
    for row in rows[1:]:
        source, target = cell(row, src_idx), cell(row, tgt_idx)
        if not source.strip() and not target.strip():
            continue
        key = cell(row, key_idx) or cell(row, location_idx)
        units.append({
            "id": len(units) + 1,
            "key": key,
            "source": [source],
            "target": [target],
            "note": cell(row, note_idx).strip(),
            "needs_review": cell(row, fuzzy_idx).strip().lower() == "true",
        })
    return units, lang


def po_unescape(text: str) -> str:
    return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "r": "\r"}.get(m.group(1), m.group(1)), text)


def read_po(path: Path) -> tuple[list[dict], str | None]:
    entries, entry, field = [], None, None
    language = None

    def close():
        if entry and "msgid" in entry:
            entries.append(entry)

    for line in path.read_text(encoding="utf-8-sig").splitlines() + [""]:
        line = line.strip()
        if not line:
            close()
            entry, field = None, None
            continue
        if entry is None:
            entry = {"flags": "", "note": []}
        if line.startswith("#,"):
            entry["flags"] += line[2:]
        elif line.startswith("#."):
            entry["note"].append(line[2:].strip())
        elif line.startswith("#"):
            continue
        elif line.startswith('"') and field:
            entry[field] += po_unescape(line[1:-1])
        else:
            m = re.match(r'^(msgctxt|msgid_plural|msgid|msgstr(?:\[\d+\])?)\s+"(.*)"$', line)
            if m:
                field = m.group(1)
                entry[field] = po_unescape(m.group(2))
    units = []
    for e in entries:
        if e["msgid"] == "" and "msgctxt" not in e:
            m = re.search(r"^Language: *(\S+)", e.get("msgstr", ""), re.MULTILINE)
            language = m.group(1) if m else None
            continue
        plural_keys = sorted((k for k in e if k.startswith("msgstr[")), key=lambda k: int(k[7:-1]))
        target = [e[k] for k in plural_keys] if plural_keys else [e.get("msgstr", "")]
        source = [e["msgid"], e["msgid_plural"]] if "msgid_plural" in e else [e["msgid"]]
        units.append({
            "id": len(units) + 1,
            "key": e.get("msgctxt", ""),
            "source": source,
            "target": target,
            "note": " ".join(n for n in e["note"] if n),
            "needs_review": "fuzzy" in e["flags"],
        })
    return units, language


def read_xliff(path: Path) -> tuple[list[dict], str | None]:
    root = ElementTree.parse(path).getroot()
    local = lambda el: el.tag.rsplit("}", 1)[-1]
    language = next((el.get("target-language") or el.get("trgLang") for el in root.iter()
                     if el.get("target-language") or el.get("trgLang")), None)
    units = []
    for el in root.iter():
        if local(el) not in ("trans-unit", "unit"):
            continue
        parts = {local(c): c for c in el.iter() if local(c) in ("source", "target", "note")}
        source = "".join(parts["source"].itertext()) if "source" in parts else ""
        target_el = parts.get("target")
        target = "".join(target_el.itertext()) if target_el is not None else ""
        state = (target_el.get("state", "") if target_el is not None else "").lower()
        units.append({
            "id": len(units) + 1,
            "key": el.get("resname") or el.get("name") or el.get("id", ""),
            "source": [source],
            "target": [target],
            "note": "".join(parts["note"].itertext()).strip() if "note" in parts else "",
            "needs_review": state.startswith("needs") or state == "new",
        })
    return units, language


def flatten_json(data, prefix="") -> dict[str, list[str]]:
    flat: dict[str, list[str]] = {}
    if isinstance(data, dict):
        for k, v in data.items():
            flat.update(flatten_json(v, f"{prefix}.{k}" if prefix else str(k)))
    elif isinstance(data, list) and all(isinstance(v, str) for v in data):
        flat[prefix] = data
    elif data is not None:
        flat[prefix] = [str(data)]
    return flat


def key_values(path: Path) -> dict[str, list[str]]:
    """A monolingual file as key -> text (JSON, or PO whose msgid is the key)."""
    if path.suffix.lower() == ".json":
        return flatten_json(json.loads(path.read_text(encoding="utf-8-sig")))
    if path.suffix.lower() == ".po":
        return {u["key"] or u["source"][0]: u["target"] for u in read_po(path)[0]}
    fail("source_file_format", file=str(path), supported=[".json", ".po"])


def read_file(path: Path, args) -> tuple[list[dict], str | None]:
    ext = path.suffix.lower()
    if args.source_file:
        source = key_values(Path(args.source_file))
        target = key_values(path)
        units = [{"id": i, "key": k, "source": v, "target": target.get(k, [""]), "note": "", "needs_review": False}
                 for i, (k, v) in enumerate(source.items(), start=1)]
        extra = sorted(set(target) - set(source))
        if extra:
            print(json.dumps({"warning": "keys_missing_in_source_file", "count": len(extra), "examples": extra[:10]},
                             ensure_ascii=False), file=sys.stderr)
        return units, args.lang
    if ext in (".csv", ".tsv"):
        return units_from_table(read_csv(path), args)
    if ext == ".xlsx":
        return units_from_table(read_xlsx(path), args)
    if ext in (".xlf", ".xliff"):
        units, lang = read_xliff(path)
        return units, args.lang or lang
    if ext == ".po":
        units, lang = read_po(path)
        sources = [u["source"][0] for u in units if u["source"][0]]
        keylike = [s for s in sources if KEYLIKE.match(s) and re.search(r"[_.\d]", s)]
        if not any(u["key"] for u in units) and sources and len(keylike) >= 0.9 * len(sources):
            fail("need_source_file", reason="PO file holds keys instead of source text", examples=sources[:5])
        return units, args.lang or lang
    if ext == ".json":
        data = json.loads(path.read_text(encoding="utf-8-sig"))
        rows = data if isinstance(data, list) else list(data.values()) if isinstance(data, dict) else []
        if rows and all(isinstance(r, dict) and "source" in r for r in rows):
            keys = [r.get("key", r.get("context", "")) for r in rows] if isinstance(data, list) else list(data)
            units = [{"id": i, "key": k, "source": forms(r.get("source")), "target": forms(r.get("target")),
                      "note": r.get("note", ""), "needs_review": False}
                     for i, (k, r) in enumerate(zip(keys, rows), start=1)]
            return units, args.lang
        fail("need_source_file", reason="JSON file holds key -> translation only, no source text",
             examples=list(flatten_json(data))[:5])
    fail("unsupported_format", extension=ext, supported=[".csv", ".tsv", ".xlsx", ".po", ".xlf", ".xliff", ".json"])


def read_glossary(path: Path, args) -> list[dict]:
    sheets = read_xlsx(path) if path.suffix.lower() == ".xlsx" else read_csv(path)
    rows = next(r for r in sheets.values() if r)
    headers = [h.strip() for h in rows[0]]
    src = pick(headers, args.glossary_source_col, ("source", "src", "term", "термин"))
    tgt = pick(headers, args.glossary_target_col, ("target", "tgt", "translation"))
    # A loc-kit style glossary has language columns, like the kit itself.
    if src is None and getattr(args, "source_col", None):
        src = pick(headers, None, (args.source_col.lower(),))
    if tgt is None and args.lang:
        tgt = pick(headers, None, (args.lang.lower(),))
    if src is None or tgt is None:
        fail("choose_glossary_columns", headers=headers)
    terms = []
    for row in rows[1:]:
        s = row[src].strip() if src < len(row) else ""
        t = row[tgt].strip() if tgt < len(row) else ""
        if s and t:
            terms.append({"source": s, "target": t})
    return terms


# --- server (optional) -------------------------------------------------------


def api_get(url: str, token: str) -> dict:
    request = urllib.request.Request(url, headers={"Authorization": f"Token {token}", "Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=60) as response:
        return json.load(response)


def api_all(url: str, token: str) -> list[dict]:
    data = api_get(url, token)
    results = list(data.get("results", []))
    while data.get("next"):
        data = api_get(data["next"], token)
        results.extend(data.get("results", []))
    return results


def read_server(link: str) -> tuple[list[dict], str, list[dict], str]:
    token = os.environ.get("WEBLATE_API_TOKEN", "").strip()
    if not token:
        fail("missing_token", hint="set WEBLATE_API_TOKEN for this command only")
    parsed = urllib.parse.urlparse(link)
    parts = [p for p in parsed.path.split("/") if p]
    anchors = ("projects", "translate", "zen", "browse", "translations", "download")
    start = next((i for i, p in enumerate(parts) if p in anchors), None)
    if start is None or len(parts) < start + 4:
        fail("link_is_not_a_translation", hint="need a link to one language of one component", link=link)
    project, component, lang = parts[start + 1 : start + 4]
    base = f"{parsed.scheme}://{parsed.netloc}/api"
    rows = api_all(f"{base}/translations/{project}/{component}/{lang}/units/?page_size=1000", token)
    units = [{
        "id": i,
        "key": r.get("context") or "",
        "source": forms(r.get("source")),
        "target": forms(r.get("target")),
        "note": r.get("explanation") or r.get("note") or "",
        "needs_review": r.get("state") == 10,
    } for i, r in enumerate(rows, start=1)]
    glossary = []
    for comp in api_all(f"{base}/projects/{project}/components/", token):
        if not comp.get("is_glossary"):
            continue
        try:
            terms = api_all(f"{base}/translations/{project}/{comp['slug']}/{lang}/units/?page_size=1000", token)
        except urllib.error.HTTPError:
            continue
        for t in terms:
            s, g = " | ".join(forms(t.get("source"))).strip(), " | ".join(forms(t.get("target"))).strip()
            if s and g:
                glossary.append({"source": s, "target": g})
    return units, lang, glossary, f"{project}/{component}/{lang}"


# --- automatic hints ---------------------------------------------------------


def stem(word: str) -> str:
    w = word.casefold()
    return w if len(w) <= 5 else w[:-2]


def term_pattern(term: str) -> re.Pattern | None:
    words = re.findall(r"\w+", term)
    if len("".join(words)) < 3:
        return None
    return re.compile(r"(?<!\w)" + r"\W+".join(re.escape(stem(w)) + r"\w*" for w in words), re.IGNORECASE)


def automatic_hints(units: list[dict], lang: str | None, glossary: list[dict]) -> list[dict]:
    hints = []
    base_lang = (lang or "").lower().replace("-", "_").split("_")[0].split("@")[0]

    def add(unit, kind, form, note):
        hints.append({"unit_id": unit["id"], "key": unit["key"], "type": kind, "form": form, "note": note})

    by_term: dict[str, dict] = {}
    for t in glossary:
        entry = by_term.setdefault(t["source"].casefold(), {"term": t["source"], "targets": []})
        if t["target"] not in entry["targets"]:
            entry["targets"].append(t["target"])
    compiled = []
    for entry in by_term.values():
        pattern = term_pattern(entry["term"])
        renderings = [(r, term_pattern(r)) for r in entry["targets"]]
        renderings = [(r, p) for r, p in renderings if p]
        if pattern and renderings:
            compiled.append((entry, pattern, renderings))
    usage: dict[str, dict[str, list[int]]] = {}

    for unit in units:
        for i, target in enumerate(unit["target"]):
            source = unit["source"][min(i, len(unit["source"]) - 1)] if unit["source"] else ""
            if not source.strip():
                continue
            if not target.strip():
                add(unit, "empty_target", i, "no translation")
                continue
            plain = lambda s: TAG.sub(" ", PLACEHOLDER.sub(" ", s))
            if target == source and re.search(r"[^\W\d_]{2}", plain(source)):
                add(unit, "same_as_source", i, "target identical to source")
            if sorted(PLACEHOLDER.findall(source)) != sorted(PLACEHOLDER.findall(target)):
                add(unit, "placeholder_mismatch", i,
                    f"source {sorted(PLACEHOLDER.findall(source))} vs target {sorted(PLACEHOLDER.findall(target))}")
            if sorted(TAG.findall(source)) != sorted(TAG.findall(target)):
                add(unit, "markup_mismatch", i, f"source {sorted(TAG.findall(source))} vs target {sorted(TAG.findall(target))}")
            for token, label in (("$", "$"), ("\\n", "\\n"), ("\n", "newline")):
                if source.count(token) != target.count(token):
                    add(unit, "line_break_mismatch", i, f"'{label}': source {source.count(token)}, target {target.count(token)}")
            if source.count("[") + source.count("]") != target.count("[") + target.count("]"):
                add(unit, "bracket_mismatch", i, "square bracket count differs")
            src_numbers = [n.replace(",", ".") for n in NUMBER.findall(plain(source))]
            tgt_numbers = [n.replace(",", ".") for n in NUMBER.findall(plain(target))]
            missing = [n for n in set(src_numbers) if src_numbers.count(n) > tgt_numbers.count(n)]
            if missing:
                add(unit, "number_missing", i, f"numbers not found in target: {sorted(missing)}")
            if base_lang and base_lang not in CYRILLIC_LANGS and re.search(r"[Ѐ-ӿ]", target):
                add(unit, "cyrillic_in_target", i, "Cyrillic letters in a non-Cyrillic target")
            for entry, pattern, renderings in compiled:
                if not pattern.search(source):
                    continue
                used = [r for r, p in renderings if p.search(target)]
                if not used:
                    add(unit, "glossary_term_missing", i,
                        f"source uses '{entry['term']}', target has none of: {', '.join(entry['targets'])}")
                for r in used:
                    usage.setdefault(entry["term"], {}).setdefault(r, []).append(unit["id"])

    for term, variants in usage.items():
        if len(variants) > 1:
            detail = "; ".join(f"'{r}' in units {ids[:5]}" for r, ids in sorted(variants.items()))
            first = min(i for ids in variants.values() for i in ids)
            hints.append({"unit_id": first, "key": "", "type": "glossary_term_varies", "form": 0,
                          "note": f"'{term}' rendered {len(variants)} different ways: {detail}"})
    return hints


def words(units: list[dict]) -> int:
    return sum(len(s.split()) for u in units for s in u["source"])


def write_workdir(workdir: Path, units, lang, glossary, glossary_source, origin) -> None:
    workdir.mkdir(parents=True, exist_ok=True)
    with open(workdir / "units.jsonl", "w", encoding="utf-8") as f:
        for u in units:
            f.write(json.dumps(u, ensure_ascii=False) + "\n")
    hints = automatic_hints(units, lang, glossary)
    (workdir / "hints.json").write_text(json.dumps(hints, ensure_ascii=False, indent=1), encoding="utf-8")
    counts: dict[str, int] = {}
    for h in hints:
        counts[h["type"]] = counts.get(h["type"], 0) + 1
    summary = {
        "origin": origin,
        "workdir": str(workdir),
        "language": lang,
        "units": len(units),
        "source_words": words(units),
        "empty_targets": sum(1 for u in units if not any(t.strip() for t in u["target"])),
        "marked_needs_review": sum(1 for u in units if u["needs_review"]),
        "units_with_note": sum(1 for u in units if u["note"]),
        "glossary_source": glossary_source,
        "glossary_terms": len(glossary),
        "hints_by_type": counts,
    }
    (workdir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=False, indent=2))


# --- scoring -----------------------------------------------------------------


def expand_ids(items: list) -> set[int]:
    ids: set[int] = set()
    for item in items:
        if isinstance(item, str) and re.fullmatch(r"\d+-\d+", item.strip()):
            a, b = map(int, item.split("-"))
            ids.update(range(a, b + 1))
        else:
            ids.add(int(item))
    return ids


def score(units: list[dict], payload: dict) -> dict:
    by_id = {u["id"]: u for u in units}
    scope = payload.get("review_scope")
    verdicts = payload.get("verdicts", [])
    if not isinstance(scope, dict):
        fail("missing_review_scope", hint='{"coverage": "full"} or {"reviewed_unit_ids": [1, "2-40"]}')
    if scope.get("coverage") == "full":
        reviewed = set(by_id)
    elif scope.get("reviewed_unit_ids"):
        reviewed = expand_ids(scope["reviewed_unit_ids"])
        unknown = sorted(reviewed - set(by_id))
        if unknown:
            fail("unknown_unit_ids", ids=unknown[:20])
    else:
        fail("missing_review_scope", hint='{"coverage": "full"} or {"reviewed_unit_ids": [1, "2-40"]}')

    counts = dict.fromkeys(SEVERITY_WEIGHT, 0)
    problems = []
    for n, v in enumerate(verdicts, start=1):
        uid = v.get("unit_id")
        sev = str(v.get("severity", "")).lower()
        if uid not in reviewed:
            problems.append(f"verdict {n}: unit {uid} is outside review_scope")
            continue
        if sev not in SEVERITY_WEIGHT:
            problems.append(f"verdict {n}: severity '{sev}' is not one of {list(SEVERITY_WEIGHT)}")
            continue
        if v.get("category") not in CATEGORY_RU:
            problems.append(f"verdict {n}: category '{v.get('category')}' is not in references/quality-model.md")
            continue
        unit = by_id[uid]
        # A verdict must name its unit twice (id and key, or id and source) so a
        # mistyped id fails here instead of pinning a defect on an innocent string.
        if unit["key"]:
            if v.get("key") != unit["key"]:
                problems.append(f"verdict {n}: unit {uid} has key '{unit['key']}', verdict says '{v.get('key')}'")
                continue
        elif v.get("source") not in unit["source"]:
            problems.append(f"verdict {n}: unit {uid} has no key, so 'source' must equal its source text")
            continue
        counts[sev] += 1
    if problems:
        fail("invalid_verdicts", problems=problems[:20], total=len(problems))

    scoped = [by_id[i] for i in sorted(reviewed)]
    reviewed_words = words(scoped)
    penalty = sum(SEVERITY_WEIGHT[s] * c for s, c in counts.items())
    mqm = round(max(0.0, 100.0 - penalty / reviewed_words * 100.0), 2) if reviewed_words else 100.0
    full = len(reviewed) == len(units)
    if counts["critical"]:
        grade = "blocked_critical"
    elif not full:
        grade = "not_gradable_partial"
    elif mqm >= 95:
        grade = "A"
    elif mqm >= 85:
        grade = "B"
    elif mqm >= 70:
        grade = "C"
    else:
        grade = "fail"
    return {
        "coverage": "full" if full else "partial",
        "reviewed_units": len(reviewed),
        "total_units": len(units),
        "reviewed_words": reviewed_words,
        "total_words": words(units),
        "counts": counts,
        "penalty_points": penalty,
        "mqm_score": mqm,
        "grade": grade,
    }


def column_name(index: int) -> str:
    name = ""
    index += 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def write_xlsx(path: Path, headers: list[str], rows: list[list[str]]) -> None:
    def esc(text: str) -> str:
        text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", str(text))
        return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")

    sheet_rows = []
    for r, values in enumerate([headers] + rows, start=1):
        bold = ' s="1"' if r == 1 else ""
        cells = "".join(
            f'<c r="{column_name(c)}{r}" t="inlineStr"{bold}>'
            f'<is><t xml:space="preserve">{esc(v)}</t></is></c>'
            for c, v in enumerate(values)
        )
        sheet_rows.append(f'<row r="{r}">{cells}</row>')
    widths = "".join(f'<col min="{i + 1}" max="{i + 1}" width="{w}" customWidth="1"/>'
                     for i, w in enumerate([24, 40, 40, 12, 22, 45, 40]))
    files = {
        "[Content_Types].xml": '<?xml version="1.0" encoding="UTF-8"?><Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types"><Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/><Default Extension="xml" ContentType="application/xml"/><Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/><Override PartName="/xl/worksheets/sheet1.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/><Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/></Types>',
        "_rels/.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/></Relationships>',
        "xl/_rels/workbook.xml.rels": '<?xml version="1.0" encoding="UTF-8"?><Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships"><Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet1.xml"/><Relationship Id="rId2" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/></Relationships>',
        "xl/workbook.xml": '<?xml version="1.0" encoding="UTF-8"?><workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"><sheets><sheet name="Fixes" sheetId="1" r:id="rId1"/></sheets></workbook>',
        "xl/styles.xml": '<?xml version="1.0" encoding="UTF-8"?><styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main"><fonts count="2"><font><sz val="11"/></font><font><b/><sz val="11"/></font></fonts><fills count="2"><fill><patternFill patternType="none"/></fill><fill><patternFill patternType="gray125"/></fill></fills><borders count="1"><border><left/><right/><top/><bottom/><diagonal/></border></borders><cellStyleXfs count="1"><xf numFmtId="0" fontId="0" fillId="0" borderId="0"/></cellStyleXfs><cellXfs count="2"><xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/><xf numFmtId="0" fontId="1" fillId="0" borderId="0" xfId="0" applyFont="1"/></cellXfs><cellStyles count="1"><cellStyle name="Normal" xfId="0" builtinId="0"/></cellStyles></styleSheet>',
        "xl/worksheets/sheet1.xml": '<?xml version="1.0" encoding="UTF-8"?><worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        f'<sheetViews><sheetView workbookViewId="0"><pane ySplit="1" topLeftCell="A2" state="frozen"/></sheetView></sheetViews><cols>{widths}</cols>'
        f'<sheetData>{"".join(sheet_rows)}</sheetData></worksheet>',
    }
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as z:
        for name, content in files.items():
            z.writestr(name, content)


def run_score(args) -> None:
    workdir = Path(args.workdir)
    units = [json.loads(line) for line in (workdir / "units.jsonl").read_text(encoding="utf-8").splitlines() if line]
    payload = json.loads(Path(args.verdicts).read_text(encoding="utf-8"))
    result = score(units, payload)
    if args.fixes_xlsx:
        by_id = {u["id"]: u for u in units}
        order = {"critical": 0, "major": 1, "minor": 2, "neutral": 3}
        rows = []
        for v in sorted(payload.get("verdicts", []), key=lambda v: (order[v["severity"].lower()], v["unit_id"])):
            u = by_id[v["unit_id"]]
            rows.append([u["key"], " | ".join(u["source"]), " | ".join(u["target"]),
                         SEVERITY_RU[v["severity"].lower()], CATEGORY_RU[v["category"]], v.get("problem", ""),
                         v.get("suggestion", "")])
        write_xlsx(Path(args.fixes_xlsx), ["Ключ", "Оригинал", "Перевод сейчас", "Серьёзность",
                                           "Категория", "Что не так", "Как исправить"], rows)
        result["fixes_xlsx"] = str(Path(args.fixes_xlsx).resolve())
    print(json.dumps(result, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)

    def glossary_args(p):
        p.add_argument("--glossary", help="glossary CSV/TSV/XLSX")
        p.add_argument("--glossary-source-col")
        p.add_argument("--glossary-target-col")
        p.add_argument("--workdir", help="work folder (default: system temp)")

    read = sub.add_parser("read", help="read a downloaded file")
    read.add_argument("file")
    read.add_argument("--lang", help="target language code, e.g. de")
    read.add_argument("--source-file", help="source-language file for key -> text JSON/PO downloads")
    read.add_argument("--source-col")
    read.add_argument("--target-col")
    read.add_argument("--key-col")
    read.add_argument("--sheet")
    glossary_args(read)

    server = sub.add_parser("read-server", help="read one translation from Weblate by its link")
    server.add_argument("link")
    server.add_argument("--lang")
    glossary_args(server)

    sc = sub.add_parser("score", help="score reviewed verdicts")
    sc.add_argument("--workdir", required=True)
    sc.add_argument("--verdicts", required=True)
    sc.add_argument("--fixes-xlsx")

    args = parser.parse_args()
    if args.command == "score":
        run_score(args)
        return

    if args.command == "read":
        path = Path(args.file)
        if not path.is_file():
            fail("file_not_found", file=str(path))
        units, lang = read_file(path, args)
        glossary, glossary_source = [], None
        origin = str(path.resolve())
        stem_name = path.stem
    else:
        units, lang, glossary, origin = read_server(args.link)
        glossary_source = "server" if glossary else None
        stem_name = origin.replace("/", "-")
    if args.glossary:
        glossary, glossary_source = read_glossary(Path(args.glossary), args), str(Path(args.glossary).resolve())
    if not units:
        fail("no_strings_found", origin=origin)
    if not lang:
        # Weblate's CSV and XLSX downloads carry no language code, and the
        # Cyrillic check silently does nothing without one.
        fail("need_language", hint="pass --lang with the target language code", examples=units[:3])
    workdir = Path(args.workdir) if args.workdir else Path(tempfile.gettempdir()) / f"lqa-{stem_name}-{lang or 'xx'}"
    write_workdir(workdir, units, lang, glossary, glossary_source, origin)


if __name__ == "__main__":
    main()
