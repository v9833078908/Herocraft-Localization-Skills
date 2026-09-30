#!/usr/bin/env python3
"""Inventory a localization pack before deciding anything about it.

Standard library only, so it runs on any machine with Python 3.9+.

  inspect_inputs.py PATH [PATH...] [--export-dir DIR] [--max-samples N]

Walks folders and ZIP archives and prints one JSON document of facts, never
decisions: the kind of every file, text encoding evidence, table delimiters,
a profile of every table column (fill, uniqueness, scripts, the language its
header names, placeholders and markup, how often it repeats each language
column), document headings, and groups of near-identical text files such as
per-language copies of one prompt.

--export-dir writes every table sheet as UTF-8 CSV and every DOCX as plain
text, and extracts ZIP members, so later steps never need openpyxl.

Exit code 2 with a JSON "error" object means a path given on the command line
does not exist; an unreadable file is reported inside the inventory instead.
"""

from __future__ import annotations

import argparse
import codecs
import csv
import io
import json
import os
import posixpath
import re
import struct
import sys
import unicodedata
import zipfile
from collections import Counter
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from pathlib import Path
from typing import NoReturn
from xml.etree import ElementTree

CAP = 200 * 1024 * 1024  # uncompressed bytes read from one file or one archive
SAMPLE_LEN = 80
TEXT_EXT = {".txt", ".text", ".md", ".markdown", ".rst"}
XML_EXT = {".xliff", ".xlf", ".tmx", ".tbx", ".xml", ".resx"}
STRUCTURED_EXT = XML_EXT | {".json", ".arb", ".po", ".pot", ".yaml", ".yml", ".strings", ".properties", ".ini"}
IMAGE_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".bmp", ".tga", ".psd", ".svg"}
KIND_BY_EXT = {**dict.fromkeys((".csv", ".tsv", ".xlsx", ".xlsm"), "table"), **dict.fromkeys(TEXT_EXT, "text"),
               **dict.fromkeys(STRUCTURED_EXT, "structured"), **dict.fromkeys(IMAGE_EXT, "image"),
               ".pdf": "pdf", ".docx": "docx", ".zip": "archive"}
JUNK = {".DS_Store": "os_metadata", "Thumbs.db": "os_metadata", "desktop.ini": "os_metadata", "__MACOSX": "os_metadata"}

# A language code, then its names as they appear in headers: English, native, Russian.
LANGUAGES = """
en english английский; ru russian русский; de german deutsch немецкий; fr french français французский;
es spanish español испанский;
es_419 spanishlatam latamspanish spanishlatinamerica latinamericanspanish spanishmexico испанскийлатам;
it italian italiano итальянский; pt portuguese português португальский;
pt_BR portuguesebrazil portuguesebrazilian brazilianportuguese portuguesebr brazilian
      бразильскийпортугальский португальскийбразилия;
pt_PT portugueseportugal europeanportuguese; pl polish polski польский; tr turkish türkçe турецкий;
uk ukrainian українська украинский; be belarusian белорусский; kk kazakh казахский; cs czech čeština чешский;
sk slovak словацкий; hu hungarian magyar венгерский; ro romanian română румынский; bg bulgarian болгарский;
sr serbian сербский; hr croatian хорватский; el greek ελληνικά греческий;
nl dutch nederlands нидерландский голландский; sv swedish svenska шведский; nb norwegian norsk норвежский;
da danish dansk датский; fi finnish suomi финский; et estonian эстонский; lv latvian латышский;
lt lithuanian литовский; he hebrew עברית иврит; ar arabic العربية арабский; fa persian farsi فارسی персидский;
hi hindi हिन्दी хинди; bn bengali бенгальский; th thai ไทย тайский; vi vietnamese tiếngviệt вьетнамский;
id indonesian bahasaindonesia индонезийский; ms malay bahasamelayu малайский; fil filipino tagalog филиппинский;
ja japanese 日本語 японский; ko korean 한국어 корейский; zh chinese 中文 китайский;
zh_Hans chinesesimplified simplifiedchinese 简体中文 китайскийупрощенный упрощенныйкитайский;
zh_Hant chinesetraditional traditionalchinese 繁體中文 китайскийтрадиционный традиционныйкитайский;
ka georgian грузинский; hy armenian армянский; az azerbaijani азербайджанский; uz uzbek узбекский
"""


def norm_name(text: str) -> str:
    return re.sub(r"[\W\d_]+", "", unicodedata.normalize("NFC", text).casefold()).replace("ё", "е")


NAME_TO_CODE: dict[str, str] = {}
MENTION: dict[str, re.Pattern] = {}
for _entry in LANGUAGES.split(";"):
    _code, *_names = _entry.split()
    NAME_TO_CODE.update((norm_name(n), _code) for n in _names)
    # Russian adjectives are inflected in prose ("на русском"), so they match by stem.
    MENTION[_code] = re.compile("|".join([rf"\b{n}\b" for n in _names if n.isascii()]
                                         + [rf"\b{n[:-2]}\w*" for n in _names if re.fullmatch(r"[а-я]+(ий|ый)", n)]),
                                re.IGNORECASE)
