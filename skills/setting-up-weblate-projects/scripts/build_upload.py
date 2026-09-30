#!/usr/bin/env python3
"""Turn the contract CSV files into the upload artifacts the Weblate REST API accepts.

Standard library only, so it runs on any machine with Python 3.9+. It needs no
HCGameLoc checkout: it renders the same PO and TBX content that the server-side
loc_kit_ingest renders, and parses its own output back to prove it.

  strings KIT    string kit CSV -> <slug>.zip (one monolingual PO per language,
                 flat) and <slug>.explanations.json (key -> explanation)
  glossary CSV   glossary CSV -> <slug>.zip (tbx/<target>.tbx per target language)
  project        record the project name and slug
  machinery FILE validate the automatic-suggestion prompts and record them
  check DIR      re-read every input, parse every artifact back, compare them
                 cell by cell and cross-check languages; the readiness gate

Every command merges its result into DIR/manifest.json (paths in it are
relative to DIR) and prints one JSON summary. Exit code 2 with a JSON "error"
object means the input needs a fix or a decision; it is not a crash.
"""

from __future__ import annotations

import argparse
import csv
import io
import json
import re
import sys
import zipfile
from pathlib import Path
from typing import NoReturn
from xml.etree import ElementTree
from xml.sax.saxutils import escape

# Language codes translate-toolkit knows: loc_kit_ingest resolves headers against them.
LANGS = set(
    "ach af ak am an anp ar arn as ast ay az be bg bn bo br brx bs ca cgg cs csb cy da de doi dz el en eo es "
    "et eu fa ff fi fil fo fr fur fy ga gd gl gu gun ha he hi hne hr ht hu hy ia id is it ja jbo jv ka kab kk "
    "kl km kn ko kok ks ku kw ky lb ln lo lt lv mai me mfe mg mi mk ml mn mni mnk mr ms mt my nah nap nb ne nl "
    "nn nqo nso oc or pa pap pl pms ps pt rm ro ru rw sa sah sat scn sco sd se si sk sl so son sq sr st su sv "
    "sw szl ta te tg th ti tk tr tt ug uk ur uz ve vi wa wo yo yue zu "
    "bn_BD bn_IN en_GB en_ZA es_AR pt_BR zh_CN zh_HK zh_TW".split()
)
ALIASES = {"zh_tc": "zh_Hant", "zh_hant": "zh_Hant", "zh_sc": "zh_Hans", "zh_hans": "zh_Hans", "ch": "zh_Hans",
           "ch_s": "zh_Hans", "ch_t": "zh_Hant", "cn": "zh_Hans", "jp": "ja", "kr": "ko"}
CODE = r"([A-Za-z]{2,3}(?:[-_][A-Za-z0-9]{1,8})*)"
PARENS_CODE = re.compile(r"\(\s*" + CODE + r"\s*\)\s*$")
BARE_CODE = re.compile(r"^\s*" + CODE + r"\s*$")
# A header that spells a language out resolves to no code, so the server would drop the column.
LANGUAGE_NAMES = (
    "english russian german french spanish portug brazil italian polish turkish japanese korean chinese arabic "
    "vietnamese thai indonesian dutch swedish norwegian danish finnish czech hungarian romanian greek hebrew "
    "ukrainian hindi malay filipino английск русск немецк французск испанск португальск итальянск польск "
    "турецк японск корейск китайск арабск вьетнамск украинск"
).split()
EXPLANATION_HEADERS = {"explanation", "explanations", "пояснение", "пояснения"}
FLAGS_HEADERS = {"flags", "weblate-flags", "флаги"}
GLOSSARY_FLAGS = {"read-only", "forbidden", "exact"}
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
INSTRUCTION_LIMIT = 1000  # LLM_LANGUAGE_INSTRUCTION_LENGTH, weblate/machinery/forms.py
MIN_FILL = 5.0  # percent of rows; loc_kit_ingest drops a sparser string-kit language
EXAMPLES = 20
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
TEXT_ENTITIES = {"\r": "&#13;"}
ATTR_ENTITIES = {'"': "&quot;", "\n": "&#10;", "\r": "&#13;", "\t": "&#9;"}
TBX_HEAD = """<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE martif PUBLIC "ISO 12200:1999A//DTD MARTIF core (DXFcdV04)//EN" "TBXcdv04.dtd">
<martif type="TBX" xml:lang="{lang}">
    <martifHeader><fileDesc><sourceDesc><p>build_upload.py</p></sourceDesc></fileDesc></martifHeader>
    <text>
        <body>
"""
TBX_TAIL = "        </body>\n    </text>\n</martif>\n"


