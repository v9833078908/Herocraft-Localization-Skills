---
name: preparing-weblate-loc-kits
description: "Use when converting a game localization kit or string export—CSV, TSV, XLSX, TXT, or custom-delimited text—for import through the HCGameLoc Weblate component-creation interface."
---

# Preparing Weblate loc kits

## Overview

Convert exports into the HCGameLoc import contract without inventing identities, losing languages, or importing cross-language corruption. Filename extensions are untrusted; `loc_kit_ingest` proves readiness.

## Required interview

Before writing the import file, ask the user and record:

1. **Is the source language Russian?** Russian (`ru`) is the default: Hero Craft kits are authored in Russian, so ask for a correction rather than an answer — "Исходный язык — русский, верно?" — and proceed on the default when the user does not object, stating the assumption in the report. The source language is still semantic project metadata: it MUST NOT be *derived* from column order, population, filenames, or apparent text quality, and it must be the first language column because the UI infers it from that position. Leave `ru` only on an explicit statement by the user, or when the kit itself contradicts the default (an empty or clearly machine-translated Russian column beside a fully authored other language); in that case stop and confirm before writing anything.
2. **Which file is the structural reference?** Use it for metadata roles and ordering conventions, not as permission to discard languages absent from it.
3. **What do key, metadata, ID, explanation, and context columns mean?** Ask whether legacy columns must remain and whether their values should be empty. If explanations must be created, confirm their language; default to the source language, not the conversation language. Never invent game identities or usage context.
4. **How should unverifiable duplicate or malformed rows be handled?** Recommend quarantine; never guess translations or IDs.

Investigate file-provided facts—encoding, delimiter, escaping, sheets, columns, and row widths—with tools rather than asking. Do not generate the final import until the source language is settled—`ru` by default, or a user-stated alternative—and metadata semantics are explicit.

## Target contract

Produce semicolon-delimited UTF-8 CSV with standard quoting:

```text
key;<metadata columns>;<source-language>;<all target languages>;Explanation
```

The reference schema is authoritative for metadata roles and order. Retain every resolved language from the source even when absent from the reference. Put the settled source language first—`ru` unless the user stated another one—then targets in their original input order unless the reference explicitly fixes language order. `key` becomes the PO unit identity. `Explanation` is optional unless the reference contains it or the user asks to create contextual explanations; then keep the exact `Explanation` header as the last column. Empty cells are normal.

A metadata header that resembles a language code is dangerous: `Id` can mean Indonesian. Rename a legacy engine column descriptively, for example `Unity legacy ID`. If its values are intentionally empty, keep them empty; the importer will ignore the column. If an authoritative numeric ID exists, retain it as a location reference. Do not populate an empty legacy column with generated values unless the user explicitly requests that behavior.

For a Russian-source kit containing English, Simplified Chinese, Traditional Chinese, Korean, and Japanese, with an intentionally empty Unity legacy column:

```text
key;Unity legacy ID;ru;en;zh-Hans;zh-Hant;ko;ja;Explanation
```

Use codes recognized by `loc_kit_ingest/langcode.py`; bare `zh` is not recognized here, so distinguish `zh-Hans` and `zh-Hant`. Unknown translations and absent explanations stay empty.

## Creating `Explanation` fields

`Explanation` describes **where and how this exact string is used**, not what its words mean. Write it in the confirmed explanation language; default to the source language. Create a value only when the available evidence answers a question the string itself does not:

- speaker, addressee, gender, tone, or whether a row is dialogue, narration, UI, notification, or a selectable option;
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

A bare repeated value does not prove either sense. For choice labels, require at least two mutually exclusive option-label rows with the same scene stem. `*Text` and reply describe one branch and never count as an alternative. Therefore `Refuse` with only `RefuseText`/reply MUST stay blank; annotate it only when an actual sibling option row is present. When proven, describe only the selectable-option role; do not infer an addressee or consequence.

