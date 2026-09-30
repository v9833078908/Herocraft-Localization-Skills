# Reading any pack

How to turn the output of `inspect_inputs.py` into decisions. The script gives
facts; everything here is judgement applied to those facts. When a rule below
does not settle a case, the evidence goes into a round-1 or round-2 question
with sample values - never a guess.

## Contents

- File roles
- Column destinations
- Per-language prompts
- Coverage: what to do when something is missing
- Lessons from the first real pack

## File roles

| Role | Typical evidence | Goes to |
|---|---|---|
| Strings | table with a unique identifier-like column and two or more language columns, hundreds to thousands of rows | `preparing-weblate-loc-kits` |
| Glossary | table with short cells, a term column, often category/meaning columns, tens to a few hundred rows; file or sheet named glossary/terms/глоссарий | `game-glossary-builder` |
| Prompts | text files that address a model («You are...», «Translate...», «TARGET LANGUAGE»), often one per language and near-identical (`groups` in the inspector output) | `weblate-machinery-prompts` as evidence |
| Style guide | prose about tone, form of address, typography, per-language rules | evidence for prompts and explanations |
| Game context | prose about the game: genre, characters, genders, mechanics, terminology | evidence for explanations, glossary explanations and prompts |
| Visual reference | screenshots, mockups | evidence for explanations only; not uploaded. Mention in the report that screenshots can be attached in Weblate by hand |
| Not relevant | lock files (`~$...`), `.DS_Store`, build artefacts | ignored, listed once |

A workbook can hold several roles, one per sheet. A file whose extension
disagrees with its content is classified by content. An archive is inspected
member by member. When two files claim the same role (two glossaries, two
kits), do not merge them silently: say what differs and ask in round 1.

## Column destinations

For every column of a strings table decide one destination. Use the
inspector's per-column profile: fill rate, uniqueness, identifier-likeness,
script mix, `language` (code, basis, whether the script agrees), and
`similar_to_language_columns`.

| Destination | Evidence | Where it lands |
|---|---|---|
| Key | unique non-empty values, identifier-like, no spaces or few | PO `msgid`, the string's identity |
| Language | header resolves to a language by code or name, and the content script agrees | its own PO file. Rewrite names to codes (`English` -> `en`, `PortugueseBrazil` -> `pt-BR`, `ChineseSimplified` -> `zh-Hans`, `ChineseTraditional` -> `zh-Hant`) and list the mapping in the report |
| Speaker | short repeated person names on dialogue rows | `Character`: the name only |
| Developer note | prose or counts **about** the string: usage, comment, context, description, screen, "N usages" | a note the translator and the model see (`Unit.note`, read-only in Weblate) |
| Explanation evidence | anything that explains where and how the string is used and is worth rewriting into a sentence: character limits, UI slot, addressee, what a placeholder stands for | `Explanation`, written by `preparing-weblate-loc-kits` rules |
| Not imported | another **version of** the string: debug copies, drafts, old text, a copy with other placeholders; empty columns; workflow status | nothing; counted in the report |

"About the string" against "another version of the string" is the decision
that matters most. Any one of these is evidence of a version of the string:

- the header says so: `Debug`, `Old`, `Draft`, `Previous`,
  `Старый текст`, `Черновик`, `Было`;
- the values equal or closely resemble a language column in a large share of
  rows (`similar_to_language_columns`);
- the values read as alternative wordings of the same strings rather than as
  information about them: the same script and length class as the source
  column, the same kind of text (button labels beside button labels), their
  own placeholders - even when a letter-level similarity is low (`Старт` beside
  `Начать`);
- text in another language's script where no language belongs (Russian drafts
  in an English-source kit).