def fail(code: str, **details) -> NoReturn:
    print(json.dumps({"error": code, **details}, ensure_ascii=False, indent=2))
    sys.exit(2)


def emit(summary: dict) -> None:
    print(json.dumps(summary, ensure_ascii=False, indent=2))


def language_code(text: str) -> str | None:
    """Weblate code for a header such as `pt-BR` or `Japanese (ja)`; None for anything else."""
    match = PARENS_CODE.search(text) or BARE_CODE.match(text)
    if not match:
        return None
    norm = match.group(1).replace("-", "_")
    if norm.casefold() in ALIASES:
        return ALIASES[norm.casefold()]
    if norm in LANGS:
        return norm
    base, _, region = norm.partition("_")
    if region:
        canonical = f"{base.lower()}_{region.upper()}"
        return canonical if canonical in LANGS or base.lower() in LANGS else None
    return base.lower() if base.lower() in LANGS else None


def xml_lang(code: str) -> str:
    return code.replace("_", "-")


def is_numeric(values: list[str]) -> bool:
    present = [v.strip() for v in values if v.strip()]
    return bool(present) and all(v.lstrip("-").replace(".", "", 1).isdigit() for v in present)


# --- reading -------------------------------------------------------------------


def read_table(path: Path) -> list[list[str]]:
    try:
        # Bytes, not read_text: universal newlines would rewrite \r\n inside quoted cells.
        text = path.read_bytes().decode("utf-8-sig")
    except (OSError, UnicodeDecodeError) as exc:
        fail("unreadable_input", path=str(path), detail=str(exc))

    def parse(delimiter: str):
        return csv.reader(io.StringIO(text, newline=""), delimiter=delimiter)

    def header_score(delimiter: str) -> tuple[int, int]:
        header = next(parse(delimiter), [])
        return sum(language_code(cell) is not None for cell in header), len(header)

    try:
        # The delimiter is the one under which the header row names the most languages.
        rows = list(parse(max((";", "\t", ","), key=header_score)))
    except csv.Error as exc:
        fail("unreadable_input", path=str(path), detail=str(exc))
    if len(rows) < 2:
        fail("no_data_rows", path=str(path))
    return rows


def classify_header(header: list[str], source: str, first: int) -> tuple[dict[int, str], dict[str, list[int]]]:
    """Split header columns into languages {column: code} and the other column groups."""
    langs: dict[int, str] = {}
    groups: dict[str, list[int]] = {"explanation": [], "flags": [], "names": [], "other": []}
    for col in range(first, len(header)):
        cell, code = header[col].strip().casefold(), language_code(header[col])
        if code in langs.values():
            fail("language_column_duplicate", language=code, header=header)
        if code:
            langs[col] = code
        elif cell in EXPLANATION_HEADERS:
            groups["explanation"].append(col)
        elif cell in FLAGS_HEADERS:
            groups["flags"].append(col)
        elif any(name in "".join(ch for ch in cell if ch.isalpha()) for name in LANGUAGE_NAMES):
            groups["names"].append(col)
        else:
            groups["other"].append(col)
    if groups["names"]:
        fail("language_header_not_code", headers=[header[c] for c in groups["names"]],
             hint="rewrite each header to a code such as en, pt-BR, zh-Hans or Name(code)")
    if source not in langs.values():
        fail("source_column_missing", source=source, languages=list(langs.values()))
    if langs[min(langs)] != source:
        fail("source_not_first_language", source=source, first_language=langs[min(langs)])
    for group in ("explanation", "flags"):
        if len(groups[group]) > 1:
            fail(f"{group}_column_duplicate", columns=[c + 1 for c in groups[group]])
    return langs, groups


def fail_on_problems(problems: dict[str, list]) -> None:
    found = {code: rows for code, rows in problems.items() if rows}
    if found:
        code, rows = next(iter(found.items()))
        fail(code, count=len(rows), rows=rows[:EXAMPLES], also={c: len(r) for c, r in found.items() if c != code})


