---
name: splitting-loc-kits-into-components
description: "Use when one localization kit, string export or existing Weblate component must become several components — UI, Dialogues, Tutorial, quests, items — when a game team asks to regroup strings into separate components, or when the rows of one table must be routed into more than one component."
---

# Splitting loc kits into components

## Overview

A split is a **partition proved cell by cell**, not a filter run three times. One input table becomes N import files plus one quarantine file, every input row lands in exactly one of them, and every language cell is byte-identical to the input. The boundary between components is a decision the user owns; the conservation of the data is a decision you prove with a machine.

**REQUIRED SUB-SKILL:** Use preparing-weblate-loc-kits for format discovery, schema proof, language resolution, `Character`/`Explanation` semantics and the readiness gate. Everything it says applies to *each* output file of a split. This skill adds only the partition layer.

## Language and scope

Keep these instructions in English. Conduct the interview, progress notes and the final report in plain Russian: "компонент", "исходный язык", "строка", "пояснение". Column headers, language codes and diagnostics stay machine-readable English.

This skill produces files — N import files, one quarantine file, a report. It never creates a component, uploads anything, edits a translation, or deletes the input. Reading the fork's code and a **read-only** probe of a live component are expected; changing a live instance is not.

## What the intake forces on a split

These are properties of the import path, not style preferences. Each one has been observed to break a split:

| Fact | Source | Consequence for a split |
|---|---|---|
| One upload creates one component; a multi-sheet workbook is refused with "The workbook holds N sheets, and one upload creates one component" | `weblate/utils/views.py` `create_component_from_kit` | One file per component. Never deliver one workbook with three sheets |
| The source language is the **leftmost populated language column** | `loc_kit_ingest/infer.py`; the gate prints `source language assumed to be 'de' (leftmost populated language column)` | The settled source language must be the first language column **in every output file** |
| A component's source language is immutable once the component exists | fork behaviour | A wrong source column is not fixable later — the component must be deleted and recreated |
| A row with a key but no text in any language is `po.key_without_content`, severity ERROR | `loc_kit_ingest/parser.py`; UI: "The loc-kit has errors, nothing was imported" | One such row rejects the **whole file**, not the row. It must go to quarantine, never into a component |
| `Explanation` is scalar profile metadata applied to `Unit.explanation`; other prose columns become `#.` notes | see preparing-weblate-loc-kits | Same header set in every output file, or components diverge in what context they can carry |
| A kit carries key, text, notes and explanations — nothing else | file format | Unit states (approved / needs rewriting), unit flags, comments, history and authorship do not survive a re-creation |

### Rationalizations that produced a broken split

Every excuse below was produced by an agent splitting a kit without this skill. Four of five kept the export's column order; none quarantined a row that was empty in every language, and the resulting files were refused by the gate with `exit=2`.

| Excuse | Reality |
|---|---|
| «Исходный язык задаётся настройкой компонента, а не позицией колонки» | Not on this path. `infer_profile` takes the leftmost populated language column and the wizard has no per-column choice. The gate then prints `source de` on a Russian kit |
| «Любая перестановка колонок — лишний диф и риск сломать маппинг» | The diff is against a file nobody keeps; the source language is against a component nobody can fix. Reorder |
| «Пустая строка поедет как есть, Weblate покажет её непереведённой» | A row empty in *every* language is an ERROR that rejects the whole file. An empty *target* beside a real source is the case that legitimately stays |
| «UI как catch-all, значит ничего не потеряется» | A confirmed residue destination is correct; it does not cover the rows that break the file, and it must be confirmed rather than assumed |
| «`partition_exact=True`, `data_match=True` — проверено» | A self-declared pass on row counts and key sets. Both were true while two of three files were unimportable |
| «Правило выведу по смыслу строк, ключи врут» | Reading the text is not reproducible: independent agents produced three different assignments for the same two keys. Anchor the rule, show the ambiguity set, let the user decide |

## Required interview

Do not write any output file before these are settled. Bring measurements to the table, not open questions.

1. **The boundary rule.** Propose one, stated as anchors on the key (or on whatever grouping signal the kit actually carries), and show the user: the count per component, the residue count, and the **ambiguity set** — every key whose anchor and apparent meaning disagree — with samples. Ask which side each ambiguous family belongs to. A split decided by reading the Russian text is your taste, not their contract.
2. **The residue destination.** Name the component that receives every key matching no anchor, and confirm it. "UI as catch-all" is a legitimate answer; silently dropping unmatched rows is not.
3. **Is an existing component being replaced?** If yes, probe it read-only first (see "Replacing a live component") and report what the re-creation loses *before* the files are used, not after the old component is deleted.

The source language does **not** enter the interview as an open question: `ru` is the default, per preparing-weblate-loc-kits. Confirm it, and state the assumption in the report.

## The boundary rule is a written contract

Write the rule down in the report in the form you implemented it, so the next kit can be split the same way:

