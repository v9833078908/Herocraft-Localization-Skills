---
name: preparing-weblate-loc-kits
description: "Use when converting a game localization kit or string export—CSV, TSV, XLSX, TXT, or custom-delimited text—for import through the HCGameLoc Weblate component-creation interface, or when a game team asks for a string-delivery template."
---

# Preparing Weblate loc kits

## Overview

Convert exports into the HCGameLoc import contract without inventing identities, losing languages, or importing cross-language corruption. Filename extensions are untrusted; `loc_kit_ingest` proves readiness.

## Language and scope

Keep these instructions in English. Conduct the interview, progress notes and the final report in plain Russian. Say “исходный язык”, “переводы”, “пояснение”, “говорящий”; do not expose pipeline jargon. Column headers, language codes and diagnostics stay machine-readable English, and explanation text defaults to the source language.

This skill produces files: an import CSV, a quarantine CSV when something was held back, and a report. It does not create the component, upload anything, translate an empty cell, or run a paid model. Reading `loc_kit_ingest/` and the fork's code to verify a claim is expected; changing a live instance is not.

## Required interview

Before writing the import file, ask the user and record:

1. **Is the source language Russian?** Russian (`ru`) is the default: Hero Craft kits are authored in Russian, so ask for a correction rather than an answer — "Исходный язык — русский, верно?" — and proceed on the default when the user does not object, stating the assumption in the report. The source language is still semantic project metadata: it MUST NOT be *derived* from column order, population, filenames, or apparent text quality, and it must be the first language column because the UI infers it from that position. Leave `ru` only on an explicit statement by the user, or when the kit itself contradicts the default (an empty or clearly machine-translated Russian column beside a fully authored other language); in that case stop and confirm before writing anything.
2. **Which file is the structural reference?** Use it for metadata roles and ordering conventions, not as permission to discard languages absent from it.
3. **What do key, metadata, ID, explanation, and context columns mean?** Ask whether legacy columns must remain and whether their values should be empty. If explanations must be created, confirm their language; default to the source language, not the conversation language. Never invent game identities or usage context.
4. **How should unverifiable duplicate or malformed rows be handled?** Recommend quarantine; never guess translations or IDs.
5. **Which regional variant does an ambiguous language header mean?** `Portugal`, `Chinese` or `Portuguese` does not settle `pt` vs `pt_BR`, or `zh_Hans` vs `zh_Hant`. Mixed wording inside the column ("aplicativos" beside "equipa") is evidence of an uneven translation, not of a locale, so ask instead of scoring vocabulary. State the default you will apply — `pt`, because `loc_kit_ingest/langcode.py` keeps `pt` as Portuguese and a per-project "pt means pt-BR" decision belongs to Weblate's project language aliases — and never relabel a real code because a game usually ships another locale.

Investigate file-provided facts—encoding, delimiter, escaping, sheets, columns, and row widths—with tools rather than asking. Do not generate the final import until the source language is settled—`ru` by default, or a user-stated alternative—and metadata semantics are explicit.

## Target contract

Produce semicolon-delimited UTF-8 CSV with standard quoting:

```text
key;Character;<other metadata columns>;<source-language>;<all target languages>;Explanation
```

Every column of that skeleton is mandatory, in that order. `key` becomes the PO unit identity. `Character` is the canonical speaker column and comes directly after `key`. `Explanation` is always the last column. Emit both **even when the input kit has neither a speaker nor a context column** and every cell you can honestly fill stays empty: an entirely empty non-language column costs nothing — the gate says `column 2 ('Character') is empty and is not a recognised language code; ignored` (`loc_kit_ingest/infer.py`) and the unit count is unchanged — while a missing column forces the producer to change their export schema before context can be delivered at all. Dropping a column because the input had no data for it is the wrong call; filling it with generated values is a worse one.

The reference schema is authoritative for metadata roles and order. Retain every resolved language from the source even when absent from the reference. Put the settled source language first—`ru` unless the user stated another one—then targets in their original input order unless the reference explicitly fixes language order. Empty cells are normal.

A metadata header that resembles a language code is dangerous: `Id` can mean Indonesian. Rename a legacy engine column descriptively, for example `Unity legacy ID`. If its values are intentionally empty, keep them empty; the importer will ignore the column. If an authoritative numeric ID exists, retain it as a location reference. Do not populate an empty legacy column with generated values unless the user explicitly requests that behavior.