def read_kit(path: Path, source: str) -> dict:
    rows = read_table(path)
    header = rows[0]
    keys = [col for col, cell in enumerate(header) if cell.strip().casefold() == "key"]
    if len(keys) != 1:
        fail("key_column_missing" if not keys else "key_column_duplicate", columns=[c + 1 for c in keys])
    if keys[0] != 0:
        fail("key_column_not_first", column=keys[0] + 1)
    langs, groups = classify_header(header, source, 1)
    if groups["flags"]:
        fail("flags_column_in_string_kit", column=groups["flags"][0] + 1,
             hint="the importer swallows it and nothing applies it; rename the column")
    problems: dict[str, list] = {c: [] for c in ("ragged_row", "empty_key", "duplicate_key",
                                                  "row_empty_in_all_languages", "row_without_source")}
    data, seen, blank = [], {}, 0
    for number, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            blank += 1
        elif len(row) != len(header):
            problems["ragged_row"].append({"row": number, "cells": len(row), "expected": len(header)})
        elif not row[0].strip():
            problems["empty_key"].append(number)
        elif row[0] in seen:
            problems["duplicate_key"].append({"row": number, "key": row[0], "first_row": seen[row[0]]})
        else:
            seen[row[0]] = number
            if not any(row[col].strip() for col in langs):
                problems["row_empty_in_all_languages"].append({"row": number, "key": row[0]})
            elif not row[min(langs)].strip():
                problems["row_without_source"].append({"row": number, "key": row[0]})
            data.append((number, row))
    fail_on_problems(problems)
    if not data:
        fail("no_data_rows", path=str(path))

    # A metadata column holding only numbers is a location reference (#:), any other a developer note (#.).
    refs = [c for c in groups["other"] if is_numeric([row[c] for _, row in data])]
    notes = [c for c in groups["other"] if c not in refs]
    expl = groups["explanation"][0] if groups["explanation"] else None
    units = [{"row": number, "key": row[0], "values": {code: row[col] for col, code in langs.items()},
              "notes": [row[c] for c in notes if row[c].strip()], "refs": [row[c] for c in refs if row[c].strip()]}
             for number, row in data]

    warnings: dict = {}
    for code in langs.values():
        fill = round(100.0 * sum(1 for u in units if u["values"][code].strip()) / len(units), 1)
        if fill < MIN_FILL:
            warnings.setdefault("sparse_languages", {})[code] = fill
        if code == source:
            continue
        same = sum(1 for u in units if u["values"][code] == u["values"][source])
        empty = sum(1 for u in units if not u["values"][code].strip())
        for kind, count in (("target_equals_source", same), ("empty_target", empty)):
            if count:
                warnings.setdefault(kind, {})[code] = count
    spaced = [u["key"] for u in units if u["key"] != u["key"].strip()]
    if spaced:
        warnings["keys_with_outer_whitespace"] = spaced
    return {"languages": list(langs.values()), "units": units, "blank_rows": blank, "warnings": warnings,
            "explanations": {row[0]: row[expl].strip() for _, row in data if expl is not None and row[expl].strip()}}