KNOWN_BASES = {c.split("_")[0] for c in MENTION}
CODE = re.compile(r"^([A-Za-z]{2,3})(?:[_-]([A-Za-z]{4}|[A-Za-z]{2}|\d{3}))?$")
PAREN_CODE = re.compile(r"\(([A-Za-z]{2,3}(?:[_-][A-Za-z0-9]{2,4})?)\)")
EXPECTED_SCRIPT = {"zh": {"CJK"}, "ja": {"Kana", "CJK"}, "ko": {"Hangul"}, "ar": {"Arabic"}, "fa": {"Arabic"},
                   "th": {"Thai"}, "sr": {"Cyrillic", "Latin"},
                   **dict.fromkeys(("ru", "uk", "be", "kk", "bg"), {"Cyrillic"}),
                   **dict.fromkeys(("el", "he", "hi", "bn", "ka", "hy"), {"other"})}

SCRIPTS = {
    "Latin": re.compile(r"[A-Za-z\u00c0-\u024f\u1e00-\u1eff]"),
    "Cyrillic": re.compile(r"[\u0400-\u04ff]"),
    "CJK": re.compile(r"[\u3400-\u4dbf\u4e00-\u9fff\uf900-\ufaff]"),
    "Hangul": re.compile(r"[\uac00-\ud7af\u1100-\u11ff\u3130-\u318f]"),
    "Kana": re.compile(r"[\u3040-\u30ff\u31f0-\u31ff\uff66-\uff9f]"),
    "Arabic": re.compile(r"[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]"),
    "Thai": re.compile(r"[\u0e00-\u0e7f]"),
}
LETTER = re.compile(r"[^\W\d_]")
ASCII_LETTER = re.compile(r"[A-Za-z]")
# Characters written differently in Simplified and Traditional Chinese, paired by position.
HANS = set("这们说对时会为国过还没么经发样问开关门见长东车书无动电话让个击级战队奖务获胜败宝买卖币敌选择领启设语")
HANT = set("這們說對時會為國過還沒麼經發樣問開關門見長東車書無動電話讓個擊級戰隊獎務獲勝敗寶買賣幣敵選擇領啟設語")

PRINTF = re.compile(r"%(?:\d+\$)?[-+0#]*\d*(?:\.\d+)?[sdifuxXeEgGc@]")
TOKENS = {
    "{0}": re.compile(r"\{\d+[^{}]*\}"),
    "{name}": re.compile(r"\{[A-Za-z_][^{}]*\}"),
    "[0]": re.compile(r"\[\d+\]"),
    "%s": PRINTF,
    "%KEY%": re.compile(r"%[A-Za-z_][A-Za-z0-9_]*%"),
    "\\n": re.compile(r"\\n"),
    "newline": re.compile(r"\n"),
}
TAG = re.compile(r"</?([A-Za-z][\w-]*)[^<>]*>")
ANY_TOKEN = re.compile("|".join(TOKENS[k].pattern for k in ("{0}", "{name}", "[0]", "%s", "%KEY%")))
IDENT = re.compile(r"^[A-Za-z0-9_.\-/:\[\]]+$")
NUMERIC = re.compile(r"^[+-]?\d+(?:[.,]\d+)?$")
WELL_QUOTED = re.compile(r'^"(?:[^"]|"")*"$')

M = "{http://schemas.openxmlformats.org/spreadsheetml/2006/main}"
W = "{http://schemas.openxmlformats.org/wordprocessingml/2006/main}"
R_ID = "{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id"
XL_ESCAPE = re.compile(r"_x([0-9A-Fa-f]{4})_")
BOMS = ((codecs.BOM_UTF32_LE, "utf-32-le"), (codecs.BOM_UTF32_BE, "utf-32-be"), (codecs.BOM_UTF8, "utf-8"),
        (codecs.BOM_UTF16_LE, "utf-16-le"), (codecs.BOM_UTF16_BE, "utf-16-be"))


def dump(obj, depth: int = 0) -> str:
    """Pretty JSON that packs short values onto shared lines, so a wide sheet stays readable."""
    flat = json.dumps(obj, ensure_ascii=False)
    if len(flat) <= 120 or not isinstance(obj, (dict, list)):
        return flat
    pad = "  " * (depth + 1)
    items = ([f"{json.dumps(k, ensure_ascii=False)}: {dump(v, depth + 1)}" for k, v in obj.items()]
             if isinstance(obj, dict) else [dump(v, depth + 1) for v in obj])
    lines: list[str] = []
    for item in items:
        if lines and "\n" not in item + lines[-1] and len(pad + lines[-1] + item) + 2 <= 120:
            lines[-1] += ", " + item
        else:
            lines.append(item)
    brackets = "{}" if isinstance(obj, dict) else "[]"
    return brackets[0] + "\n" + ",\n".join(pad + line for line in lines) + "\n" + "  " * depth + brackets[1]


def fail(code: str, **details) -> NoReturn:
    print(json.dumps({"error": code, **details}, ensure_ascii=False, indent=2))
    sys.exit(2)


