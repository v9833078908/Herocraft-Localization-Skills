---
name: game-glossary-builder
description: "Use when preparing a game glossary for Weblate from localization files, spreadsheets, full string exports, structured resources, screenshots, or pasted text, including unfamiliar file formats."
---

# Game glossary builder

Build a source-grounded game glossary for a new project. Ordinary entries have
no flags. Producer-approved exceptions are a separate decision, not a by-product
of extracting terms.

## Language and scope

Keep these instructions in English. Conduct interviews, progress updates and
reports in plain Russian. Explain terms as “язык оригинала”, “переводы”,
“пояснение” and “особое правило”; do not expose pipeline jargon. Explanation text
in the file defaults to Russian unless the producer specifies another language.
Exact CSV headers and flag tokens remain machine-readable English.

This skill prepares files, not a live Weblate project. Do not query repositories
or live instances for game knowledge. Local importer code may be inspected to
verify technical compatibility. Do not upload, deploy, translate missing cells,
or purchase external model calls without separate authorization. If the user asks
only to review/edit the skill, do not resume their glossary or interview them.

## Output contract

Output a UTF-8 CSV with proper CSV quoting, a header and one row per source term:

```csv
en,ru,explanation,flags
Iron,Железо,Ресурс для изготовления предметов.,
```

Use the confirmed source language first, selected target languages in input order,
then exactly `explanation,flags`. Keep the `flags` column even when every cell is
empty. No technical keys, sections, approval-status tags or invented columns.
A source term may have several target languages in the same row. The example
illustrates structure, not permission to invent translations or meanings.

Reference template: `~/Downloads/weblate-glossary-import-template.csv`.
Project root: `/Users/eli/Documents/PythonProjects/gamedev tools/weblate`.
Importer contract: `docs/product/guides/loc-kit-ingest.md`.
Verify against current `loc_kit_ingest/{reader,infer,parser,writer}.py`; older
example converters are not authoritative about current format capabilities.

## Workflow

Interview first -> decode and normalize -> research -> select terms -> review
exceptions -> serialize -> verify -> report. Keep raw input, extraction evidence
and producer decisions separate from the final CSV.

### 1. Interview before reading the kit

Use facts already supplied by the producer. Ask only missing decisions in a short
Russian batch of at most six questions, then wait for answers before ingesting or
measuring the file. No pre-interview scan and no invented term-count estimates. Ask for:

- Game identity and a store/official link: “Пришлите ссылку на игру в Google Play,
  Steam или другом магазине. Если страницы ещё нет — название и краткое описание.”
  If they have no link, research by title and developer after the interview;
  confirm uncertain identity. An unreleased game is not a reason to refuse.
- The intended original language: “На каком языке исходные тексты игры?”
  Ask a separate Weblate-source clarification only if the producer explicitly
  describes a different authoring and import language. File order alone cannot
  settle that decision.
- Requested languages: “Для каких языков нужен глоссарий?” Offer all supplied
  languages as a scope option, not an assertion about unseen column contents.
- Scope: “Включаем названия предметов, персонажей и мест, а также повторяющиеся
  игровые понятия? Обычные кнопки и целые реплики не включаем.” The producer may
  change these categories. Do not promise counts before extraction.
- Existing terminology agreements and exceptions: “Есть ли готовые правила или
  список терминов? Есть ли слова, которые нужно сохранять без перевода, писать
  строго в одной форме или не использовать?”
  A list of existing materials and a decision about translation quality are
  separate answers. Accept “нет”; do not require a style guide or a flag quota.

Question wording: one decision per question, distinct short options, consequences
in descriptions. Do not recommend that a translation is approved merely because
the game was released. Use clarification after inspection for genuinely ambiguous
language headers or meanings. Batch real blockers when found; no arbitrary
one-follow-up limit that would force guessing.

Approval history is not a mandatory gate. Preserve supplied translations as supplied;
unknown approval does not authorize erasing them, declaring them canonical, or
retranslating them. Mention uncertainty in the report. Ask whether existing wording
may be used as the preferred term only when a concrete conflict changes selection.
If the producer explicitly excludes draft translations, explain the resulting
missing-language/import limitations before promising a ready-to-upload glossary.
“Решай сам” authorizes ordinary conservative choices, not new restrictions.