def read_glossary(path: Path, source: str) -> dict:
    rows = read_table(path)
    header = rows[0]
    langs, groups = classify_header(header, source, 0)
    expl = groups["explanation"][0] if groups["explanation"] else None
    flags_col = groups["flags"][0] if groups["flags"] else None
    problems: dict[str, list] = {c: [] for c in ("ragged_row", "unknown_column", "empty_source_term",
                                                  "duplicate_source_term", "invalid_flag")}
    terms, seen = [], {}
    for number, row in enumerate(rows[1:], start=2):
        if not any(cell.strip() for cell in row):
            continue
        if len(row) != len(header):
            problems["ragged_row"].append({"row": number, "cells": len(row), "expected": len(header)})
            continue
        stray = [header[c] or f"column{c + 1}" for c in groups["other"] if row[c].strip()]
        if stray:
            problems["unknown_column"].append({"row": number, "columns": stray})
        # The server trims outer whitespace from terms and explanations: TBX drops it on write.
        term = {"row": number, "values": {code: row[col].strip() for col, code in langs.items()},
                "explanation": row[expl].strip() if expl is not None else "", "flags": []}
        source_term = term["values"][source]
        if not source_term:
            problems["empty_source_term"].append(number)
        elif source_term in seen:
            problems["duplicate_source_term"].append({"row": number, "term": source_term,
                                                      "first_row": seen[source_term]})
        seen.setdefault(source_term, number)
        if flags_col is not None and row[flags_col].strip():
            tokens = [token.strip() for token in row[flags_col].split(",")]
            if any(token not in GLOSSARY_FLAGS for token in tokens):
                problems["invalid_flag"].append({"row": number, "flags": row[flags_col],
                                                 "allowed": sorted(GLOSSARY_FLAGS)})
            term["flags"] = sorted(set(tokens))
        terms.append(term)
    fail_on_problems(problems)
    if not terms:
        fail("no_data_rows", path=str(path))

    targets, warnings = [], {}
    for code in langs.values():
        blank = sum(1 for t in terms if not t["values"][code])
        if code == source:
            continue
        if blank == len(terms):  # the server creates no TBX for a target without a single term
            warnings.setdefault("target_language_without_terms", []).append(code)
            continue
        targets.append(code)
        if blank:
            warnings.setdefault("blank_targets", {})[code] = blank
    if not targets:
        fail("no_target_language", languages=list(langs.values()))
    return {"languages": [source, *targets], "targets": targets, "terms": terms, "warnings": warnings}


# --- rendering and parsing back ------------------------------------------------------


def po_escape(text: str) -> str:
    return (text.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
            .replace("\t", "\\t").replace("\r", "\\r"))


def po_field(name: str, text: str) -> list[str]:
    parts = re.findall(r"[^\n]*\n|[^\n]+", text)
    if len(parts) <= 1:
        return [f'{name} "{po_escape(text)}"']
    return [f'{name} ""', *(f'"{po_escape(part)}"' for part in parts)]


def render_po(kit: dict, code: str, source: str) -> str:
    header = ["MIME-Version: 1.0\n", "Content-Type: text/plain; charset=UTF-8\n",
              "Content-Transfer-Encoding: 8bit\n", f"Language: {xml_lang(code)}\n"]
    blocks = ["\n".join(['msgid ""', 'msgstr ""', *(f'"{po_escape(line)}"' for line in header)])]
    for unit in kit["units"]:
        lines = []
        if code == source:  # developer notes and references live in the source-language file only
            lines += [f"#. {line}" if line else "#." for note in unit["notes"] for line in note.split("\n")]
            lines += [f"#: {ref}" for ref in unit["refs"]]
        blocks.append("\n".join(lines + po_field("msgid", unit["key"]) + po_field("msgstr", unit["values"][code])))
    return "\n\n".join(blocks) + "\n"


def parse_po(text: str) -> tuple[str, list[dict]]:
    """Parse the PO this script writes; returns (Language header value, entries)."""
    def unescape(s: str) -> str:
        return re.sub(r"\\(.)", lambda m: {"n": "\n", "t": "\t", "r": "\r"}.get(m.group(1), m.group(1)), s)

    entries = []
    for block in text.split("\n\n"):
        entry: dict = {"notes": [], "refs": [], "msgid": "", "msgstr": ""}
        field = ""
        for line in block.split("\n"):
            if line.startswith(("#.", "#:")):
                entry["notes" if line[1] == "." else "refs"].append(line[3:])
            elif line.startswith('"'):
                entry[field] += unescape(line[1:-1])
            elif line:
                field, _, rest = line.partition(" ")
                entry[field] = unescape(rest[1:-1])
        entries.append(entry)
    header = entries.pop(0)["msgstr"] if entries and entries[0]["msgid"] == "" else ""
    language = re.search(r"^Language: (.*)$", header, re.MULTILINE)
    return (language.group(1) if language else ""), entries


def term_id(term: dict, source: str) -> str:
    # loc_kit_ingest identity: JSON [section, source term]; a flat glossary has no section.
    return json.dumps(["", term["values"][source]], ensure_ascii=False, separators=(",", ":"))


def entry_flags(term: dict, target: str) -> str:
    # `exact` binds a concrete target form, so an entry with a blank target does not carry it.
    return ", ".join(f for f in term["flags"] if f != "exact" or term["values"][target])