For a Russian-source kit containing English, Simplified Chinese, Traditional Chinese, Korean, and Japanese, with a speaker column and an intentionally empty Unity legacy column:

```text
key;Character;Unity legacy ID;ru;en;zh-Hans;zh-Hant;ko;ja;Explanation
```

Use codes recognized by `loc_kit_ingest/langcode.py`; bare `zh` is not recognized here, so distinguish `zh-Hans` and `zh-Hant`. Unknown translations and absent explanations stay empty.

### Header cells carry codes, not language names

`loc_kit_ingest/langcode.py` recognizes a bare code (`ja`, `zh-Hans`, `pt-BR`) or a name with the code in parentheses (`Japanese(ja)`, `Portuguese (pt-BR)`, `Indonesian(id)`). A spelled-out name resolves to nothing: `English`, `Russian`, `German` and `Portugal` all return `None`, so a kit whose header row spells its languages out loses every one of them unless the header is rewritten. Whitespace is stripped (`JA ` → `ja`) and case normalized (`KO` → `ko`). Record the old → new header mapping in the report: it is the producer's own vocabulary and they will ask about it.

A language column filled in under 5% of rows is not imported. Keyed inference excludes it as stray content and only says so in a note (`DEFAULT_MIN_FILL`, `loc_kit_ingest/infer.py`); `--include-lang <code>` overrides that. A language present in three rows out of a thousand therefore disappears unless the notes are read. Decide with the producer whether such a column is a real language or a leftover paste-over, and never report a language as imported without seeing it in the gate's own language list.

## `Character` and `Explanation` reach different destinations

A string kit carries context in two places, and the difference is not cosmetic:

- **`Explanation`** (headers `explanation`/`explanations`/`пояснение`/`пояснения`, `loc_kit_ingest/infer.py`) becomes a scalar profile field and is never rendered into a PO file. The component-creation wizard collects a key → explanation map (`weblate/utils/views.py`) and applies it to `Unit.explanation` through `Component.apply_loc_kit_explanations` once translations exist. It is editable in Weblate afterwards, needs `source.edit` to apply at all, and on a later string update a non-empty explanation survives unless the operator ticks "Overwrite existing, non-empty Explanations" (`weblate/trans/forms.py`).
- **Every other populated prose column**—`Character` being the canonical one—is declared in profile `comments` and rendered as a `#.` developer note in the source-language PO only. Weblate exposes it as `Unit.note`: read-only in the interface and refreshed from the file on every re-upload.
- Both arrive at the LLM as separate prompt fields, `explanation` and `note` (`weblate/machinery/llm.py`), and the prompt tells the model to use the note to choose register, gender agreement and tone. A `note` identical to the `explanation` is dropped, so duplicating the speaker in both columns wastes the field.

Therefore: the file is the producer's channel and is overwritten by the next export; the database is the localization team's accumulated knowledge and is not. Put the speaker's name—one word, nothing else—in `Character`, and write in `Explanation` only what the name does not already say. `Character` belongs to dialogue, replies and barks; UI labels, item names and notifications leave it empty.

Never name a column `flags`, `weblate-flags` or `флаги` in a string kit: inference consumes it as scalar metadata, and nothing applies it to a string component, so its content silently disappears. `Comment`, `Context` and `Note` headers are safe—they become developer notes exactly like `Character`.

## Template to hand a producer

When a game team asks how to deliver strings, hand them [`assets/loc-kit-template.csv`](assets/loc-kit-template.csv) instead of describing the format in prose. It ships the canonical column order, UTF-8 with BOM so Excel keeps Cyrillic through a round trip, semicolon delimiters, and thirteen rows that each demonstrate exactly one rule: a character limit, call-to-action wording, a dialogue line with speaker and register, a self-explanatory reply with an empty `Explanation`, a lowercase continuation fragment naming its owner, two sibling player-choice rows that reference each other, an unknown-gender addressee, two positional placeholders of different types, a glossary-bound term, Unity markup, the `$` line separator, and one row carrying no context at all.

Give the producer the rule in two sentences: `Character` holds the speaker's name and nothing else; `Explanation` holds anything a translator cannot see in the string itself. When unsure, write into `Explanation`—an empty cell beats a guess, because wrong context is not verified, it is believed.

The template passes the gate as shipped: 13 units, 0 skipped, `Character` mapped to a developer comment, `Explanation` to explanation metadata.