### 2. Decode and normalize any readable localization input

The filename extension is a hint, not a format contract. Separate raw-file reading
from glossary import. `read_sheets(Path(...))` directly accepts UTF-8 CSV/TSV and
XLSX; it is not a universal reader. Adapt other formats to a normalized table first.

- Inspect bytes/BOM before decoding. Recognize UTF-8, UTF-16 and UTF-32 signatures;
  decode strictly. Without a signature, use encoding evidence and inspect ambiguous
  cases. Never hide decoding failures with replacement/ignored bytes.
- Delimited text (`.txt` included): establish delimiter, quoting, escaping and
  record boundaries from the content. Use `csv.reader` for quoted CSV/TSV, including
  embedded newlines. For an unquoted tab export whose quotes are literal text,
  use `delimiter="\t", quoting=csv.QUOTE_NONE` and preserve quote characters.
- Structured JSON, XML, YAML, PO, key/value resources, per-language files and archives:
  use an appropriate safe parser. Do not execute supplied code, macros, unsafe YAML
  constructors or XML external entities. Join language files by stable keys/context,
  not row order or translated text. Retain duplicate-key and missing-key diagnostics.
- Spreadsheets: preserve sheet identity and check missing formula results. Images,
  PDFs and pasted text: extract with available readers/OCR and retain locations;
  verify uncertain cells before selecting them. Never invent unreadable content.
- For unfamiliar formats, build a small deterministic adapter from the observed
  grammar. Encrypted, proprietary binary, ambiguous or unavailable content requires
  a readable export or format description, not a fabricated successful parse.

Keep per-record provenance: file, sheet/record/key, raw values, language mapping and
explanatory context. Preserve meaningful whitespace, markup, placeholders, escapes
and invisible characters until a documented normalization is justified. Do not
mistake a single-column file for proof of a particular alternative delimiter.

Validation of an adapter:

1. Account for every input record and every nonempty field; report malformed records
   with locations. Never silently truncate records or drop late-file content.
2. Surplus trailing fields may be trimmed only after proving they are all empty;
   this is not permission to discard nonempty fields or internal empty cells.
3. A bounded `rsplit(separator, locale_count)` is valid only when trailing locale
   fields cannot contain unescaped separators and missing fields are unambiguous.
   Field counts and script distributions are diagnostic clues, not proof of alignment.
4. Rejoining arbitrary splits is tautological. Verify the declared grammar, key
   coverage, boundary records, nonempty-field conservation and normalized write/read
   equality. Check irregular records individually before accepting the normalization.
5. Keep literal unmatched quotes as content in a proven unquoted grammar; do not let
   a tolerant CSV reader consume subsequent records as a fabricated multiline cell.

Only then report encoding, format, record counts, blank/caption rows, language
coverage, duplicates and uncertainties. Normalize to UTF-8 CSV for downstream tools;
the normalization table may retain keys, but the final glossary must not.

Map known language names/codes with `loc_kit_ingest/langcode.py`. Ask about regional
ambiguity rather than inventing it (Portuguese vs Brazilian Portuguese, simplified
vs traditional Chinese). Do not relabel a real code just because a game often uses
another locale. For Indonesian output use `Indonesian(id)`; bare `id` is treated as
a technical identifier. The requested original language becomes the leftmost column.

### 3. Research the game externally

Read the supplied official/store page, then perform additional web research on the
same game: developer materials, patch notes, reputable guides or a wiki. Prefer
primary sources and relevant available localized pages; do not assume every locale
has an official translation. Record URLs and what each supports.

Establish genre, setting, entities and terminology families. Use the kit's actual
contexts/descriptions alongside external evidence. Store marketing and language
lists neither certify kit translations nor override the producer. An official name,
brand, Latin spelling or repeated wording is not evidence for an automatic flag.

