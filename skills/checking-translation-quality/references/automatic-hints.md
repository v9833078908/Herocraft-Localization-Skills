# Automatic hints: what each one means

`scripts/lqa.py read` writes `hints.json`. Every hint is a hypothesis about one
string, never a finding. Look each one up here, read the string, and either
turn it into a verdict or reject it. Rejected hints are not reported.

Several hints on one string can describe one defect (Russian text copied into
an English target fires both `same_as_source` and `cyrillic_in_target`). One
defect is one verdict, scored once.

Hint names are internal. Never show them to the producer.

| Hint | What the script compared | Usually a real defect when | Usually fine when | Verdict if real |
|---|---|---|---|---|
| `empty_target` | The source has text, the target is empty. | Always, if the file is meant to be final. | The producer asked to check only translated strings: then count, do not score. | `accuracy/untranslated`, critical; minor when the source has no words, only punctuation or symbols ("...") |
| `same_as_source` | Target identical to source, and the source has letters outside placeholders. | The source language was copied over (Russian text in an English file). | A proper noun, brand, model name, a word that is genuinely the same in both languages ("No" in English and Spanish), or a string made only of symbols. | `accuracy/untranslated`, critical |
| `placeholder_mismatch` | The multiset of `{...}`, `%KEY%` and `%s`-style tokens. | A token is missing, renamed, translated, or duplicated. | Reordering alone never triggers this hint. | `game_engine/broken_placeholder`, critical |
| `markup_mismatch` | The multiset of `<...>` tags. | A tag is lost, its value changed (`<color=#FFCC00>` -> `<color=#FFCC0>`), or a closing tag is missing. | Rare; almost always real. | `game_engine/markup_damage`, critical |
| `bracket_mismatch` | The count of `[` and `]`. | Square-bracket tags such as `[shake]...[/shake]` or `[color=red]` were dropped, or a `[...|...]` substitution was broken. | Ordinary prose brackets that the translation reasonably rephrased. | `game_engine/markup_damage`, critical |
| `line_break_mismatch` | Counts of `$`, a literal two-character `\n`, and real line breaks. | An engine separator was lost or added, so lines merge or split in game. | `$` used as a currency sign; a real line break that only wrapped long prose; a line break only at the very start or end of the source. | `game_engine/line_break`, major; critical when the separator structure of a dialogue is destroyed |
| `number_missing` | Numbers in the source (placeholders and tags removed, `,` and `.` treated alike) must appear in the target at least as often. | A price, amount, level or duration was changed or dropped. | A number written as a word, an ordinal restructured ("24th" vs "24."), a date format change. | `accuracy/mistranslation`, major; critical if it changes a price or a game rule |
| `cyrillic_in_target` | Cyrillic letters in a target language that does not use Cyrillic. | Untranslated fragment, a leftover working note, or a look-alike letter (Cyrillic «С» in "Сaw") that breaks fonts and search. | Never fine in a non-Cyrillic language. | untranslated or leftover note: `accuracy/untranslated` or `accuracy/addition`, critical; a single look-alike letter: `fluency/spelling_orthography`, major |
| `glossary_term_missing` | The source contains a glossary term; the target contains none of its approved translations (stem match, so inflected forms count). | A different word was used for a named entity. | An inflected or compound form the stem match could not see; a pronoun replacing the name; the glossary term appears in the source only as part of a longer different word. | `terminology/glossary_violation`, major |
| `glossary_term_varies` | One glossary term is rendered with two or more approved variants across the file. | The player sees one entity under different names. | The glossary itself allows variants for different contexts (singular and plural, a short UI form). | `terminology/inconsistent_term`, major |

## What hints cannot see

A clean hint list proves nothing about meaning. Mistranslation, wrong tone,
translation by key, grammar, invented content and most terminology problems are
found only by reading the strings. The hints exist so that the mechanical
defects that break a game are never missed, not to replace the reading.