For PO loc kits, each populated non-language prose column declared in profile `comments` becomes a separate developer note in column order; `Explanation` neither overwrites nor absorbs existing Context/Character columns. The renderer writes these as `#.` notes **only in the source-language PO**. Both CLI inference (without `--source-lang`) and the UI choose the leftmost populated language column, so ordering is load-bearing. This is not glossary TBX explanation and does not by itself prove Weblate `Unit.explanation` behavior. Verify the rendered source-language PO, not only the CSV.

## Workflow

1. **Preserve input.** Never edit or overwrite it. Input may be CSV, TSV, XLSX, TXT, or custom-delimited. Produce `NAME.import.csv` and, when needed, `NAME.excluded-rows.csv`.
2. **Discover format from content.** Record encoding/BOM, newlines, sheets, escaping, candidate delimiters, and all row widths. Inspect beginning, middle, end, and every ragged width. An extension proves nothing.
3. **Prove the schema.** Map key, metadata, languages, and explanation from the reference, headers, neighbors, and language content. Resolve and retain every language column. A short row is not automatically missing the final language. If an unescaped delimiter can occur in text, obtain its escaping rules or an authoritative re-export.
4. **Audit identity.** Group by exact key; compare every language cell:
   - Exact duplicate: keep one; quarantine later copies.
   - Complete authoritative row plus corrupted/hybrid copy: keep the authoritative row; quarantine the hybrid.
   - Same key, different strings: quarantine unresolved rows until authoritative game IDs are supplied. An empty key is unresolved identity and MUST be quarantined.
   - Trustworthy identity with missing targets: retain it with empty target cells.

   Never rename keys merely to pass uniqueness. Never combine language halves based on similarity. If identity or translations are unavailable, quarantine is completion—not permission to guess.
5. **Write and reconcile.** Use `csv.writer(delimiter=";")`; global replacement/string joining corrupts punctuation. Preserve source order and requested metadata values, including intentional blanks. Parse back; assert the agreed header, fixed row width, unique non-empty keys, all expected languages, expected counts, and `input = imported + quarantined`. Quarantine includes source line, reason, and untouched fields.
6. **Run the gate:**

```bash
rm -rf /tmp/loc-kit-check
uv run python -m loc_kit_ingest "NAME.import.csv" --source-lang ru --out /tmp/loc-kit-check
```

`--source-lang` is mandatory even though column order should infer the same result; pass `ru` unless the user stated another source language. Ready means exit 0, expected counts, 0 skipped, the settled source language, every expected resolved language, and no ERROR diagnostics. Confirm metadata columns are interpreted or ignored as intended. Inspect and report warnings. Opening in a spreadsheet is not proof.

When `Explanation` is populated, inspect the generated PO profile and source-language PO:

- `comments` maps `Explanation` and every retained prose metadata column separately, in column order;
- `source_lang` equals the settled source language (`ru` by default);
- only that language's PO contains the generated `#.` developer comments;
- parse the PO with Translate Toolkit and compare logical developer-note values by key, not raw wrapped PO lines; all non-empty CSV explanations must match after render/parse-back.

Do not use `infer_glossary_profile` for this check: it validates TBX term tables, not keyed PO string kits.

## Minimal writer (only after schema proof)

```python
import csv

header = ["key", *metadata_headers, source_code, *target_codes, "Explanation"]
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
| `Explanation` present | Verify `comments`, `source_lang`, and source-PO `#.` notes |
| Any ERROR | Not ready |

## Red flags

Source language derived from column order, population or filenames instead of the `ru` default plus a stated correction; leaving the `ru` default in place after the kit contradicted it; language-shaped metadata headers; generated values in intentionally empty legacy columns; blind delimiter replacement; dropped languages; preserved known-wrong rows; invented `_2` keys; guessed missing positions; readiness inferred from parseability instead of `loc_kit_ingest`; filling every placeholder or repeated string; mechanical “preserve `{0}`” notes; calling `*Text`/reply a sibling alternative; inferred speaker/addressee from a key alone; treating `RefuseText`/reply as proof without a sibling option; claiming PO comments are DB `Unit.explanation`.