## Creating `Explanation` fields

`Explanation` describes **where and how this exact string is used**, not what its words mean. Write it in the confirmed explanation language; default to the source language. Create a value only when the available evidence answers a question the string itself does not:

- addressee, gender, tone, or whether a row is dialogue, narration, UI, notification, or a selectable option—the speaker itself belongs in `Character`, and goes here only when the kit has no such column;
- a fragment's owner and concatenation order, required case, capitalization, or grammatical agreement;
- what a placeholder contains when its type or grammar is not already explicit;
- which in-game sense an ambiguous/repeated string has;
- a verified placement or length constraint, or a platform control convention;
- a game-state consequence when it disambiguates the wording.

Use evidence in this order: explicit context/description columns; structurally paired neighbouring rows; stable key families plus their companion `*Text`/`*Description`/choice rows; then repeated values plus a neighbouring record that disambiguates them. A key name alone is only a clue. If the role is not provable, leave the cell empty. Evidence rows prove context; they do not automatically need their own explanation. Put the note on the row whose use remains unclear, and leave a self-explanatory companion `*Text`, `*Reply`, or `*Description` row blank.

Do not fill by quota or blanket rule. A row with multiple positional placeholders of different semantic types, or an unknown-gender participant that affects grammar, MUST be explained; `SmithSalary` is the canonical example. `Price: {0} gold coins`, `Day {0}`, and `Smithing is {0}% faster` already reveal their placeholder and normally stay empty. Do not write checks such as “preserve `{0}`,” QA findings such as “translation repeats,” generic definitions, translation advice, or invented lore. Checks validate markup; `Explanation` supplies missing usage context.

Required decisions for these evidence patterns (matching rows MUST follow them; do not discard a positive example merely because the placeholder is syntactically visible):

| Row | `Explanation` |
|---|---|
| `Price: {0} gold coins` | empty: the value type is explicit |
| `SmithSalary`, when runtime/interview evidence establishes argument types and unknown worker gender | `{0} — имя работника; {1} — целое количество монет. Пол работника заранее неизвестен.` |
| lowercase `AffectsFameBad` beginning with “and/и” | explain that it continues another sentence; the conjunction itself proves continuation, but name its owner or `{0}` type only if a paired row proves them |
| `CampaignSlot`, when runtime/reference evidence establishes a save slot | `{0} — номер слота сохранения.` |
| `Smithing is {0}% faster` | empty: percentage and direction are explicit |
| ambiguous choice label with sibling option + `*Text` + reply | explain each ambiguous option label that needs the role; self-explanatory companions stay empty |
| ambiguous `GildingPart`, followed by “Securely bind parts” | `Название конструктивной детали; здесь не процесс золочения.` |
| `GildingPartDescription` | empty: it is the evidence and already self-explanatory |
| a placeholder glued between two words, `наборы{0}кейсов` | `{0} — не количество, а служебная подстановка внутри фразы: подпись делится на две строки.` — nothing can be substituted between “наборы” and “кейсов”, so the slot is structural |
| a repeated separator token inside one string, `…изменился с {0} на {1}.##Требуется действие.##…` | name the argument roles and the separator: `{0} — прежний аккаунт, {1} — новый; ## разделяет абзацы сообщения.` |

A bare repeated value does not prove either sense. For choice labels, require at least two mutually exclusive option-label rows with the same scene stem. `*Text` and reply describe one branch and never count as an alternative. Therefore `Refuse` with only `RefuseText`/reply MUST stay blank; annotate it only when an actual sibling option row is present. When proven, describe only the selectable-option role; do not infer an addressee or consequence.

A placeholder is not self-explanatory merely because it is visible. `Уничтожить {0} монстров` is (a count) and stays empty; `наборы{0}кейсов` is not, because no value fits there. Existing target cells are the cheapest evidence for that distinction: when one language moved the placeholder to the end of the string and another rendered it as a quantity, the slot has already been misread and the row MUST be explained. Describe the slot, not the defect — the divergent translations go into the report as a question for the producer, and you never repair a target cell yourself.

For PO loc kits, each populated non-language prose column declared in profile `comments` becomes a separate developer note in column order. `Explanation` is not one of them: it is a scalar profile field with its own destination, so it neither overwrites nor absorbs a Context or Character column. Both CLI inference (without `--source-lang`) and the UI choose the leftmost populated language column, so ordering is load-bearing. Verify the rendered source-language PO for the notes and the profile's own `explanation` block for the explanations—never only the CSV.

