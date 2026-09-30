---
name: setting-up-weblate-projects
description: "Use when a producer wants a new game created in HCGameLoc Weblate from whatever localization materials they have - a loc kit, glossary, per-language prompts, style guide, game description, screenshots, in any format and any completeness - and needs it published ready to translate: project, strings component, glossary, string explanations and automatic-suggestion prompts. Asks for the Weblate API key up front, asks the producer once, routes the work to preparing-weblate-loc-kits, splitting-loc-kits-into-components, game-glossary-builder and weblate-machinery-prompts, then publishes through the API and verifies. Triggers on \"заведи проект в веблейт\", \"создай проект локализации\", \"вот пак от команды, сделай проект\", \"залей локкит в weblate\", \"подготовь проект к локализации\", \"новая игра, нужен проект в веблейте\", \"set up a Weblate project from this pack\", or a producer handing over a folder of localization files for a new game."
---

# Setting up Weblate projects

Turn a pack of localization materials into a live HCGameLoc project that a
translator can open and start working in. The deliverable is on the server,
not in a file:

- a new project with a strings component: every string, every supplied
  translation, developer notes and a useful `Explanation` per string;
- a glossary component with terms, translations and explanations;
- the project's automatic-suggestion prompts (persona, style,
  per-language instructions);
- a Russian report of what was created, what was decided and what the team
  still has to fix.

This skill is an orchestrator. The format rules for each artifact live in
sibling skills and are not repeated here; this skill decides which of them the
pack needs, asks the producer once instead of four times, carries the answers
between them, converts their results into upload files and publishes.

The person on the other side is a producer, not a developer. They have the
materials and a Weblate account, and nothing else: no repository, no
`loc_kit_ingest`, often no Python packages beyond `python3`. Everything the
skill runs uses only the Python standard library.

## Language and scope

Keep these instructions in English. Everything shown to the producer -
questions, progress notes, the plan, the report - is plain Russian. Language
names are Russian words («немецкий»), not codes. Machine identifiers (column
headers, codes, flags) stay as they are.

This is the one skill in the set that writes to a live server. It writes only
after the producer has seen the publication plan and answered «да», it only
creates a new project, and it never modifies a project it did not create in
this run (the only exception is `--resume` of its own interrupted run). It does
not translate empty cells, does not invent game facts and does not pay for
model calls; the server makes one test call to the model when the prompts are
saved, and the plan says so.

If the user only asks to review or edit this skill, do not start the workflow.

## First message: the API key

Publication needs three things the materials cannot give. Ask for them in the
very first reply, before any analysis, so the producer can arrange access
while the preparation runs:

> Чтобы в конце создать проект на сервере, мне понадобится:
>
> 1. **API-ключ вашей учётной записи Weblate.** Он в профиле: аватар ->
>    «Настройки» -> вкладка «Доступ к API» (прямая ссылка:
>    https://l10n.herocraft.com/accounts/profile/#api). Ключ можно прислать сюда или назвать
>    переменную окружения либо файл, где он уже лежит. Я использую его только в
>    командах публикации и никуда не записываю.
> 2. **Право создавать проекты.** Если у вас его нет, сервер откажет на первом
>    же шаге; попросите администратора выдать роль «Добавление новых
>    проектов» (Add new projects).
> 3. **Адрес сервера**, если это не https://l10n.herocraft.com.
>
> Пока ключа нет, я разбираю материалы: ключ нужен только на последнем шаге.

If no materials came with the request, add one line asking for them: «Пришлите
папку или файлы от команды игры - строки, глоссарий, промпты, описание игры,
что есть.» If they did, continue straight to the inventory in the same turn.

Key handling:

- Pass the key to `publish.py` through the environment of that one command,
  or through `--env-file` when the producer names a file. Never write it into a
  file you create, a report, a log or a later message; never echo it back.
- If the producer pasted the key into chat, do not repeat it; refer to it as
  «ваш ключ».
- A rejected key or a refused project creation is a stop, not a workaround:
  say what the server answered in one plain sentence (see
  [references/publish.md](references/publish.md)) and wait.

## Workflow

1. **Key request** - the first message above.
2. **Inventory** - understand every file silently. Section "Inventory".
3. **Round 1: blockers** - one message, only what the pack cannot answer.
   Section "Questions".
4. **Prepare** - route to the sibling skills with the decisions attached.
   Section "Routing".
5. **Round 2: data problems** - one decision table for what preparation found.
6. **Build** the upload folder and run the readiness check.
7. **Publish** - preflight, plan, explicit «да», run, verify.
8. **Report** - on disk and a short chat summary.

Keep a work folder `weblate-setup/` next to the materials (or in the current
folder when the materials are scattered). Never modify an input file. Record
every producer answer and every default you took in `weblate-setup/decisions.md`
as you go: it is what you hand to sibling skills, what makes an interrupted
session resumable, and the source of the report's «Решения» section.

## Inventory

Run the inspector over everything the producer gave:

```sh
python3 <skill-dir>/scripts/inspect_inputs.py <paths...> --export-dir weblate-setup/sheets
```

`<skill-dir>` is the directory containing this `SKILL.md`. The script prints
facts - encodings, sheets, row-width histograms, per-column profiles, groups of
near-identical text files - and exports every table sheet as plain UTF-8 CSV so
the rest of the work never needs a spreadsheet library. It never decides
anything; you do, with [references/inventory.md](references/inventory.md):

- give every file a role: strings, glossary, prompts, style guide, game
  context, visual reference, or not relevant;
- give every column of every string table a destination: key, language,
  speaker, developer note, explanation evidence, or not imported;
- build the coverage matrix and look up what to do for every gap.

Column meanings are decided from the data, not asked. A `Usage`, `Comment` or
`Context` column that describes the string becomes a developer note without a
question; a `Debug` or `Old text` column that turns out to be another version of
the string itself is not imported, because the note reaches the translation
model and a stale draft there misleads it. Ask only when the values genuinely
do not reveal the meaning, and then show three sample values with the question.

## Questions

Everything the producer is asked arrives in at most three messages for the
whole run: round 1 now, round 2 after preparation, the publication «да» at the
end. A sibling skill that has its own interview does not run it: this skill
asks on its behalf, once, and records the answers in `decisions.md`.

Round 1 contains only real blockers, each with the answer the pack suggests,
at most five questions:

1. **Source language.** Always asked, never assumed: it is immutable once the
   component exists. Put Russian and English on the table with the costs the
   sibling skill `preparing-weblate-loc-kits` states for each, and add the
   evidence from the pack («в ките английский заполнен полностью и стоит
   первым, глоссарий тоже от английского»).
2. **Project name.** Offer the game title from the pack; the slug is derived
   (lowercase, hyphens) and shown, not asked.
3. **Target languages** - only when the kit has no target columns or when a
   header is regionally ambiguous and the pack does not settle it (a lone
   `Portuguese` or `Chinese`; a `Portuguese` beside a `PortugueseBrazil`
   settles itself).
4. **Components** - only when the pack carries a grouping signal (several
   sheets, several kits, a group column) or more than a few thousand strings.
   Default: one strings component per kit.
5. **Glossary** - only when none was supplied: build one from the kit with
   `game-glossary-builder` (default when the kit names characters, items or
   places), or publish without it.

Everything else that a sibling would ask is answered from the materials when
they contain it - the player's form of address and the rudeness policy from
supplied prompts or a style guide, the game's genre from a context document,
glossary exceptions from explicit rules in the materials. Only what the
materials leave open goes into round 1, and only if it blocks work; the rest is
a stated default.

Defects in the source text that the inventory already shows - a register the
style guide forbids, a count glued to a noun that will not inflect («{0}
досок»), a number typed into text that looks like a lost placeholder, broken
markup - go into the round-1 message too, as information rather than
questions. The team can fix the source before import, which is far cheaper
than afterwards: every source edit later reopens that string in every
language. Publication does not wait for these fixes unless the producer says
so.

If the producer answers «решай сам» or skips a question, take the default given
with it, record it in `decisions.md` and list it in the report. That never
licenses inventing game facts.

Round 2 comes after preparation, as one table: every conflict or suspected error
found in the data, what it affects, and the recommended action. The default
recommendation is the one this skill applies when told «как рекомендуешь»:

- suspected errors in supplied translations are listed for the team, never
  silently fixed - they are the team's text;
- a glossary entry that contradicts the pack's own rules or its own strings is
  different, because the glossary is enforced on every future translation:
  replace it with the rendering the kit proves, or clear the cell when nothing
  proves a better one;
- noise columns and dropped rows are reported with numbers, not asked about,
  unless they change which strings exist.

## Routing

Use the sibling skills; do not reimplement their rules. In Claude Code invoke
them with the Skill tool by name; in other agents read
`<skills dir>/<name>/SKILL.md` next to this skill's directory. If a sibling is
not installed, stop and ask the producer to run the collection's
`install.sh`; do not improvise its contract from memory.

Tell each sibling, in the request that starts it:

- the path to `weblate-setup/decisions.md` - its answers are the producer's
  answers; ask nothing that is already there;
- the exported CSV of its input (from `weblate-setup/sheets/`), not the
  original workbook;
- where to write its result inside `weblate-setup/`;
- that its report goes into this skill's final report instead of being
  delivered separately;
- when `loc_kit_ingest` cannot be imported (the producer has no HCGameLoc
  checkout), its gate is replaced by `build_upload.py` and `build_upload.py
  check` below. The replacement renders the same PO and TBX files as the
  importer and parses them back cell by cell.

| Need | Sibling | Result it must leave |
|---|---|---|
| strings table in the import contract | `preparing-weblate-loc-kits` | `weblate-setup/<name>.import.csv` (+ quarantine CSV) with `Explanation` filled from evidence |
| one kit becomes several components | `splitting-loc-kits-into-components`, then `preparing-weblate-loc-kits` per part | one import CSV per component |
| glossary supplied in any shape, or to be built | `game-glossary-builder` | `weblate-setup/glossary.csv` in its output contract |
| prompts, from supplied prompts, a style guide, a context document or the kit alone | `weblate-machinery-prompts` | `weblate-setup/machinery.json`: `{"persona", "style", "language_instructions": {code: text}}` |

Supplied per-language prompts are evidence for the three fields, not text to
paste: [references/inventory.md](references/inventory.md) says how to split a
shared body from per-language blocks and what to drop. Terms found in prompts
belong in the glossary.

Order: strings first (their languages fix the project's language set), then
glossary and prompts. The glossary and the prompts can be prepared in parallel
by subagents when the agent supports them; reconcile afterwards so a term lives
only in the glossary, and a glossary fix from round 2 is reflected in a prompt
that mentioned it.

The engine is always `openrouter`: it serves translation suggestions, while
LiteLLM serves only the AI judge, which the instance administrators configure
for the whole server. The judge reads the persona and style from the
`openrouter` configuration, so nothing else is needed per project.

## Build

```sh
S=<skill-dir>/scripts/build_upload.py
python3 $S project   --name "<Название>" --slug <slug> --out weblate-setup/upload
python3 $S strings   weblate-setup/<name>.import.csv --source-lang <src> --name Strings --slug strings --out weblate-setup/upload
python3 $S glossary  weblate-setup/glossary.csv --source-lang <src> --out weblate-setup/upload
python3 $S machinery weblate-setup/machinery.json --out weblate-setup/upload
python3 $S check     weblate-setup/upload
```

Run `strings` once per component with its own name and slug. Every command
prints a JSON summary; exit code 2 prints a JSON `error` naming the rows or
fields to fix - fix the prepared CSV (or send it back to the sibling that
produced it) and rerun. Never edit the generated ZIP files by hand. `check`
passing is the readiness gate; its numbers (strings, languages, notes,
explanations, terms) are the ones the plan and the report quote.

## Publish

Full API facts, error meanings and recovery are in
[references/publish.md](references/publish.md). The sequence:

```sh
P=<skill-dir>/scripts/publish.py
python3 $P plan      weblate-setup/upload
python3 $P preflight weblate-setup/upload --base-url <url> --token-env <VAR> [--env-file <file>]
python3 $P run       weblate-setup/upload --base-url <url> --token-env <VAR> [--env-file <file>]
```

1. `preflight` is read-only: the key works, the project does not exist yet,
   every language code exists on the server. Resolve anything it reports
   before showing the plan.
2. Show the producer the plan in Russian: server, project name and link,
   what will be created with the numbers from `check`, that reviews are
   switched on (the Hero Craft rule for every new project: supplied
   translations arrive as translated and wait for a reviewer's approval), that
   the prompts save makes one test call to the model, and that nothing is sent
   until they answer. Wait for an explicit «да». An earlier «делай всё сам» covers
   decisions, not this step, unless the producer said in so many words that
   publication needs no confirmation.
3. `run` creates everything in a fixed order and verifies at the end. If it
   stops with an error, report it in plain Russian and rerun with `--resume`
   once the cause is fixed: every step checks what already exists.
4. Read the `verify` block: `problems` must be empty. Anything else goes into
   the report, never smoothed over.
5. Access control cannot be read or set through the API. Give the producer the
   link `<url>/access/<slug>/` («Контроль доступа») and ask them to check that
   the project is «Приватный».

## Report

Write `weblate-setup/ОТЧЁТ.md` in Russian, in this order:

1. **Итог** - link to the project and a table: строк, языков, пояснений,
   заметок, терминов глоссария, языков в промптах.
2. **Что проверить руками** - access control, and anything `verify` reported.
3. **Что сделано с материалами** - per file its role; per column where it went
   and why; what was not imported, with counts and the reason.
4. **Решения** - producer answers and defaults taken without an answer, one
   line each, from `decisions.md`.
5. **Что исправить команде** - data problems left as they are: suspected
   translation errors, missing glossary translations, lost line breaks,
   duplicate or odd keys, anything a check will flag later - each with keys or
   examples.
6. **Технические детали** - the upload folder, `check` and `verify` output
   summaries. This is the one section where codes and file names may appear.

In the chat give the link, the headline numbers, what to check by hand and the
report path. Do not paste the report.

## Red flags

- Anything written to the server before the producer saw the plan and said «да».
- The API key repeated, logged or written to a file.
- A question the materials already answer, a column meaning asked when its
  values show it, or a sibling's interview run on top of this one.
- The source language inferred instead of asked.
- A sibling skill's rule rewritten here from memory instead of the sibling
  being used.
- A draft or debug copy of the string imported as a developer note.
- Terms restated in the prompts, or per-language prompts pasted whole.
- Supplied translations silently «fixed», or empty cells translated.
- A success reported while `verify.problems` is not empty, or access control
  claimed as checked.
- A second project created because the first run failed, instead of `--resume`.