```python
RULE = [("Dialogues", ("dialog_text_", "dialog_character_")),
        ("Tutorial",  ("tutorial_",)),
        ("UI",        ())]   # residue destination, confirmed by the user
```

**Anchor the rule at the start of the key.** A substring test over-captures without a sound: on a real 3864-row kit, `"dial" in key` matched 481 keys where `key.startswith("dialog_")` matched 388 — 93 UI rows (`label_continue_dialog`, `shop_confirm_dialog_title`, `hard_compensation_dialog_content`) would have been moved into a dialogue component that the game's dialogue loader never reads. The mirror case is `mission_descr_complete_tutorial`: a mission description that merely mentions the tutorial.

Grouping signals, in order of trustworthiness:

| Signal | Use it when | Caution |
|---|---|---|
| Sheets of the workbook | the producer already separated them | They may be languages or platforms, not components — check the headers before trusting the names |
| A column stating the group (`component`, `screen`, `file`) | present and populated | Verify the values are closed and spelled consistently before grouping on them |
| Key namespace anchored at the start | keys share a stable `family_` convention | Anchor, never substring; second-level anchors (`dialog_text_` vs `dialog_name_`) are normal |
| An authoritative external artifact (engine file list, id ranges) | the producer supplies it | Do not reconstruct it from the kit |
| Nothing above | — | **Stop and ask for a grouping signal.** A headerless positional export whose key is the English source text (`Game settings._Game settings._Общие настройки._…`) carries no component signal at all; inventing buckets from its content is fabrication |

Do not route a row by what its text says. Two agents reading the same kit produced three different assignments for the same two keys; the anchored rule plus a confirmed ambiguity list produces one.

## Partition contract

Every output file has the same shape:

```text
key;Character;<other metadata columns>;<source language>;<target languages>;Explanation
```

- **Identical header in every file**, including `Character` and `Explanation` even when both are empty everywhere, and including a language that is empty in this particular component. Components that share a schema share a configuration.
- **The settled source language is the first language column** in every file, whatever order the input used. A Weblate export is alphabetical by code, so a kit whose source is `ru` arrives with `de` first: shipping "the original column order" hands you a German-source component.
- **Row order inside a component follows the input.** Do not re-sort.
- **One sheet per file.** Name it after the component.
- **Write empty cells as `""`, never `None`.** With `None`, openpyxl drops trailing empty cells when the file is read back, rows arrive at different widths and the conservation check reports drift that does not exist. Fixed width also makes `len(row) == len(header)` a usable assertion.
- **Copy a recognized language header verbatim.** Reordering columns is required; rewriting their spelling is not. `zh_Hans` and `pt_BR` already resolve (`loc_kit_ingest/langcode.py`), so "normalizing" them to `zh-Hans` or `pt-BR` only edits the producer's own vocabulary and hides which spelling their exporter emits. Rewrite a header only when it resolves to nothing — a spelled-out name such as `Russian` — and record that mapping in the report.
- **Never mutate a cell while splitting.** No trimming, no filling an empty target, no repairing a placeholder, no normalizing case. A defect found in transit goes into the report as a question.

Quarantine file: one row per held-back input row, carrying the source row number, the component it would have joined, the reason, and the untouched original cells. Rows empty in every language are the mandatory case (`po.key_without_content`); the duplicate and hybrid cases from preparing-weblate-loc-kits apply per component.

## Conservation proof

Row counts and key sets are not a conservation proof — they pass while a cell is silently altered. Prove it with the reader the importer itself uses, and compare padded tuples so representation differences cannot masquerade as data loss:

```python
from loc_kit_ingest.reader import read_sheets

def cells(row, width):                     # one normalization for both sides
    body = [("" if c is None else c) for c in row[1:]]
    return tuple(body + [""] * (width - len(body)))

src = read_sheets(kit_path)[sheet]         # header + data rows, as the importer sees them
width = len(src[0]) - 1
original = {r[0]: cells(r, width) for r in src[1:]}

seen, counts = {}, {}
for name, path in outputs.items():         # the N component files
    rows = read_sheets(path)[name]
    assert rows[0] == header               # same schema everywhere
    counts[name] = len(rows) - 1
    for r in rows[1:]:
        assert len(r) == len(header)       # fixed width
        assert r[0] not in seen, f"{r[0]} landed in two components"
        seen[r[0]] = cells(r, width)
for r in quarantine_rows:                  # held-back rows count too
    seen[r.key] = cells(r.original, width)

assert set(seen) == set(original), "keys lost or invented"
drift = [k for k in original if seen[k] != original[k]]
assert not drift, drift
assert sum(counts.values()) + len(quarantine_rows) == len(original)
```

Report the identity itself — `3453 + 274 + 120 + 17 = 3864` — and the drift count. If the input had duplicate keys, key identity is not available: prove conservation on multisets of full rows instead, and resolve the duplicates per preparing-weblate-loc-kits before splitting.

