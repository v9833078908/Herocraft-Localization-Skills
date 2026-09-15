---
name: checking-translation-quality
description: "Use when a producer has a downloaded translation file of a game (XLSX, CSV, TSV, PO, XLIFF or JSON exported from Weblate, or a loc kit with filled-in language columns) and wants to know whether the translation is good enough to ship: a quality check with a score, a plain verdict, and a spreadsheet of fixes for the translator. Triggers on \"проверь качество перевода\", \"оцени перевод\", \"посмотри, нормальный ли перевод\", \"можно ли отдавать перевод\", \"проверь файл локализации\", \"вот выгрузка, проверь\", \"LQA\", \"оценка локализации\", \"check translation quality\", \"is this translation ready to ship\", or a producer attaching a translated file and asking what is wrong with it. Prefer this over weblate-lqa whenever the person works with a file on their computer rather than with the Weblate API."
---

# Checking translation quality

Read a translation file the producer downloaded, find what is wrong with it,
and answer the question the producer actually has: can this be shipped, and
if not, what exactly has to be fixed. The deliverables are a short report and a
spreadsheet of fixes the producer can forward to the translator.

The person on the other side is a producer, not a developer. They work in the
Weblate interface, they know the game, and they have a file. They do not know
file-format internals, API calls, check names or scoring formulas, and they
should never need to. They do not change the platform either, so the report
contains no advice about settings, flags, automatic checks, prompts or
integrations - only what is wrong in the text and how the text should read.

## Language and scope

Keep these instructions in English. Everything shown to the producer - the
questions, progress notes, the report and the spreadsheet - is plain Russian.
Proposed fixes are written in the target language.

The file is the input. Read it with `scripts/lqa.py`, which needs only Python 3
and no extra packages. Do not upload the file anywhere, do not call an LLM
service, do not change anything on a server. The one exception is server mode
below, and only when the producer offers a link and an API key themselves.

If the user only asks to review or edit this skill, do not start the check.

## Talking to the producer

Say «строка», «оригинал», «перевод», «ключ», «подстановки вроде {0}», «теги
разметки», «глоссарий», «балл качества». Language names are Russian words
(«немецкий»), not codes.

Keep out of the conversation and the report: unit, hint names, check IDs, JSON,
work folder, MQM (except one line in «Как считался балл»), severity codes,
command lines, and anything about how Weblate is configured.

Settle these yourself instead of asking:

| Tempting question | What to do instead |
|---|---|
| Which file format is it? | Run the script; it detects the format. |
| Which column is the key / the note? | The script finds `key`, `context`, `Explanation`, `developer_comments` by name. |
| Which language is the translation? | PO and XLIFF headers and kit column names give it; Weblate's XLSX and CSV downloads do not. Then take it from the file name or from the translated text itself and pass `--lang`. Ask only if the text leaves it unclear. Name the language in Russian. |
| Where to save the results? | Next to the checked file (see "Deliver"). |
| Which categories and severities apply? | Decide from [references/quality-model.md](references/quality-model.md). |

## Workflow

1. **Get the file.** If none is attached, ask for it and nothing else (see
   "First message without a file").
2. **Read silently.** Run `read`, handle any decision it returns, look at the
   summary.
3. **Ask once, briefly** - only what the file cannot answer. See "Questions".
4. **Review** every automatic hint, then read the strings in scope.
5. **Score** with the script.
6. **Deliver** the report and the fixes spreadsheet.

If the producer answers «решай сам» or skips a question, take the default given
with that question and list it in the report under «Что выбрано без ответа».

## First message without a file

> Пришлите, пожалуйста, файл перевода, который хотите проверить. Проще всего
> скачать его в Weblate: откройте нужный язык, «Файлы» -> «Настроить
> скачивание», формат XLSX. Если есть глоссарий проекта файлом - пришлите и его,
> тогда я проверю ещё и термины.
>
> Если у вас есть API-ключ Weblate, можно без файла: пришлите ссылку на
> страницу языка, и я сам прочитаю строки с сервера. Это необязательно, файла
> достаточно.

