# Quality model: categories, severity, score, grade

The error typology and scoring are the MQM-Core game profile of the
developer-facing `weblate-lqa` skill, unchanged in substance. Only the parts
that assume a live instance were removed.

## Contents

1. Categories
2. Severity
3. Score
4. Coverage
5. Grade and what to tell the producer

## 1. Categories

Use the `category` value on the left in verdicts. The producer sees the
Russian name from the right-hand column in the fixes spreadsheet and report.

### Accuracy - `accuracy/`

| Category | Meaning | Russian name |
|---|---|---|
| `accuracy/mistranslation` | The target means something else: a mechanic inverted, subject and object swapped, a number distorted. | Искажён смысл |
| `accuracy/context_hallucination` | Translated from the key name instead of the source text (source «Стрелок», key `Unit_Driver`, target "Driver"). | Перевод по ключу, а не по тексту |
| `accuracy/omission` | Meaningful source content is missing. | Пропущен смысл |
| `accuracy/addition` | Content the source does not have: invented lore, a false instruction, a leftover working note. | Лишнее в переводе |
| `accuracy/untranslated` | Text left in the source language, unless it is a proper noun or brand. An empty target counts here. | Не переведено |

### Terminology - `terminology/`

A finding here needs glossary evidence: an entry from the glossary file the
producer supplied, or from the server glossary in server mode. Without a
glossary, terminology is unverified - never report it as clean.

| Category | Meaning | Default severity | Russian name |
|---|---|---|---|
| `terminology/glossary_violation` | The target does not use the approved glossary rendering. | Major; Critical when it renames an entity the player must recognise across screens or inverts a rule | Термин не по глоссарию |
| `terminology/inconsistent_term` | One entity (weapon, faction, currency, rank) is named differently across strings without a context reason. | Major; Minor when the variants are transparent synonyms in flavour text | Термин переведён по-разному |
| `terminology/acronym_leak` | An acronym from another language leaks into the target (English `AT` inside German text). | Major | Чужое сокращение |
| `terminology/inappropriate_register` | A word with the wrong domain meaning (cargo "unload" for infantry "disembark"). | Major | Слово не из той области |

A deliberate, context-driven variant is not a terminology defect: log it as
`fluency/style`, Neutral.

### Fluency - `fluency/`

| Category | Meaning | Russian name |
|---|---|---|
| `fluency/grammar_syntax` | A real grammar error a native proofreader would mark as wrong: case, agreement, broken word order. A correct sentence phrased differently from its neighbours is `style`, not grammar. | Грамматика |
| `fluency/spelling_orthography` | Typos, wrong capitalisation, wrong compound spacing, a look-alike letter from another alphabet. | Орфография |
| `fluency/register_tone` | Formal and informal address mixed (German Sie/du), a character's voice broken. | Сбит тон или обращение |
| `fluency/punctuation` | Missing or malformed punctuation, quotes or dashes against target-language rules. | Пунктуация |
| `fluency/style` | Correct and acceptable, but worth a note for the translator. Always Neutral, 0 points. | Стилистика |

### Game text - `game_engine/`

| Category | Meaning | Russian name |
|---|---|---|
| `game_engine/broken_placeholder` | A substitution (`{0}`, `{value}`, `%KEY%`, `%s`) is missing, altered or added. | Сломана подстановка |
| `game_engine/markup_damage` | Formatting tags (`<b>`, `<color=#...>`, `[shake]`, `[color=red]`) lost, altered or unbalanced. | Сломана разметка |
| `game_engine/keybinding_format` | A key or button token is malformed or not localised consistently. | Обозначение клавиши |
| `game_engine/line_break` | An engine line separator (`$`, a literal `\n`, a real line break) lost or added. | Сломан перенос строки |
| `game_engine/overflow_risk` | A short interface label grew far beyond its slot, when the file tells you the slot is tight (a note like «слот 96 px» or «кнопка»). | Может не влезть |

## 2. Severity

| Severity | Points | When | Russian label |
|---|---|---|---|
| `neutral` | 0 | Style remark, valid alternative. | Замечание |
| `minor` | 1 | A typo, a punctuation slip, slightly awkward phrasing, or a lost nuance - the player still understands the same thing and does the same thing. | Мелко |
| `major` | 5 | The player understands something different: a changed meaning, a distorted mechanic, a wrong term, an acronym leak, a significant grammar defect, mixed register. | Серьёзно |
| `critical` | 25 | Breaks the game or the player's trust: corrupted placeholder or markup, untranslated text, an inverted rule, a translation of the wrong thing, a leftover working note shown to the player. | Критично |

One verdict per defect. Two independent defects in one string are two verdicts.

## 3. Score

The script computes it; never compute or adjust it by hand.

```
penalty = minor x 1 + major x 5 + critical x 25
score   = max(0, 100 - penalty / reviewed_source_words x 100)
```

The denominator is the source words of the strings actually reviewed, not of
the whole file.

## 4. Coverage

- **Full**: every string in the file was read. Only this earns a grade.
- **Partial**: the listed strings were read - including the clean ones, not only
  those with a defect. The score is then a defect density over that part. It
  says how bad the found problems are, never how good the whole file is: the
  unread strings are unverified, not clean.

Terminology coverage is a separate axis. Glossary matching is surface stem
matching: it misses compounds, irregular forms and terms missing from the
glossary. A fully read file with no glossary still has unverified terminology.

## 5. Grade and what to tell the producer

| `grade` from the script | Headline in Russian |
|---|---|
| `blocked_critical` | Отдавать нельзя, пока не исправлены критичные ошибки. |
| `not_gradable_partial` | Итоговой оценки нет: проверена только часть строк. |
| `A` (score 95 and above) | Можно отдавать. Мелкие замечания - по желанию. |
| `B` (85 - 94.9) | Можно отдавать после исправления серьёзных ошибок. |
| `C` (70 - 84.9) | Отдавать нельзя: нужна полноценная вычитка. |
| `fail` (below 70) | Отдавать нельзя: перевод нужно переделывать. |

`blocked_critical` wins over everything: a single critical defect anywhere in
the reviewed part blocks the file, whatever the score and coverage.