def render_tbx(glossary: dict, target: str, source: str) -> str:
    out = [TBX_HEAD.format(lang=xml_lang(source))]
    for term in glossary["terms"]:
        flags = entry_flags(term, target)
        flags_attr = f' weblate-flags="{escape(flags, ATTR_ENTITIES)}"' if flags else ""
        out.append(f'            <termEntry id="{escape(term_id(term, source), ATTR_ENTITIES)}"{flags_attr}>\n')
        for code in (source, target):
            value = escape(term["values"][code], TEXT_ENTITIES)
            out.append(f'                <langSet xml:lang="{xml_lang(code)}"><tig><term>{value}</term></tig>'
                       "</langSet>\n")
        if term["explanation"]:
            out.append(f"                <descrip>{escape(term['explanation'], TEXT_ENTITIES)}</descrip>\n")
        out.append("            </termEntry>\n")
    return "".join(out) + TBX_TAIL


def write_zip(path: Path, files: dict[str, str]) -> None:
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, content in files.items():
            archive.writestr(name, content.encode("utf-8"))


def verify_strings(kit: dict, source: str, zip_path: Path, explanations_path: Path) -> list[str]:
    problems = []
    with zipfile.ZipFile(zip_path) as archive:
        expected = {f"{code}.po" for code in kit["languages"]}
        if set(archive.namelist()) != expected:
            return [f"{zip_path.name}: files {sorted(archive.namelist())}, expected {sorted(expected)}"]
        for code in kit["languages"]:
            language, entries = parse_po(archive.read(f"{code}.po").decode("utf-8"))
            if language != xml_lang(code):
                problems.append(f"{code}.po: Language header {language!r}")
            if [e["msgid"] for e in entries] != [u["key"] for u in kit["units"]]:
                problems.append(f"{code}.po: key list or order differs from the kit")
                continue
            for entry, unit in zip(entries, kit["units"]):
                at_source = code == source
                got = (entry["msgstr"], "\n".join(entry["notes"]), entry["refs"])
                want = (unit["values"][code], "\n".join(unit["notes"]) if at_source else "",
                        unit["refs"] if at_source else [])
                if got != want:
                    problems.append(f"{code}.po row {unit['row']} key {unit['key']!r}: {got!r} != {want!r}")
    if json.loads(explanations_path.read_text(encoding="utf-8")) != kit["explanations"]:
        problems.append(f"{explanations_path.name}: differs from the kit's Explanation column")
    return problems


def verify_glossary(glossary: dict, source: str, zip_path: Path) -> list[str]:
    problems = []
    with zipfile.ZipFile(zip_path) as archive:
        expected = {f"tbx/{code}.tbx" for code in glossary["targets"]}
        if set(archive.namelist()) != expected:
            return [f"{zip_path.name}: files {sorted(archive.namelist())}, expected {sorted(expected)}"]
        for code in glossary["targets"]:
            root = ElementTree.fromstring(archive.read(f"tbx/{code}.tbx"))
            if root.get(XML_LANG) != xml_lang(source):
                problems.append(f"tbx/{code}.tbx: martif xml:lang {root.get(XML_LANG)!r}")
            entries = list(root.iter("termEntry"))
            if [e.get("id") for e in entries] != [term_id(t, source) for t in glossary["terms"]]:
                problems.append(f"tbx/{code}.tbx: term list or order differs from the glossary")
                continue
            for entry, term in zip(entries, glossary["terms"]):
                terms = {ls.get(XML_LANG): ls.findtext("tig/term") or "" for ls in entry.findall("langSet")}
                got = (terms, entry.findtext("descrip") or "", entry.get("weblate-flags", ""))
                want = ({xml_lang(c): term["values"][c] for c in (source, code)}, term["explanation"],
                        entry_flags(term, code))
                if got != want:
                    problems.append(f"tbx/{code}.tbx row {term['row']}: {got!r} != {want!r}")
    return problems


# --- manifest and commands --------------------------------------------------------------


def load_manifest(out: Path) -> dict:
    path = out / "manifest.json"
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}