Ask about the API key only here, when there is no file. With a file attached,
the file is the input and the key is never mentioned.

## Read

```sh
python3 <skill-dir>/scripts/lqa.py read <file> [--lang de] [--glossary <glossary>]
```

`<skill-dir>` is the directory containing this `SKILL.md`. The command prints a
JSON summary and writes `units.jsonl` (one string per line, with `id`, `key`,
`source`, `target`, `note`) and `hints.json` into a work folder under the
system temp directory; the summary names it.

Exit code 2 prints a JSON `error` - a decision, not a crash:

| `error` | What it means | What to do |
|---|---|---|
| `choose_source_column` | A table with several language columns. | Ask which column is the original. Offer the column that looks like the source, but never decide it from column order alone. Then rerun with `--source-col`. |
| `choose_target_column` | Several translated columns and no `--lang`. | Ask which language to check, or check each in turn if the producer wants all. Rerun with `--target-col` or `--lang`. |
| `need_language` | No language code in the file. | See the language row in the table above, then rerun with `--lang`. |
| `choose_sheet` | A workbook with several filled sheets. | If the sheet names make the choice obvious, pick and state it; otherwise ask. Rerun with `--sheet`. |
| `need_source_file` | The file holds keys and translations but no original text (a raw JSON or PO file of one language). | Ask for the same download in the original language, then rerun with `--source-file <that file>`. |
| `choose_glossary_columns` | The glossary columns were not recognised. | Rerun with `--glossary-source-col` and `--glossary-target-col` using the header names printed. |
| `unsupported_format`, `file_not_found`, `no_strings_found` | Nothing usable. | Tell the producer in one sentence and ask for an XLSX download. |

The work folder name includes the language code. After a rerun, use the folder
the latest summary printed.

A ZIP download holds one file per language: unpack it
(`python3 -m zipfile -e <zip> <folder>`) and run `read` on the language asked.

### Server mode (only when offered)

When the producer sends a link to a language page and an API key:

```sh
WEBLATE_API_TOKEN=<key> python3 <skill-dir>/scripts/lqa.py read-server "<link>"
```

The key goes into that one command's environment. Never write it into a file,
the report, or a later message. Server mode also picks up the project glossary
for that language by itself. Everything after reading is identical to file
mode. If the link or key does not work, say so once and ask for the file.

## Questions

Ask only what blocks the review, in one message, at most three questions, each
with a proposed answer. When nothing blocks it, do not stop to ask - start
reviewing.

1. **Which language** - only when the file holds several translations.
   Default: all of them, one after another.
2. **Glossary** - never a reason to stop. When none was given and you are
   already asking something else, add «Если есть глоссарий проекта файлом -
   пришлите, проверю ещё и термины.» Otherwise review without it, report
   terminology as unverified, and offer the glossary check at the end of the
   chat message.
3. **All strings or a part** - only when the file has more than 1000 strings.
   «В файле N строк. Проверить все (это дольше, зато будет итоговая оценка) или
   только часть (быстрее, но итоговой оценки не будет)?» Default: all strings.
   Up to 1000 strings, check all without asking.

Do not ask about tone, audience or style policy: inconsistency is visible in the
file itself, and the producer asked for a check, not a style guide.

## Review

Read [references/automatic-hints.md](references/automatic-hints.md) and
[references/quality-model.md](references/quality-model.md) first.

1. **Hints.** Open every hint in `hints.json`, read its string, and confirm it as
   a verdict or reject it. A hint is a hypothesis, never a finding.
2. **Strings.** Read `units.jsonl` in batches, in order, every string in scope.
   Use `note` (character, slot size, screen) as context. Look for what the
   hints cannot see: meaning, omissions and additions, translation by key,
   grammar, register, character voice, terminology against the glossary,
   leftover working notes.
3. **Track coverage honestly.** Record which strings you actually read,
   including the clean ones. If the session cannot finish all of them, the
   check is partial - say so, never round it up to full.