When evidence is limited, give a narrow factual description and record uncertainty.
A meaningful key prefix supports a category, not invented lore, gender or mechanics.
Research may suggest terminology but must not silently replace supplied translations.

### 4. Select terminology and explanations

Select reusable game concepts under the agreed scope, not all short strings.
Keys, neighbouring descriptions and repeated contexts are evidence; prefixes and
length thresholds alone are not selectors. Random keys are valid. Dialogue can
provide context or contain a recurring entity; do not discard that evidence merely
because it is in a dialogue namespace. Do not infer a translation by unverified
substring alignment across languages.

Exclude generic UI labels and full sentences unless the producer requested them.
Keep named tasks/events when agreed scope makes them terminology. Distinguish real
term/description pairs from arbitrary adjacent rows.

Explain what each term means and where its usage should be consistent, in one
concise Russian line. Allow normal grammar for ordinary terms. Do not smuggle
“never inflect”, “must match exactly” or an unapproved ban into an explanation when
the flag is blank. Use specific, evidenced notes rather than generic boilerplate.

Merge identical entries only when meanings, translations and approved rules agree.
Treat case-only differences as duplicate candidates, not automatic equivalence.
When one source string has divergent meanings/translations, present the alternatives
and ask which belongs in this flat glossary. Do not silently choose the first or
union flags. Current flat identity cannot carry duplicate source/context rows
(`tbx.duplicate_context`); explanations do not fix a structural collision.

Preserve translations from the selected record. Blank stays blank; unknown approval
is not blank. Trim outer term whitespace only as documented import normalization;
record such changes. Keep evidence for every selected and excluded candidate.

### 5. Moderate exceptional rules

Start every entry with an empty `flags` cell. Most glossaries need no restrictions.
The interview discovers whether special agreements exist; it does not assign flags
by entity class. If there are no requested exceptions, skip this review stage and
serialize ordinary entries with blank flags.

For each requested or evidence-backed proposed exception, show a compact Russian
review table: source term; relevant translation; language(s); proposed rule in plain
words; why it is needed; what it will prohibit; approval status; export capability.
Proposals remain unapplied until approved. Approval may come from an explicit
producer decision or an applicable rule document the producer designates as binding.
A blanket “decide yourself” is not approval for restrictions. Do not ask the producer
to review every ordinary row. Unknown, rejected or unnecessary proposals remain blank.

| Decision | Meaning | Approval and current delivery |
|---|---|---|
| Empty | Ordinary recommended term, normal grammatical forms allowed | Default; no special agreement required |
| `read-only` | Preserve the source wording instead of translating it | Confirm exact terms and languages; this CSV applies it across all included target languages |
| `exact` | Require the specified target form without inflection/paraphrase | Confirm each term and language; this CSV accepts it and applies it to every nonempty imported target on that row |
| `forbidden` | Disallow the specified target rendering, not the source trigger term | Rare; confirm banned rendering, preferred replacement and affected languages; this CSV propagates the flag across languages |

Compatibility is a separate gate after approval:

- `loc_kit_ingest/parser.py:GLOSSARY_SOURCE_FLAGS` accepts `read-only`, `forbidden`
  and `exact`. `read-only`/`forbidden` are inherited from the source term, while
  `exact` is target-scoped: only a nonempty imported target keeps it. The source
  unit, a blank or absent target, and a language added to the glossary later never
  receive it, so a later language needs a separate decision in Weblate.
- Never invent `ru:exact`, `exact:ru`, JSON flags, approval tags, extra columns or
  substitute `read-only` for `exact`. Verify current code if capabilities change.
- The shared column cannot express an exact rule for only one of several target
  languages. For that, keep ordinary CSV entries and list the approved
  term/language/rule separately as requiring application in Weblate after import;
  explain that this CSV does not apply it. If automatic enforcement in the file is
  required, obtain agreement on another supported workflow; do not silently
  downgrade the requirement.
- Combinations follow current runtime precedence: `exact, forbidden` behaves as
  `forbidden`, and `exact, read-only` behaves as `read-only` and demands the source
  form. Do not assign a combination automatically.