The note reaches the translation model as context, and a stale version there
is believed. A column that tells where or how the string is used (a screen, a
count, a situation, a speaker's state) is about the string and goes in as a
note, whatever its script.

A workflow status column (approved, final, draft) is not a note. Report its
distribution; ask in round 2 only if it should change which translations are
imported, because by default every supplied translation is imported as is.

Legacy numeric IDs: keep as a note only when they help someone find the string
in the engine; rename a header that looks like a language code (`Id` reads as
Indonesian) - `preparing-weblate-loc-kits` covers this.

Trailing empty rows and columns are export artefacts: drop them and say how
many. A row empty in every language is quarantined by the kit skill, not
dropped silently.

## Per-language prompts

A set of per-language prompt files is usually one shared body plus a short
language block. The inspector's `groups` shows the shared-line ratio and which
lines differ per file. Treat the set as evidence for the three prompt fields,
through `weblate-machinery-prompts`, and sort every rule:

| Rule in the supplied prompt | Destination |
|---|---|
| Role sentence («You are a localization expert...») | dropped: the platform prompt has its own role, and the judge reads persona and style as an annotator |
| Placeholders, markup, output format, reply JSON, "return only the translation" | dropped: the platform prompt already fixes them, and a second output format contradicts it |
| A specific term and its rendering | glossary, not prompt: the glossary is sent with every request. A term missing from the glossary goes into the glossary proposal; keep it in a language block only until it is there |
| Game description, tone, audience, register, recurring meaning traps | persona and style, which the judge also reads |
| Typography, grammar, form of address, worked examples for one language | that language's block in `language_instructions`, at most 1000 characters, self-contained |
| A rule the supplied translations visibly break (a register the kit does not use) | a round-2 question: the rule becomes judge ground truth and will flag the existing translations |

Each language block must stand alone: the platform picks one block per target
language and never merges them, so `pt` and `pt_BR`, `zh_Hans` and `zh_Hant`
each need their own.

## Coverage: what to do when something is missing

| Situation | Action |
|---|---|
| No strings at all | Stop. A project without strings is not ready for localization. Ask for the export and offer the kit template from `preparing-weblate-loc-kits` (`assets/loc-kit-template.csv`) |
| Strings with the source language only | Ask for target languages in round 1; target columns stay empty and each language is still created |
| Several kits | One component per kit by default. Same keys in two kits is a round-1 question |
| Kit with several content sheets | Ask whether each sheet is a component; `splitting-loc-kits-into-components` if the boundary is not the sheet |
| No glossary | Round-1 question: build with `game-glossary-builder` or publish without one |
| Glossary in an odd shape (per-language files, extra columns, a sheet inside the kit) | `game-glossary-builder` normalizes it; its explanation column can combine category and meaning |
| Glossary with blank translations | Blank stays blank; the report lists the terms. A blank target means the term does not reach the model for that language |
| No prompts, but a context document or style guide | `weblate-machinery-prompts` from the kit plus that document |
| Nothing but the kit | `weblate-machinery-prompts` from the kit alone; that is its default mode |
| No explanation material anywhere | Explanations only where the kit's own rows prove usage (neighbour rows, key families, placeholders); an empty cell beats a guess |
| Unreadable file (encrypted, proprietary binary, scanned PDF without text) | Say which and ask for a readable export; never fabricate its content |

## Lessons from the first real pack

- Most of the rows in the exported workbook were trailing empty rows, and
  several empty columns trailed the header row: export artefacts, not data.
- A usage column ("3 usages", "NO USAGES since ...") was a note about the
  string. A debug column differed from the source in about two thirds of the
  rows - drafts in another language, stale wording, other placeholders - and
  was not imported once the producer saw those numbers.
- Fifteen per-language prompt files of about 11 KB each shared everything but
  an eight-line language block. They became a persona and a style of 1-2 KB
  together and fifteen language blocks of 200-900 characters.
- The glossary carried battle shouts as terms («БОСС!!!»), a season name the
  context document forbade, and result text in place of a button label. Fixed
  where the kit proved the rendering, cleared where it did not.
- Plural blocks such as `{amount[Night|Nights]}` are masked as one placeholder
  by the platform checks, so every correct localized plural is flagged. Report
  such strings to the team; the pack cannot fix it.