def ratio(part: int, whole: int) -> float:
    return round(part / whole, 3) if whole else 0.0


def clip(text: str, limit: int = SAMPLE_LEN) -> str:
    return text if len(text) <= limit else text[: limit - 3] + "..."


def letter(index: int) -> str:
    name, index = "", index + 1
    while index:
        index, rem = divmod(index - 1, 26)
        name = chr(65 + rem) + name
    return name


def ranges(numbers: list[int]) -> str:
    spans: list[list[int]] = []
    for n in numbers:
        if spans and n == spans[-1][1] + 1:
            spans[-1][1] = n
        else:
            spans.append([n, n])
    return ",".join(f"{a}-{b}" if a != b else str(a) for a, b in spans)


def local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1]


def junk_reason(name: str) -> str | None:
    if name in JUNK:
        return JUNK[name]
    if name.startswith("~$"):
        return "office_lock_file"
    return "hidden" if name.startswith(".") else None


# --- language and script -----------------------------------------------------


def as_code(text: str) -> str | None:
    m = CODE.match(text.strip())
    if not m or m.group(1).lower() not in KNOWN_BASES or text.strip().lower() == "id":
        return None
    base, sub = m.group(1).lower(), m.group(2)
    if not sub:
        return base
    return f"{base}_{sub.title() if len(sub) == 4 else sub.upper()}"


def language_of(header: str) -> tuple[str, str] | None:
    for candidate in (header, *PAREN_CODE.findall(header)):
        code = as_code(candidate)
        if code:
            return code, "header_code"
    for candidate in (header, re.sub(r"\(.*?\)", "", header)):
        code = NAME_TO_CODE.get(norm_name(candidate))
        if code:
            return code, "header_name"
    return None


def script_counts(text: str) -> dict[str, int]:
    if text.isascii():
        n = len(ASCII_LETTER.findall(text))
        return {"Latin": n} if n else {}
    counts = {name: len(rx.findall(text)) for name, rx in SCRIPTS.items()}
    counts["other"] = len(LETTER.findall(text)) - sum(counts.values())
    return {k: v for k, v in counts.items() if v > 0}


def dominant_script(value: str) -> str:
    counts = script_counts(TAG.sub(" ", ANY_TOKEN.sub(" ", value)))
    return max(counts, key=counts.get) if counts else "none"


# --- decoding ----------------------------------------------------------------


def decode(data: bytes) -> tuple[str | None, dict]:
    for bom, codec in BOMS:
        if data.startswith(bom):
            try:
                return data[len(bom):].decode(codec), {"bom": codec, "encoding": codec}
            except UnicodeDecodeError as e:
                return None, {"bom": codec, "decoded": False, "error": str(e)}
    head = data[:4096]
    if b"\x00" in head:
        odd, even = head[1::2].count(0), head[0::2].count(0)
        codec = "utf-16-le" if odd > even else "utf-16-be"
        if max(odd, even) > len(head) // 4:
            try:
                return data.decode(codec), {"bom": None, "encoding": codec, "note": "UTF-16 without BOM"}
            except UnicodeDecodeError:
                pass
        return None, {"bom": None, "decoded": False, "error": "NUL bytes: binary data"}
    try:
        return data.decode("utf-8"), {"bom": None, "encoding": "utf-8"}
    except UnicodeDecodeError as e:
        trials = {}
        for codec in ("cp1251", "cp1252"):
            try:
                trials[codec] = script_counts(data.decode(codec))
            except UnicodeDecodeError:
                trials[codec] = "undecodable"
        return None, {"bom": None, "decoded": False,
                      "error": f"not UTF-8: byte 0x{data[e.start]:02x} at offset {e.start}",
                      "legacy_trials_letters_by_script": trials}


# --- containers --------------------------------------------------------------


def open_zip(data: bytes) -> zipfile.ZipFile:
    z = zipfile.ZipFile(io.BytesIO(data))
    total = sum(i.file_size for i in z.infolist())
    if total > CAP:
        raise ValueError(f"declares {total} uncompressed bytes, over the {CAP}-byte cap")
    return z


def parse_xml(data: bytes) -> ElementTree.Element:
    if b"<!DOCTYPE" in data or b"<!ENTITY" in data:
        raise ValueError("XML with DOCTYPE or ENTITY declarations is not parsed")
    return ElementTree.fromstring(data)


def rich_text(el: ElementTree.Element) -> str:
    # Direct <t> and <r><t> runs only: <rPh> phonetic guides are not cell text.
    parts = []
    for child in el:
        if child.tag == M + "t":
            parts.append(child.text or "")
        elif child.tag == M + "r":
            parts.extend(t.text or "" for t in child.findall(M + "t"))
    return XL_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), "".join(parts))


def number_text(raw: str) -> str:
    try:
        d = Decimal(raw)
    except InvalidOperation:
        return raw
    return format(d.to_integral_value(), "f") if d.is_finite() and d == d.to_integral_value() else raw


def col_number(ref: str) -> int:
    n = 0
    for ch in re.match(r"[A-Z]*", ref).group(0):
        n = n * 26 + ord(ch) - 64
    return n