- For an exportable read-only row, verify that target cells repeat the approved
  source wording. Resolve existing translated names with the producer rather than
  overwriting them automatically.
- A Russian-only forbidden rendering must not flag a row whose German translation
  is valid. Do not erase German, change the approved source, or duplicate the source
  row to force the restriction into the format. If the producer has now banned
  wording stored in an ordinary row, resolve its replacement before finalizing
  that row; do not publish it as a preferred unflagged translation.
- In a representable forbidden row, target cells hold the banned renderings, not
  the preferred ones. Put preferred replacements, labelled by language, in the
  explanation. A blank forbidden target is unsafe; do not export it.
- Do not combine flags or union them during deduplication. In particular,
  `read-only,forbidden` changes which wording is banned; no automatic combination.
- Existing flags from an input file are proposed rules, not automatically inherited
  restrictions, unless the producer explicitly authorized carrying them over.

Runtime reference: `weblate/checks/glossary.py:evaluate_glossary_terms` checks source
wording for read-only and target wording otherwise; exact matching bypasses
morphology but currently uses case-insensitive matching. Do not promise that `exact`
enforces letter case or that ordinary glossary entries always cause hard failures.

### 6. Serialize and verify

Serialize approved selections deterministically with `csv.writer`; no runtime model
calls in the converter. Keep the original file unchanged. Use a temporary directory
for normalization and checks. Preserve reusable converters only when requested or
needed to reproduce a delivered artifact; never create documentation just to log work.

Run the real loc-kit path, not a generic CSV validator. In a temporary script:

```python
import json
from pathlib import Path
from loc_kit_ingest.reader import read_sheets
from loc_kit_ingest.infer import infer_glossary_profile
from loc_kit_ingest.pipeline import run

# csv_path is the final CSV; work_dir is a fresh temporary directory.
sheet, rows = next(iter(read_sheets(Path(csv_path)).items()))
profile, diagnostics = infer_glossary_profile(sheet, rows, component="Glossary")
profile_path = Path(work_dir) / "profile.json"
profile_path.write_text(json.dumps(profile, ensure_ascii=False), encoding="utf-8")
assert run([Path(csv_path)], profile_path=profile_path,
           output=Path(work_dir) / "verified") == 0
```

The explicit profile is mandatory: automatic CLI inference otherwise takes the PO
path. Verify schema 2/TBX, intended source/targets, flat records, source explanation
mapping and flags mapping only when populated. An all-empty flags column is valid.
Confirm that the inferred languages exactly match the requested export; inference
excludes entirely empty columns and may refuse sparse ones. The current route needs
at least one populated target language. Do not invent translations, drop languages
silently or claim that a source-only/all-empty-target draft is upload-ready.

The pipeline parses, renders TBX and parses it back. Additionally inspect XML
entries, not line counts: term identity, values, explanations and flags must match
the approved CSV in every output language. Check supplied exceptional cases only;
never invent flagged terms to meet a test quota. Verify empty cells and meaningful
invisibles when present. Report actual failures and unresolved requirements.

### 7. Deliver a concise Russian report

Give the output path, source/target languages, term count and coverage; summarize
selection decisions and link research sources. State special-rule counts (zero is
normal), producer approvals, unsupported rules awaiting separate application, data
uncertainties and exact verification results. Separate import readiness from linguistic
approval. Do not bury decisions in raw logs or claim live upload verification after
only an offline run. Remove temporary verification artifacts.

## Common mistakes and stop conditions

- Brand -> automatic read-only: category is not authorization. Default remains blank.
- Unknown provenance -> erased translations: preserve evidence and resolve concrete conflicts.
- All short strings -> terminology: review meaning and agreed scope.
- Same source -> first translation plus unioned flags: resolve conflict before export.
- Matching field counts/round-trip -> proven parse: check actual alignment and key coverage.
- Weblate supports a flag -> this importer accepts it: verify both semantics and transport.
- Deadline -> guess ambiguous records or deliver an unexplained subset: finish all safely
  recoverable work, identify remaining blockers, and obtain approval for any reduced scope.