## Workflow

1. **Preserve input.** Never edit or overwrite it. Input may be CSV, TSV, XLSX, TXT, or custom-delimited. Produce `NAME.import.csv` and, when needed, `NAME.excluded-rows.csv`.
2. **Discover format from content.** An extension proves nothing: a `.txt` from an engine team is routinely a UTF-16LE TSV with a BOM. Read the first bytes and dispatch on the signature (`ff fe`, `fe ff`, `ef bb bf`, the UTF-32 variants); decode strictly, never with `errors="replace"` or `"ignore"`. Then record newlines, sheets, quoting, escaping, candidate delimiters, and a count of every distinct row width. Inspect beginning, middle, end, and every ragged width. Where quotes are literal text in an unquoted export, read with `delimiter="\t", quoting=csv.QUOTE_NONE` so one stray quote cannot swallow the following records into a fabricated multiline cell.
3. **Prove the schema.** Map key, metadata, languages, and explanation from the reference, headers, neighbors, and language content. Resolve and retain every language column. A short row is not automatically missing the final language, and a long row is not automatically corrupt: surplus trailing fields may be trimmed only after proving that every one of them is empty in every affected row. If an unescaped delimiter can occur in text, obtain its escaping rules or an authoritative re-export.
4. **Audit identity.** Group by exact key; compare every language cell:
   - Exact duplicate: keep one; quarantine later copies.
   - Complete authoritative row plus corrupted/hybrid copy: keep the authoritative row; quarantine the hybrid.
   - Same key, different strings: quarantine unresolved rows until authoritative game IDs are supplied. An empty key is unresolved identity and MUST be quarantined.
   - Trustworthy identity with missing targets: retain it with empty target cells.
   - Every language cell empty: quarantine it. An empty source imports nothing, so the row is the difference between `0 skipped` and a kit the gate holds back. An empty *target* beside a real source is the opposite case and stays.

   Never rename keys merely to pass uniqueness. Never combine language halves based on similarity. If identity or translations are unavailable, quarantine is completion—not permission to guess.
5. **Write and reconcile.** Use `csv.writer(delimiter=";")`; global replacement/string joining corrupts punctuation. Preserve source order and requested metadata values, including intentional blanks. Parse back; assert the agreed header, fixed row width, unique non-empty keys, all expected languages, expected counts, and `input = imported + quarantined`. Quarantine includes source line, reason, and untouched fields.
6. **Run the gate:**

```bash
rm -rf /tmp/loc-kit-check
uv run python -m loc_kit_ingest "NAME.import.csv" --source-lang ru --out /tmp/loc-kit-check
```

`--source-lang` is mandatory even though column order should infer the same result; pass `ru` unless the user stated another source language. Ready means exit 0, expected counts, 0 skipped, the settled source language, every expected resolved language, and no ERROR diagnostics. Read the profile lines the gate prints, not only its verdict: every language column must appear with its own resolved code, `column N ('Explanation') -> explanation metadata` must be present whenever that column exists, and any column reported as ignored or excluded must be one you meant to leave empty. Opening the file in a spreadsheet is not proof.

Triage every warning; most are content facts rather than conversion defects. `po.target_equals_source` and `po.wrong_script` fire on brand names, item codes and pure formulas (`Dead Shell`, `xray m2`, ` + 50% HP`) that legitimately repeat across languages. Report them as questions for the producer — "should the event name be translated?" — and never silence one by editing a translation.

When `Explanation` is populated, inspect the generated PO profile and source-language PO:

- profile `comments` lists every retained prose metadata column in column order, while profile `explanation` names the `Explanation` column; the two never share a destination;
- `source_lang` equals the settled source language (`ru` by default);
- only that language's PO contains the generated `#.` developer comments, and no `Explanation` text appears in any PO;
- parse the PO with Translate Toolkit and compare logical values by key, not raw wrapped PO lines. In a keyed PO kit the key is the `msgid`: `unit.getid()` returns it while `unit.getcontext()` is empty, so a comparison keyed on the context matches nothing and looks like total corruption;
- explanation text is absent from the CLI output by design: it reaches `Unit.explanation` only through the component-creation wizard, so verify the parsed key → explanation map instead of grepping the PO.