## Gate every output file

```bash
rm -rf /tmp/loc-kit-check && mkdir -p /tmp/loc-kit-check
for f in ui dialogues tutorial; do
  uv run python -m loc_kit_ingest "NAME.$f.import.xlsx" --source-lang ru --out "/tmp/loc-kit-check/$f"
done
```

Create the parent directory first: with a missing parent the run fails on `pipeline.missing_parent` before reading a single row, which looks like a broken file rather than a broken command.

Each file must independently report exit 0, its expected unit count, `0 skipped`, the settled source language, and every expected language with its own resolved code. One file passing proves nothing about its siblings: a split fails asymmetrically, because the rows that break a file are not spread evenly across components. Triage warnings per preparing-weblate-loc-kits; delete the temporary directory afterwards.

## Replacing a live component

Splitting an existing component means deleting it and creating N new ones. Before that is done, probe the live component **read-only** and put the numbers in the report:

- **Counts that do not survive:** units in state approved / needs rewriting, units with flags, comments. `Change` history and authorship go with them.
- **Explanations and notes,** which *can* be carried: recover them and fill the `Explanation` column of the file the key lands in.
- **Staleness, both directions:** keys live in the component but absent from the export (the export is behind) and keys in the export but absent live (the export is ahead, or the keys were deleted). Report both lists. Do not merge live rows into the kit and call it a split of the kit — recommend a fresh export, or ask.

When copying a live explanation into the kit, match on **both** the key and the exact source string. Presence of the key is not enough: an export that is 14 rows behind can also be one edit behind on a source string, and a current explanation attached to a stale source is a false statement about a string nobody wrote. Report any key whose source differs and leave its cell empty.

Never copy a live *target* value into the kit to fill a gap. The kit is the producer's channel; the database is the team's accumulated work; mixing them destroys the evidence of which is which.

## Metadata is not derived from key names

`Character` is the speaker; a `dialog_character_*` row **is** a speaker-name resource, not a line spoken by that speaker, so writing its own name into its `Character` cell asserts a false self-reference. Filling `Character` for a `dialog_text_*` row requires a proven line→speaker mapping; a key like `dialog_text_campaign_0_0_boss_1` does not say who speaks, and no amount of reading the text supplies it. If the kit and the database both lack the mapping, leave the column empty, say so, and name the artifact that would fill it. The same applies to `Explanation`: the split is not an occasion to invent context.

## Quick reference

| Symptom | Action |
|---|---|
| Kit must become N components | One file per component; never one workbook with N sheets |
| Export column order is alphabetical | Move the settled source language first in every file |
| Key contains `dialog`/`tutorial` mid-string | Anchor at the start; the substring is not the signal |
| Anchor and meaning disagree | Show the ambiguity set with counts; the user decides |
| Key matches no anchor | Route to the confirmed residue component; never drop |
| Row empty in every language | Quarantine: one such row rejects the entire file |
| Empty target beside a real source | Keep it empty inside its component |
| Writing XLSX output | Empty cell is `""`, not `None`; assert fixed width |
| Header already a recognized code (`zh_Hans`, `pt_BR`) | Copy it verbatim; reorder columns, never respell them |
| Gate reports `pipeline.missing_parent` | The `--out` parent does not exist; `mkdir -p` it and re-run |
| "Row counts match" | Not a proof: compare every language cell through one reader |
| Drift appears only in trailing columns | Representation, not data: pad both sides, re-check |
| Existing component is being replaced | Probe it read-only; report states, flags, comments, history as losses |
| Live explanation to carry over | Match key **and** source string; otherwise leave empty |
| Kit carries no grouping signal | Stop; ask for one; do not invent buckets |
| Sheets named by language or platform | Not component boundaries; check headers |
| Any ERROR in any output file | The split is not ready |

## Red flags

Source language left in the input's column position "because Weblate sets it in the component settings"; boundary decided by reading the strings instead of an anchored, confirmed rule; substring matching on keys; unmatched rows dropped or quietly renamed into a fourth file nobody asked for; a row empty in every language shipped inside a component; `None` written into empty cells; a recognized language header respelled; conservation claimed from row counts, key sets or a self-declared `data_match=True`; one output file gated and its siblings assumed fine; a live component deleted before the losses were reported; an explanation copied on a key match alone; `Character` or `Explanation` filled from key names; a cell "cleaned up" in transit.

## Report

Close with a short Russian report: the output paths with the row count of each; the arithmetic identity including the quarantine file; the boundary rule as implemented, with the ambiguous families and who decided them; the settled source language and its column position; the gate's own verdict line per file; the cell-level drift count; for a replaced component — the recovered explanations with the match rule used, the staleness lists in both directions, and the explicit list of what the re-creation loses; and the next step: the wizard's "Upload translation files" tab, one file per component, source language immutable afterwards.