def save_manifest(out: Path, manifest: dict) -> None:
    out.mkdir(parents=True, exist_ok=True)
    (out / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def prepare(args: argparse.Namespace) -> tuple[Path, dict, str]:
    """Shared start of strings/glossary: the manifest and the settled source language."""
    out = Path(args.out)
    manifest = load_manifest(out)
    source = language_code(args.source_lang)
    if source is None:
        fail("unknown_source_language", given=args.source_lang)
    if manifest.get("source_language", source) != source:
        fail("source_language_mismatch", manifest=manifest["source_language"], given=source)
    manifest["source_language"] = source
    check_name_slug(args.name, args.slug)
    out.mkdir(parents=True, exist_ok=True)  # the ZIPs are written before the manifest
    return out, manifest, source


def check_name_slug(name: str, slug: str) -> None:
    if not name.strip():
        fail("empty_name")
    if not SLUG.match(slug):
        fail("invalid_slug", slug=slug, pattern=SLUG.pattern)


def manifest_languages(manifest: dict) -> set[str]:
    codes = set(manifest.get("glossary", {}).get("languages", []))
    return codes.union(*(c["languages"] for c in manifest.get("components", [])))


def cmd_strings(args: argparse.Namespace) -> None:
    out, manifest, source = prepare(args)
    if args.slug == manifest.get("glossary", {}).get("slug"):
        fail("slug_taken", slug=args.slug, by="glossary")
    kit = read_kit(Path(args.kit), source)
    zip_name, explanations_name = f"{args.slug}.zip", f"{args.slug}.explanations.json"
    write_zip(out / zip_name, {f"{code}.po": render_po(kit, code, source) for code in kit["languages"]})
    (out / explanations_name).write_text(json.dumps(kit["explanations"], ensure_ascii=False, indent=1) + "\n",
                                         encoding="utf-8")
    problems = verify_strings(kit, source, out / zip_name, out / explanations_name)
    if problems:
        fail("parse_back_mismatch", count=len(problems), problems=problems[:EXAMPLES])
    entry = {"name": args.name, "slug": args.slug, "zip": zip_name, "explanations": explanations_name,
             "units": len(kit["units"]), "languages": kit["languages"],
             "notes": sum(1 for u in kit["units"] if u["notes"]), "input": str(Path(args.kit).resolve())}
    manifest["components"] = [c for c in manifest.get("components", []) if c["slug"] != args.slug] + [entry]
    save_manifest(out, manifest)
    emit({"component": entry, "source_language": source, "blank_rows_skipped": kit["blank_rows"],
          "explanations": len(kit["explanations"]), "warnings": kit["warnings"]})


def cmd_glossary(args: argparse.Namespace) -> None:
    out, manifest, source = prepare(args)
    if any(c["slug"] == args.slug for c in manifest.get("components", [])):
        fail("slug_taken", slug=args.slug, by="strings component")
    glossary = read_glossary(Path(args.csv), source)
    zip_name = f"{args.slug}.zip"
    write_zip(out / zip_name, {f"tbx/{code}.tbx": render_tbx(glossary, code, source) for code in glossary["targets"]})
    problems = verify_glossary(glossary, source, out / zip_name)
    if problems:
        fail("parse_back_mismatch", count=len(problems), problems=problems[:EXAMPLES])
    manifest["glossary"] = {"name": args.name, "slug": args.slug, "zip": zip_name, "terms": len(glossary["terms"]),
                            "languages": glossary["languages"], "input": str(Path(args.csv).resolve())}
    save_manifest(out, manifest)
    emit({"glossary": manifest["glossary"], "source_language": source,
          "flagged_terms": sum(1 for t in glossary["terms"] if t["flags"]), "warnings": glossary["warnings"]})


def cmd_project(args: argparse.Namespace) -> None:
    out = Path(args.out)
    manifest = load_manifest(out)
    check_name_slug(args.name, args.slug)
    manifest["project"] = {"name": args.name.strip(), "slug": args.slug}
    save_manifest(out, manifest)
    emit({"project": manifest["project"]})


def cmd_machinery(args: argparse.Namespace) -> None:
    out = Path(args.out)
    manifest = load_manifest(out)
    try:
        data = json.loads(Path(args.file).read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        fail("invalid_json", path=args.file, detail=str(exc))
    if isinstance(data, dict) and "configuration" in data:
        if data.get("service", "openrouter") != "openrouter":
            fail("unsupported_service", service=data.get("service"), supported="openrouter")
        data = data["configuration"]
    if not isinstance(data, dict):
        fail("not_an_object", path=args.file)
    # Key, base URL and routing are inherited from the global configuration and never belong in a file.
    extra = sorted(set(data) - {"persona", "style", "language_instructions"})
    if extra:
        fail("unexpected_fields", fields=extra, allowed=["persona", "style", "language_instructions"])
    for field in ("persona", "style"):
        if not isinstance(data.get(field, ""), str):
            fail("field_not_string", field=field)
    instructions = data.get("language_instructions") or {}
    if not isinstance(instructions, dict) or not all(isinstance(v, str) for v in instructions.values()):
        fail("language_instructions_not_object", hint='{"de": "text", ...}')
    too_long = {code: len(text.strip()) for code, text in instructions.items()
                if len(text.strip()) > INSTRUCTION_LIMIT}
    if too_long:
        fail("instruction_too_long", limit=INSTRUCTION_LIMIT, languages=too_long)
    unknown = [code for code in instructions if (language_code(code) or code) not in manifest_languages(manifest)]
    config = {"persona": data.get("persona", "").strip(), "style": data.get("style", "").strip(),
              "language_instructions": {code: text.strip() for code, text in instructions.items() if text.strip()}}
    manifest["machinery"] = {"service": "openrouter", "configuration": config}
    save_manifest(out, manifest)
    emit({"machinery": manifest["machinery"], "warnings": {"languages_not_in_manifest": unknown} if unknown else {}})


def cmd_check(args: argparse.Namespace) -> None:
    out = Path(args.dir)
    manifest = load_manifest(out)
    if not manifest:
        fail("manifest_missing", dir=str(out))
    source = manifest.get("source_language", "")
    problems: list[str] = []
    if "project" not in manifest:
        problems.append("project is not recorded; run the project command")
    if not manifest.get("components") and "glossary" not in manifest:
        problems.append("no strings component and no glossary recorded")
    # read_kit/read_glossary re-validate the input and guarantee the source column; the verifiers
    # guarantee a file per language, the source one included.
    for entry in manifest.get("components", []):
        paths = [Path(entry["input"]), out / entry["zip"], out / entry["explanations"]]
        missing = [str(p) for p in paths if not p.is_file()]
        found = [f"missing {missing}"] if missing else verify_strings(read_kit(paths[0], source), source, *paths[1:])
        problems += [f"component {entry['slug']}: {p}" for p in found]
    glossary = manifest.get("glossary")
    if glossary:
        paths = [Path(glossary["input"]), out / glossary["zip"]]
        missing = [str(p) for p in paths if not p.is_file()]
        found = ([f"missing {missing}"] if missing
                 else verify_glossary(read_glossary(paths[0], source), source, paths[1]))
        problems += [f"glossary: {p}" for p in found]
    if problems:
        fail("check_failed", count=len(problems), problems=problems[:EXAMPLES * 2])
    info: dict = {}
    if glossary:
        used = {code for c in manifest.get("components", []) for code in c["languages"]}
        info["languages_missing_from_glossary"] = sorted(used - set(glossary["languages"]))
    instructions = manifest.get("machinery", {}).get("configuration", {}).get("language_instructions", {})
    unknown = [code for code in instructions if (language_code(code) or code) not in manifest_languages(manifest)]
    if unknown:
        info["machinery_languages_not_in_manifest"] = unknown
    emit({"ready": True, "manifest": manifest, "info": info})


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = parser.add_subparsers(dest="command", required=True)
    for name, positional, func, default in (("strings", "kit", cmd_strings, "Strings"),
                                            ("glossary", "csv", cmd_glossary, "Glossary")):
        command = sub.add_parser(name, help=f"{name} CSV -> upload ZIP")
        command.add_argument(positional)
        command.add_argument("--source-lang", required=True)
        command.add_argument("--out", required=True)
        command.add_argument("--name", default=default)
        command.add_argument("--slug", default=default.lower())
        command.set_defaults(func=func)
    project = sub.add_parser("project", help="record the project name and slug")
    project.add_argument("--name", required=True)
    project.add_argument("--slug", required=True)
    project.add_argument("--out", required=True)
    project.set_defaults(func=cmd_project)
    machinery = sub.add_parser("machinery", help="validate and record the suggestion prompts")
    machinery.add_argument("file")
    machinery.add_argument("--out", required=True)
    machinery.set_defaults(func=cmd_machinery)
    check = sub.add_parser("check", help="parse everything back and cross-check")
    check.add_argument("dir")
    check.set_defaults(func=cmd_check)
    args = parser.parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