```python
from loc_kit_ingest.parser import parse_component
from loc_kit_ingest.profile import load_profile
from loc_kit_ingest.reader import read_sheets

profile = load_profile(work_dir / "profile.loc-ingest.json")
component = profile.components[0]
rows = read_sheets(csv_path)[component.sheet]   # sheet name comes from the file name
result = parse_component(component, rows)       # takes the row list, not the sheet dict
parsed = {unit.key: unit.explanation for unit in result.units if unit.explanation}
assert parsed == authored_explanations and len(result.units) == expected_units
```

Do not use `infer_glossary_profile` for this check: it validates TBX term tables, not keyed PO string kits.

## Minimal writer (only after schema proof)

```python
import csv

header = ["key", "Character", *metadata_headers, source_code, *target_codes, "Explanation"]
with open(output_path, "w", encoding="utf-8", newline="") as stream:
    writer = csv.writer(stream, delimiter=";")
    writer.writerow(header)
    writer.writerows(mapped_rows)  # each row validated to len(header)
```

## Quick reference

| Symptom | Action |
|---|---|
| Source language unspecified | Interview user; do not infer |
| `Id` means legacy engine field | Rename descriptively; preserve intended blanks |
| Unknown/misleading extension | Detect from bytes and content |
| Additional language | Resolve and retain it |
| Ragged widths | Inspect every outlier; prove missing position |
| Duplicate key | Compare cells; deduplicate or quarantine |
| Cross-language hybrid | Quarantine; require authoritative repair |
| Empty key | Quarantine: identity is unresolved |
| Empty target | Keep empty; report warning; the unit must still count toward `0 skipped` |
| Explanation requested | Populate only evidence-backed usage context; blanks are normal |
| Speaker known | `Character` = the name only; never repeat it in `Explanation` |
| Team asks for a delivery format | Hand `assets/loc-kit-template.csv`; do not paraphrase it |
| Column named `flags` in a string kit | Rename it: the importer swallows it and nothing applies it |
| `Explanation` present | Verify profile `explanation`, `source_lang`, and that no `Explanation` text landed in a PO |
| `.txt` from an engine team | Dispatch on the BOM; it is often UTF-16LE TSV |
| Header spells `English`, `Portugal` | Rewrite to codes; a language name resolves to nothing |
| Ambiguous `Portugal` / `Chinese` | Ask `pt` vs `pt_BR`, `zh_Hans` vs `zh_Hant`; never relabel silently |
| Language filled in a handful of rows | Under 5% it is excluded as stray content; decide, then `--include-lang` |
| Row empty in every language | Quarantine: an empty source imports nothing |
| Surplus trailing fields | Trim only after proving every one of them is empty |
| Kit has no speaker or context column | Still emit `Character` and `Explanation`, both empty |
| Placeholder glued between words | Explain the slot: it is a separator, not a value |
| `target_equals_source` / `wrong_script` | Triage as content — brand, code or formula; ask, do not edit |
| Any ERROR | Not ready |

## Red flags

Source language derived from column order, population or filenames instead of the `ru` default plus a stated correction; leaving the `ru` default in place after the kit contradicted it; language-shaped metadata headers; spelled-out language names left in the header row; a language quietly dropped by the fill threshold; decoding with `errors="replace"`; generated values in intentionally empty legacy columns; `Character` or `Explanation` omitted because the input had no such column; blind delimiter replacement; dropped languages; preserved known-wrong rows; invented `_2` keys; guessed missing positions; readiness inferred from parseability instead of `loc_kit_ingest`; filling every placeholder or repeated string; mechanical “preserve `{0}`” notes; a warning silenced by editing a translation; calling `*Text`/reply a sibling alternative; inferred speaker/addressee from a key alone; treating `RefuseText`/reply as proof without a sibling option; the speaker duplicated in both `Character` and `Explanation`; a `flags` column in a string kit; claiming `Explanation` becomes a PO `#.` note; claiming PO comments are DB `Unit.explanation`.

## Report

Close with a short Russian report: output paths; source and target languages with the header mapping you applied; imported and quarantined counts against the input total; the gate's own verdict lines; each `Explanation` row with the evidence behind it; the warning triage phrased as questions for the producer; and the next step — the wizard's "Upload translation files" tab with the settled source language, which is immutable once the component exists. Keep import readiness separate from linguistic quality: the gate proves the file loads, never that a translation is right. Delete the temporary verification directory.