Write the verdicts file into the work folder:

```json
{
  "review_scope": {"coverage": "full"},
  "verdicts": [
    {
      "unit_id": 14,
      "key": "TIP_REPAIR",
      "severity": "critical",
      "category": "game_engine/broken_placeholder",
      "problem": "Потеряна подстановка {1}: игрок не увидит количество монет.",
      "suggestion": "Die Reparatur kostet {0} Bretter und {1} Münzen."
    }
  ]
}
```

- For a partial check use `"review_scope": {"reviewed_unit_ids": [1, "2-400"]}`;
  ranges are inclusive.
- `unit_id` and `key` are copied from `units.jsonl`, never typed from memory; the
  script rejects a verdict whose key does not match its id. For a string with
  an empty key, give `source` (its exact original text) instead of `key`.
- `problem` is Russian, one or two sentences, and says what the player would
  experience. `suggestion` is the full corrected string in the target language.
  If you are not confident enough in the target language to propose a fix, say
  so in `problem` and leave `suggestion` empty rather than guessing.

## Score

```sh
python3 <skill-dir>/scripts/lqa.py score --workdir <work folder> \
  --verdicts <work folder>/verdicts.json --fixes-xlsx "<fixes path>"
```

It prints `coverage`, `reviewed_units`, `counts`, `mqm_score` and `grade`, and
writes the spreadsheet. Use these numbers as printed; never recompute or round
them into a different grade. If it returns `invalid_verdicts`, fix the listed
verdicts and rerun.

## Deliver

Save next to the checked file (in server mode, in the current folder):

- `<file name>-проверка-<язык>.md` - the report;
- `<file name>-правки-<язык>.xlsx` - the fixes spreadsheet from `score`.

`<file name>` is without its extension, `<язык>` is the Russian word:
`ui-de.xlsx` gives `ui-de-проверка-немецкий.md` and `ui-de-правки-немецкий.xlsx`.

The report, in Russian, in this order:

1. **Итог** - one sentence from the grade table in
   [references/quality-model.md](references/quality-model.md), then a small
   table: проверено строк (N из M), балл качества, критичных, серьёзных,
   мелких.
2. **Что исправить обязательно** - every critical and serious problem: ключ,
   оригинал, перевод, что не так, как исправить. Past 30 items, show the first
   30 and point to the spreadsheet for the rest.
3. **Мелкие замечания** - the count and up to five typical examples.
4. **Термины** - which glossary was used and what was found; or, without a
   glossary, one sentence saying terminology was not checked. Names that recur
   in the file but are missing from the glossary go here as a short list.
5. **Что не проверено** - unread strings in a partial check; that nobody saw the
   strings in the game, so whether text fits on screen is unknown unless the
   notes gave slot sizes; that the check was done by an AI agent, so disputed
   places are worth showing to a native speaker before release.
6. **Что выбрано без ответа** - defaults taken instead of an answer, one line
   each. Omit the section if there were none.
7. **Как считался балл** - two lines: 1 point for a minor problem, 5 for a
   serious one, 25 for a critical one, per word of the checked original, taken
   from 100 (MQM methodology); a single critical problem blocks the file
   whatever the score.

In the chat, give the headline, the counts, and both file paths. Do not paste
the whole report into the chat.

## Related skills

- `game-glossary-builder` builds the glossary this check compares terms
  against. When terminology was unverified for lack of a glossary, it is the
  way to get one.

## Red flags

- A verdict from a hint nobody read, or a hint reported as a finding.
- "Terminology is fine" with no glossary.
- A grade for a partial check, or a partial check described as full.
- A score or grade computed by hand instead of taken from `score`.
- Advice about flags, check settings, prompts, the AI judge or the API in the
  report.
- The API key asked for when a file was already given, or the key repeated,
  logged or written to disk.
- Internal words in front of the producer: unit, hint, JSON, MQM category codes.
- A proposed fix that changes placeholders, tags or numbers of the original.