def read_xlsx(data: bytes) -> list[dict]:
    with open_zip(data) as z:
        names = set(z.namelist())
        rels = {r.get("Id"): r for r in parse_xml(z.read("xl/_rels/workbook.xml.rels"))}

        def part(target: str) -> str:
            return target.lstrip("/") if target.startswith("/") else posixpath.normpath("xl/" + target)

        shared: list[str] = []
        ss = next((part(r.get("Target")) for r in rels.values() if r.get("Type", "").endswith("/sharedStrings")), None)
        if ss in names:
            shared = [rich_text(si) for si in parse_xml(z.read(ss)).findall(M + "si")]
        sheets = []
        for sheet in parse_xml(z.read("xl/workbook.xml")).iter(M + "sheet"):
            member = part(rels[sheet.get(R_ID)].get("Target"))
            rows: list[list[str]] = []
            formulas, uncached = 0, []
            root = parse_xml(z.read(member)) if member in names else None
            for row in root.iter(M + "row") if root is not None else ():
                r = int(row.get("r", len(rows) + 1))
                while len(rows) < r - 1:
                    rows.append([])
                cells: dict[int, str] = {}
                col = 0
                for c in row.findall(M + "c"):
                    col = col_number(c.get("r")) if c.get("r") else col + 1
                    kind, f, v = c.get("t", "n"), c.find(M + "f"), c.find(M + "v")
                    if f is not None:
                        formulas += 1
                        if v is None or (v.text is None and kind != "str"):
                            uncached.append(f"{letter(col - 1)}{r}")
                    if kind == "inlineStr":
                        inline = c.find(M + "is")
                        value = rich_text(inline) if inline is not None else ""
                    elif v is None or v.text is None:
                        value = ""
                    elif kind == "s":
                        value = shared[int(v.text)]
                    elif kind == "b":
                        value = "TRUE" if v.text == "1" else "FALSE"
                    elif kind == "n":
                        value = number_text(v.text)
                    else:
                        value = XL_ESCAPE.sub(lambda m: chr(int(m.group(1), 16)), v.text)
                    cells[col - 1] = value
                rows.append([cells.get(i, "") for i in range(max(cells) + 1)] if cells else [])
            sheets.append({"name": sheet.get("name"), "hidden": sheet.get("state") in ("hidden", "veryHidden"),
                           "rows": rows, "formulas": formulas, "uncached": uncached})
    return sheets


def docx_text(data: bytes) -> tuple[str, list[str]]:
    with open_zip(data) as z:
        root = parse_xml(z.read("word/document.xml"))
    paragraphs, headings = [], []
    for p in root.iter(W + "p"):
        parts = []
        for el in p.iter():
            if el.tag == W + "t":
                parts.append(el.text or "")
            elif el.tag == W + "tab":
                parts.append("\t")
            elif el.tag in (W + "br", W + "cr"):
                parts.append("\n")
        text = "".join(parts)
        style = p.find(f"{W}pPr/{W}pStyle")
        if style is not None and re.match(r"(Heading|Title)", style.get(W + "val", "")) and text.strip():
            headings.append(clip(text.strip(), 100))
        paragraphs.append(text)
    return "\n".join(paragraphs), headings


def image_size(data: bytes) -> tuple[int, int] | None:
    if data[:8] == b"\x89PNG\r\n\x1a\n" and data[12:16] == b"IHDR":
        return struct.unpack(">II", data[16:24])
    if data[:6] in (b"GIF87a", b"GIF89a"):
        return struct.unpack("<HH", data[6:10])
    if data[:2] == b"\xff\xd8":
        i = 2
        while i + 9 < len(data) and data[i] == 0xFF:
            marker = data[i + 1]
            if marker == 0xFF or 0xD0 <= marker <= 0xD8 or marker == 0x01:
                i += 1 if marker == 0xFF else 2
                continue
            if 0xC0 <= marker <= 0xCF and marker not in (0xC4, 0xC8, 0xCC):
                height, width = struct.unpack(">HH", data[i + 5 : i + 9])
                return width, height
            i += 2 + struct.unpack(">H", data[i + 2 : i + 4])[0]
    return None


# --- tables ------------------------------------------------------------------


def sniff_table(text: str) -> tuple[list[dict], dict | None, list[list[str]]]:
    """Every delimiter present, read with and without quote handling; the most consistent reading wins.

    On a tie, quote handling is used only if no cell opens with a quote it cannot close: the csv module
    would silently drop such quote characters, while a literal reading keeps the text exact.
    """
    candidates, best, best_rows, best_key = [], None, [], None
    for delimiter in [d for d in "\t;,|" if d in text] or [","]:
        entry: dict = {"delimiter": delimiter}
        stray = 0
        for quoting, mode in (("quote_none", csv.QUOTE_NONE), ("quoted", csv.QUOTE_MINIMAL)):
            try:
                rows = list(csv.reader(io.StringIO(text, newline=""), delimiter=delimiter, quoting=mode))
            except csv.Error as e:
                entry[quoting] = {"error": str(e)}
                continue
            if quoting == "quote_none":
                stray = sum(1 for r in rows for c in r if c.startswith('"') and not WELL_QUOTED.match(c))
                entry["cells_opening_with_stray_quote"] = stray
            widths = Counter(len(r) for r in rows if any(c.strip() for c in r))
            total = sum(widths.values())
            modal, count = widths.most_common(1)[0] if widths else (0, 0)
            entry[quoting] = {"rows": total, "modal_width": modal, "consistent": ratio(count, total),
                              "widths": {str(w): c for w, c in widths.most_common(5)}}
            key = (modal >= 2, ratio(count, total), modal, (quoting == "quoted") == (stray == 0))
            if best_key is None or key > best_key:
                best_key, best_rows = key, rows
                best = {"delimiter": delimiter, "quoting": quoting, "rows": total, "modal_width": modal,
                        "consistent": ratio(count, total)}
        candidates.append(entry)
    return candidates, best, best_rows


def pick_samples(values: list[str], k: int) -> list[str]:
    if k <= 0 or not values:
        return []
    if len(values) <= k:
        return [clip(v) for v in values]
    return [clip(values[i]) for i in sorted({round(i * (len(values) - 1) / max(k - 1, 1)) for i in range(k)})]


def token_counts(values: list[str]) -> dict[str, int]:
    counts: Counter = Counter()
    for v in values:
        counts.update(name for name, rx in TOKENS.items() if rx.search(v))
        if "$" in PRINTF.sub("", v):
            counts["$"] += 1
        counts.update({f"<{t.lower()}>" for t in TAG.findall(v)})
    return dict(counts.most_common(12))


def profile_column(index: int, header: str, values: list[str], samples: int) -> dict:
    filled = [v for v in values if v.strip()]
    n = len(filled)
    col = {"col": letter(index), "header": header, "filled": n, "fill": ratio(n, len(values))}
    lang = language_of(header) if header else None
    if n:
        distinct = len(set(filled))
        col.update(distinct_ratio=ratio(distinct, n), unique=distinct == n,
                   len_mean=round(sum(map(len, filled)) / n, 1), len_max=max(map(len, filled)),
                   identifier_like=ratio(sum(bool(IDENT.match(v.strip())) for v in filled), n),
                   numeric=ratio(sum(bool(NUMERIC.match(v.strip())) for v in filled), n))
        scripts = Counter(dominant_script(v) for v in filled)
        col["scripts"] = dict(scripts.most_common())
        if scripts.most_common(1)[0][0] == "CJK":
            han = "".join(filled)
            col["han_chars"] = {"simplified_only": sum(ch in HANS for ch in han),
                                "traditional_only": sum(ch in HANT for ch in han)}
        tokens = token_counts(filled)
        if tokens:
            col["tokens_in_values"] = tokens
    if lang:
        expected = EXPECTED_SCRIPT.get(lang[0].split("_")[0], {"Latin"})
        lettered = {k: v for k, v in col.get("scripts", {}).items() if k != "none"}
        col["language"] = {"code": lang[0], "basis": lang[1], "expected_script": sorted(expected),
                           "script_agrees": bool(lettered) and max(lettered, key=lettered.get) in expected,
                           "expected_script_share": ratio(sum(v for k, v in lettered.items() if k in expected),
                                                          sum(lettered.values()))}
    col["samples"] = pick_samples(filled, samples)
    return col


def similarity(raw: list[str], other_raw: list[str], norm: list[str], other_norm: list[str]) -> dict[str, int]:
    """Rows where both cells are filled: identical, identical ignoring case and spacing, difflib ratio >= 0.8."""
    counts = dict.fromkeys(("compared", "exact", "ignoring_case_space", "similar"), 0)
    for x, y, a, b in zip(raw, other_raw, norm, other_norm):
        if not a or not b:
            continue
        counts["compared"] += 1
        counts["exact"] += x == y
        if a == b:
            counts["ignoring_case_space"] += 1
            counts["similar"] += 1
        elif 2 * min(len(a), len(b)) / (len(a) + len(b)) >= 0.8:
            sm = SequenceMatcher(None, a, b)
            counts["similar"] += sm.quick_ratio() >= 0.8 and sm.ratio() >= 0.8
    return counts


def profile_table(rows: list[list[str]], samples: int) -> dict:
    filled_rows = [i for i, r in enumerate(rows) if any(c.strip() for c in r)]
    info: dict = {"rows": len(rows)}
    if not filled_rows:
        info["empty"] = True
        return info
    head, last = filled_rows[0], filled_rows[-1]
    stored_width = max(len(r) for r in rows)
    used = max(j for r in rows for j, c in enumerate(r) if c.strip()) + 1
    header, data = rows[head], rows[head + 1 : last + 1]
    info.update(header_row=head + 1, data_rows=len(data), empty_rows_inside=len(data) - len(filled_rows) + 1,
                trailing_empty_rows=len(rows) - last - 1, columns=used, trailing_empty_columns=stored_width - used)
    columns, raws, norms, empty = [], {}, {}, []
    for j in range(used):
        name = header[j].strip() if j < len(header) else ""
        values = [r[j] if j < len(r) else "" for r in data]
        if not name and not any(v.strip() for v in values):
            empty.append(letter(j))
            continue
        columns.append(profile_column(j, name, values, samples))
        raws[letter(j)] = values
        norms[letter(j)] = [" ".join(v.casefold().split())[:300] for v in values]
    language_cols = [c for c in columns if "language" in c and c["filled"]]
    for c in columns:
        if "language" in c or not c["filled"] or not language_cols:
            continue
        sims = [{"col": lc["col"], "header": lc["header"],
                 **similarity(raws[c["col"]], raws[lc["col"]], norms[c["col"]], norms[lc["col"]])}
                for lc in language_cols]
        sims.sort(key=lambda s: (ratio(s["similar"], s["compared"]), s["similar"]), reverse=True)
        c["similar_to_language_columns"] = sims[:3]
    if empty:
        info["empty_columns_inside"] = empty
    info["column_profiles"] = columns
    return info


# --- documents ---------------------------------------------------------------


def text_doc(text: str, ext: str) -> dict:
    lines = text.splitlines()
    info: dict = {"lines": len(lines), "chars": len(text)}
    if ext in (".md", ".markdown"):
        headings, fence = [], False
        for line in lines:
            if line.lstrip().startswith(("```", "~~~")):
                fence = not fence
            elif not fence and re.match(r"#{1,6}\s", line):
                headings.append(clip(line.strip(), 100))
        info["headings"] = headings[:40]
        if len(headings) > 40:
            info["headings_total"] = len(headings)
        info["md_table_lines"] = sum(1 for line in lines if line.lstrip().startswith("|"))
    letters = script_counts(text)
    shares = {k: ratio(v, sum(letters.values())) for k, v in sorted(letters.items(), key=lambda kv: -kv[1])}
    info["script_share"] = {k: v for k, v in shares.items() if v}
    mentions = {code: len(rx.findall(text)) for code, rx in MENTION.items()}
    info["language_mentions"] = {k: v for k, v in sorted(mentions.items(), key=lambda kv: -kv[1]) if v}
    return info


def similar_groups(docs: list[tuple[str, list[str]]]) -> list[dict]:
    keyed = [[line.strip() for line in lines if line.strip()] for _, lines in docs]
    parent = list(range(len(docs)))

    def find(i: int) -> int:
        while parent[i] != i:
            i = parent[i]
        return i

    for i in range(len(docs)):
        for j in range(i + 1, len(docs)):
            a, b = keyed[i], keyed[j]
            if not a or not b or min(len(a), len(b)) / max(len(a), len(b)) < 0.7:
                continue
            sm = SequenceMatcher(None, a, b, autojunk=False)
            if sm.quick_ratio() >= 0.7 and sm.ratio() >= 0.7:
                parent[find(j)] = find(i)
    members: dict[int, list[int]] = {}
    for i in range(len(docs)):
        members.setdefault(find(i), []).append(i)
    groups = []
    for idx in (m for m in members.values() if len(m) > 1):
        common = set.intersection(*(set(keyed[i]) for i in idx))
        files = []
        for i in idx:
            path, lines = docs[i]
            differing = [k + 1 for k, line in enumerate(lines) if line.strip() and line.strip() not in common]
            files.append({"path": path, "differing_lines": ranges(differing), "differing_count": len(differing),
                          "first_differing": [clip(lines[k - 1].strip(), 100) for k in differing[:4]]})
        shares = [sum(1 for line in keyed[i] if line in common) / len(keyed[i]) for i in idx]
        groups.append({"files": len(idx), "shared_lines": len(common),
                       "shared_line_ratio": round(sum(shares) / len(shares), 3), "members": files})
    return groups


def structured(ext: str, text: str, data: bytes) -> dict:
    if ext in (".json", ".arb"):
        try:
            obj = json.loads(text)
        except ValueError as e:
            return {"parse_error": str(e)}
        strings, depth, stack = 0, 0, [(obj, 1)]
        while stack:
            node, d = stack.pop()
            depth = max(depth, d)
            if isinstance(node, dict):
                stack.extend((v, d + 1) for v in node.values())
            elif isinstance(node, list):
                stack.extend((v, d + 1) for v in node)
            elif isinstance(node, str):
                strings += 1
        shape = {"type": {dict: "object", list: "array"}.get(type(obj), type(obj).__name__),
                 "string_leaves": strings, "max_depth": depth}
        if isinstance(obj, dict):
            shape.update(key_count=len(obj), top_keys=list(obj)[:20],
                         language_keys=[k for k in obj if language_of(k)][:30])
        elif isinstance(obj, list):
            keys = {k for item in obj[:50] if isinstance(item, dict) for k in item}
            shape.update(length=len(obj), item_keys=sorted(keys)[:20])
        return shape
    if ext in (".po", ".pot"):
        lang = re.search(r'^"Language: *([^"\\]*)', text, re.M)
        header = 1 if re.search(r'^msgid ""\r?\nmsgstr', text, re.M) else 0
        return {"units": len(re.findall(r"^msgid\s", text, re.M)) - header,
                "plural_units": len(re.findall(r"^msgid_plural\s", text, re.M)),
                "with_context": len(re.findall(r"^msgctxt\s", text, re.M)),
                "fuzzy": len(re.findall(r"^#,.*\bfuzzy", text, re.M)),
                "language": lang.group(1).strip() if lang else None}
    if ext in XML_EXT:
        if re.search(r"<!(DOCTYPE|ENTITY)", text):
            return {"rejected": "DOCTYPE or ENTITY declaration; not parsed"}
        root = parse_xml(data)
        tags = Counter(local(el.tag) for el in root.iter())
        langs = {v for el in root.iter() for k, v in el.attrib.items()
                 if local(k) in ("source-language", "target-language", "srcLang", "trgLang", "srclang", "lang")}
        units = sum(tags[t] for t in ("trans-unit", "unit", "tu", "termEntry", "string", "plurals", "string-array",
                                      "data"))
        return {"root": local(root.tag), "units": units, "languages": sorted(langs)[:20],
                "top_tags": dict(tags.most_common(8))}
    lines = text.count("\n") + 1
    if ext in (".yaml", ".yml"):
        top = [k.strip().strip("'\"") for k in re.findall(r"^([^\s#\-][^:\n]*):", text, re.M)]
        return {"lines": lines, "top_level_keys": top[:20],
                "key_lines": len(re.findall(r"^\s*[^\s#\-][^:\n]*:", text, re.M)),
                "language_keys": [k for k in top if language_of(k)][:30]}
    pairs = re.findall(r'^\s*(?:"(?:[^"\\]|\\.)*"|[^\s=:#!;\[][^=:\n]*?)\s*[=:]', text, re.M)
    return {"lines": lines, "key_value_lines": len(pairs), "sections": len(re.findall(r"^\s*\[[^\]\n]+\]", text, re.M))}


# --- inventory ---------------------------------------------------------------


class Inventory:
    def __init__(self, export_dir: Path | None, samples: int):
        self.export_dir, self.samples = export_dir, samples
        self.files: list[dict] = []
        self.skipped: list[dict] = []
        self.docs: list[tuple[str, list[str]]] = []
        self.used_names: set[str] = set()

    def add_path(self, path: Path) -> None:
        if path.is_file():
            self.add_disk_file(path)
            return
        for root, dirs, names in os.walk(path):
            for d in sorted(dirs):
                if junk_reason(d):
                    self.skipped.append({"path": os.path.join(root, d) + "/", "reason": junk_reason(d)})
                    dirs.remove(d)
            dirs.sort()
            for name in sorted(names):
                if junk_reason(name):
                    self.skipped.append({"path": os.path.join(root, name), "reason": junk_reason(name)})
                else:
                    self.add_disk_file(Path(root) / name)

    def add_disk_file(self, path: Path) -> None:
        size = path.stat().st_size
        if size > CAP:
            self.files.append({"path": str(path), "size": size,
                               "kind": KIND_BY_EXT.get(path.suffix.lower(), "binary-unknown"),
                               "error": f"larger than the {CAP}-byte cap; not read"})
        else:
            self.add(str(path), path.name, path.read_bytes(), [CAP])

    def add(self, display: str, name: str, data: bytes, budget: list[int]) -> None:
        entry = {"path": display, "size": len(data)}
        self.files.append(entry)
        try:
            entry.update(self.inspect(display, name, data, budget))
        except Exception as e:  # a corrupt file is a fact about the pack, not a reason to stop
            entry.setdefault("kind", KIND_BY_EXT.get(posixpath.splitext(name)[1].lower(), "binary-unknown"))
            entry["error"] = f"{type(e).__name__}: {e}"

    def inspect(self, display: str, name: str, data: bytes, budget: list[int]) -> dict:
        stem, ext = posixpath.splitext(name)
        ext = ext.lower()
        if ext in (".xlsx", ".xlsm"):
            sheets = []
            for sheet in read_xlsx(data):
                info = {"sheet": sheet["name"], **({"hidden": True} if sheet["hidden"] else {}),
                        **profile_table(sheet["rows"], self.samples)}
                if sheet["formulas"]:
                    info["formula_cells"] = sheet["formulas"]
                if sheet["uncached"]:
                    info["formulas_without_cached_value"] = {"count": len(sheet["uncached"]),
                                                             "cells": sheet["uncached"][:10]}
                info["exported_to"] = self.export_table(f"{stem}__{sheet['name']}.csv", sheet["rows"])
                sheets.append(info)
            return {"kind": "table", "format": ext[1:], "sheets": sheets}
        if ext == ".zip":
            return self.archive(display, stem, data, budget)
        if ext == ".docx":
            text, headings = docx_text(data)
            self.docs.append((display, text.splitlines()))
            return {"kind": "docx", **text_doc(text, ext), "headings": headings[:40],
                    "exported_to": self.export_text(f"{stem}.txt", text)}
        if ext == ".pdf":
            pages = len(re.findall(rb"/Type\s*/Page(?![A-Za-z])", data))
            return {"kind": "pdf", "pages": pages or None}
        if ext in IMAGE_EXT:
            size = image_size(data)
            return {"kind": "image", "format": ext[1:], **({"width": size[0], "height": size[1]} if size else {})}
        if ext == ".xls":
            return {"kind": "binary-unknown", "note": "Excel 97-2003 .xls; not readable with the standard library"}
        text, encoding = decode(data)
        if ext in STRUCTURED_EXT:
            return {"kind": "structured", "format": ext[1:], "encoding": encoding,
                    **(structured(ext, text, data) if text is not None else {})}
        if text is None:
            return {"kind": KIND_BY_EXT.get(ext, "binary-unknown"), "encoding": encoding}
        if ext not in (".md", ".markdown", ".rst"):
            candidates, best, rows = sniff_table(text)
            forced = ext in (".csv", ".tsv")
            if forced or (best and best["modal_width"] >= 2 and best["consistent"] >= 0.8 and best["rows"] >= 2):
                sheet = {**profile_table(rows, self.samples), "exported_to": self.export_table(f"{stem}.csv", rows)}
                return {"kind": "table", "format": ext[1:] or None, "encoding": encoding,
                        "delimiter": {"chosen": best, "candidates": candidates}, "sheets": [sheet]}
        self.docs.append((display, text.splitlines()))
        return {"kind": "text", "encoding": encoding, **text_doc(text, ext)}

    def archive(self, display: str, stem: str, data: bytes, budget: list[int]) -> dict:
        read = 0
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            members = [i for i in z.infolist() if not i.is_dir()]
            for zi in members:
                path = f"{display}!{zi.filename}"
                parts = zi.filename.replace("\\", "/").split("/")
                reason = next((junk_reason(p) for p in parts if junk_reason(p)), None)
                if zi.filename.startswith(("/", "\\")) or ".." in parts or re.match(r"^[A-Za-z]:", zi.filename):
                    reason = "unsafe_path"
                elif zi.flag_bits & 1:
                    reason = "encrypted"
                elif zi.file_size > budget[0]:
                    reason = f"over the {CAP}-byte cap on uncompressed bytes per archive"
                if reason:
                    self.skipped.append({"path": path, "reason": reason})
                    continue
                budget[0] -= zi.file_size
                read += zi.file_size
                content = z.read(zi)
                if self.export_dir:
                    base = (self.export_dir / stem).resolve()
                    target = (base / "/".join(parts)).resolve()
                    if base in target.parents:
                        target.parent.mkdir(parents=True, exist_ok=True)
                        target.write_bytes(content)
                self.add(path, parts[-1], content, budget)
        return {"kind": "archive", "members": len(members), "uncompressed_bytes_read": read}

    def export_name(self, name: str) -> Path:
        name = re.sub(r'[\\/:*?"<>|\x00-\x1f]', "_", name)
        stem, ext = posixpath.splitext(name)
        n = 1
        while name in self.used_names:
            n += 1
            name = f"{stem}__{n}{ext}"
        self.used_names.add(name)
        self.export_dir.mkdir(parents=True, exist_ok=True)
        return self.export_dir / name

    def export_table(self, name: str, rows: list[list[str]]) -> str | None:
        if not self.export_dir:
            return None
        last = max((i for i, r in enumerate(rows) if any(r)), default=-1)
        if last < 0:
            return None
        kept = rows[: last + 1]
        width = max((j + 1 for r in kept for j, c in enumerate(r) if c), default=0)
        path = self.export_name(name)
        with open(path, "w", encoding="utf-8", newline="") as f:
            csv.writer(f).writerows(r[:width] + [""] * (width - len(r)) for r in kept)
        return str(path)

    def export_text(self, name: str, text: str) -> str | None:
        if not self.export_dir:
            return None
        path = self.export_name(name)
        path.write_text(text, encoding="utf-8")
        return str(path)

    def report(self) -> dict:
        groups = similar_groups(self.docs)
        return {
            "summary": {"files": len(self.files), "by_kind": dict(Counter(f.get("kind") for f in self.files)),
                        "table_sheets": sum(len(f.get("sheets", [])) for f in self.files),
                        "files_with_errors": sum(1 for f in self.files if "error" in f),
                        "skipped": len(self.skipped), "similar_text_groups": len(groups)},
            "files": self.files,
            "groups": groups,
            "skipped": self.skipped,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("paths", nargs="+", help="files or folders of the localization pack")
    parser.add_argument("--export-dir", help="write tables as UTF-8 CSV, DOCX as text, and extract ZIP members here")
    parser.add_argument("--max-samples", type=int, default=3, help="sample values per column (default 3)")
    args = parser.parse_args()
    missing = [p for p in args.paths if not Path(p).exists()]
    if missing:
        fail("path_not_found", paths=missing)
    csv.field_size_limit(2**31 - 1)
    inventory = Inventory(Path(args.export_dir) if args.export_dir else None, args.max_samples)
    for p in args.paths:
        inventory.add_path(Path(p))
    print(dump(inventory.report()))


if __name__ == "__main__":
    main()
