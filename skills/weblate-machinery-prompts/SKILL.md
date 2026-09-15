---
name: weblate-machinery-prompts
description: "Use when a producer has a game loc kit (and maybe a glossary) and wants the prompt texts for an HCGameLoc Weblate project's automatic suggestions: Translator persona, Translator style, Language-specific instructions («Личность переводчика», «Стиль перевода», «Инструкции для конкретного языка»). Also use when reviewing or improving those texts. Triggers on \"промпты для машинери\", \"сделай промпты по локиту\", \"вот локит, нужны промпты\", \"persona и style для проекта\", \"language instructions\", \"настроить openrouter/litellm промпт\", \"machinery prompts\", \"MT prompt for a game project\", or a request to improve LLM suggestion quality for a project through its prompt configuration."
---

# Weblate machinery prompts

Turn a loc kit, and the glossary if there is one, into the three prompt texts a
producer pastes into the project's automatic-suggestion settings. The
deliverable is those three texts, ready to paste, plus a short note on where to
paste them.

The person on the other side is usually a producer, not a developer. They have
the kit and they know the game. They do not know engine names, project slugs,
repository paths, JSON or language codes, and they should never have to. Every
question they cannot answer stalls the session or produces a guessed answer,
which is worse than a conservative default the agent picks and states openly.

Every sentence in the prompt fields is paid on every request and is read by the
AI judge as well as by the translator. Write only what the product does not
already say and what the kit proves. The product facts behind every rule below
are in [references/mechanics.md](references/mechanics.md); read it before
writing the fields.

## Language and scope

Keep these instructions in English. Everything shown to the producer - the
questions, progress notes and the report - is plain Russian. Field values are
written in English (`persona`, `style`) or in the target language
(`language_instructions` blocks), never in the conversation language by default.

This skill is offline. Read the kit and the glossary. Do not query a live
Weblate instance, do not call an LLM, do not upload, and do not change any
project setting. If the user only asks to review or edit this skill, do not
start the producer workflow.

## Talking to the producer

Name things the way the Weblate screen names them: «Личность переводчика»,
«Стиль перевода», «Инструкции для конкретного языка», «Автоматические
предложения». Say «исходный язык», «языки перевода», «глоссарий», «подстановки
вроде {0}». Language names are Russian words («немецкий», «японский»), not codes.

Keep internal vocabulary out of the questions: `persona`/`style` as identifiers,
slug, engine, OpenRouter/LiteLLM as a choice, JSON, checkout, repository, path,
container, language codes, judge cache, MQM. The technical appendix of the
report is the one place these may appear.

Settle these yourself instead of asking:

| Tempting question | What to do instead |
|---|---|
| Which engine, OpenRouter or LiteLLM? | Nothing to decide: both services have the same three fields, and the paste instructions cover whichever one is set up. |
| Project slug or URL? | Not needed to write text. |
| Current values of the three fields? | Write a complete set. The paste note says the new text replaces what is in the fields, and that the producer can send the old text if they want it merged. |
| Path to the HCGameLoc checkout? | Not needed: the facts are in `references/mechanics.md`. The full gate runs only when the session is already inside a checkout. |
| Exact language codes? | Read the kit header and map columns to Weblate codes yourself (`zh_Hans`/`zh_Hant` kept distinct); show the producer names. |
| Is the glossary imported into the project? | Use the glossary file if one was given; otherwise say in the report that terms belong in a glossary, not in the prompt. |

## Workflow

1. **Get the kit.** If none is attached, ask for that and nothing else:
   «Пришлите, пожалуйста, локит (CSV, TSV или XLSX). Если есть глоссарий -
   его тоже.»
2. **Read and measure silently.** Run the evidence pass below before asking
   anything, so every question can arrive with a proposed answer.
3. **Ask once, briefly.** One message, at most three questions, only about what
   the kit cannot show. See "Questions" below.
4. **Write the three fields** following the field contracts.
5. **Check** as described in "Verification".
6. **Report** in the producer-first shape described in "Report".

If the producer answers «решай сам» or skips a question, take the conservative
default listed with that question and list it under assumptions in the report.
That never licenses inventing facts about the game.

## Questions

Ask only the questions whose answer the kit does not already make obvious, in
this order of value. Each one is a single decision in everyday words, with the
kit-derived answer offered first so the producer can simply confirm. If the
harness offers a multiple-choice question tool, every option is a plain answer
the producer could say out loud; never an option that asks them to type paths,
field contents or codes.

1. **Source language** - ask as confirmation. «Тексты изначально пишутся на
   русском, а остальные языки - перевод? По киту похоже на то.» It changes the
   prompt: the `style` rules about impersonal phrasing and added referents are
   licensed by a Russian source; with an English source re-derive them. Do not
   infer it from column order alone. Default if unanswered: the fully populated
   column the other columns were visibly translated from, stated as an
   assumption.
2. **How the game addresses the player.** «Как игра обращается к игроку:
   по-дружески, на "ты", или вежливо, на "вы"?» Offer what the shipped
   translations already do, if the kit has them. This becomes judge ground
   truth, so a wrong guess is the most expensive error in the skill. Default:
   follow the shipped corpus; with no corpus, informal in dialogue and neutral in
   interface text, stated as an assumption.
3. **Rudeness and profanity** - only if the kit contains rude or crude lines.
   «Грубость персонажей оставляем такой же, как в оригинале, или смягчаем?»
   Default: source strength, in both directions.

Add a question only when the kit leaves a real gap the prompt needs:
«На какие языки переводим?» when the kit has no target columns, or «Одной
фразой: что это за игра?» when neither strings nor glossary show genre and
setting. Never more than three questions in total.

Example of a complete first message:

> Локит прочитан: 1 240 строк, русский заполнен полностью, английский и
> немецкий - частично. Перед тем как писать промпты, три вопроса:
>
> 1. Оригинал текстов - русский, а английский и немецкий - перевод? По киту
>    выглядит так.
> 2. Как игра обращается к игроку: на «ты» или на «вы»? В немецком переводе
>    сейчас везде «du».
> 3. Грубые реплики персонажей (например, у Брана) оставляем такими же резкими
>    или смягчаем?

## Evidence pass over the kit

Measure before writing. Every prompt line must trace to one of these numbers or
to a producer answer; no line may rest on "games usually".

Collect, with a deterministic script over the kit (and over the already-shipped
target columns when the kit has them):

- row count; how many rows carry each markup family (`<color`, `<b>`, `<size>`,
  `<sprite>`, `<link>`), indexed placeholders (`{0}`), `%KEY%`, the conditional
  DSL (`[...|...]`), the `$` separator, and a literal `\n`;
- source length distribution: median, p90, max, and the count of rows at or
  below 20 characters - the share of pure UI labels versus prose;
- how many source rows end in `.`, `!`, `?`;
- explanation coverage, if the kit has an `Explanation` column;
- samples: 5-10 UI labels, 5-10 tooltips with placeholders, 5-10 dialogue lines,
  the longest rows, and rows whose shipped target visibly deviates (added
  subject, softened profanity, moved punctuation, broken tag, register drift).
  These deviations are the raw material for `style`: a rule that fixes an
  observed defect is worth its tokens, a rule that fixes an imagined one is not.

Also read the glossary file, if given: term count, which target columns are
populated, which flags are set, and which frequent kit names are missing from
it. A name that appears in dozens of strings and has no glossary entry is a
glossary task, not a prompt line.

## What never goes into a prompt

- A role sentence, a job title, or "you are..." in any field: the judge already
  has an annotator role (mechanics 1).
- Anything from the 28 fixed rules: placeholder integrity, markup preservation,
  glossary-flag semantics, "do not emit note/explanation", final punctuation.
- Instructions about `{0}`, `%KEY%` or `<color=...>`: they are masked
  (mechanics 5). A literal `\n` and a tightly used `$` are the exceptions worth
  stating.
- The glossary itself, or individual terms: they travel with the request.
- A hard length cap. The fixed prompt forbids omission and summarization, and
  the judge is told length is not an error. State the priority instead: a target
  that says less than the source is a defect, an over-long UI label is a layout
  risk.
- Unverifiable lore: a plot point, a character relation, a platform, an audience
  age, a marketing adjective. If the kit and the glossary do not show it, and the
  producer did not say it, it does not go in.
- Praise, meta-instructions about JSON, or anything about the reply format.

## Field contracts

### persona

Descriptive prose about the product, third person, no imperatives, 400-900
characters. It answers only: what the game is, what the strings are, what the
register is.

Include, in this order, and only when evidenced:

1. Genre, setting and the player's role, in one sentence.
2. What the text consists of - the actual mix measured in the evidence pass
   (short UI labels and numeric tooltips / dialogue / narration), because one
   component holds several registers and the judge otherwise measures prose with
   a label's ruler.
3. The register, ending with the explicit permission clause: "... and that is
   intended, not an error". Name what would otherwise be reported as a style
   defect: mild profanity, bluntness, deliberately plain wording, deliberate
   archaism.

Every proper noun in `persona` must be traceable to the glossary or to specific
kit keys; keep that trace in the report's appendix, not in the field.

### style

Project-wide, language-neutral policy, one rule per line, 800-1800 characters.
Admission test for a line: the judge could return a verdict on it, the
translator could act on it, and the evidence pass showed a real instance.

Rule families that usually earn their place:

- string role preserved: a label stays a label, a fragment stays a fragment, a
  spoken line stays spoken;
- no added subject, name or referent the source does not name (impersonal
  Russian is the usual source of this defect);
- quantities, prices, durations and levels exactly as stated, never rounded,
  converted or invented;
- profanity and rudeness at the strength the producer chose;
- names, factions, items, modes follow the glossary and stay identical across
  strings;
- unmasked engine syntax stated literally: the two-character `\n`, a tight `$`;
- no source-script leakage into a target that does not use that script;
- concision with the explicit "never drop content" priority.

Write each line as an observable requirement. "Keep tone appropriate" is
unusable; "keep mild profanity at source strength, do not soften and do not add
profanity the source lacks" is usable.

### language_instructions

A JSON object mapping Weblate language codes to one self-contained block per
language, each at most 1000 characters, written in that target language when the
rules are about its own typography and grammar. Content families, in order of
value:

1. Variant and region policy where two variants exist: which script, which
   vocabulary, and the explicit ban on the other one. Use `zh_Hans` and
   `zh_Hant` keys; a bare `zh` key resolves to Simplified and also serves as the
   fallback for `zh_Hant`, silently giving Traditional the Simplified rules.
2. Typography: punctuation width, quotation marks, ellipsis, spacing, digits and
   Latin runs.
3. Register and politeness level per string class (interface versus dialogue),
   anchored to the producer's answer and to the shipped corpus.
4. A genuine grammar trap around substituted values. Korean particles after
   `{0}` are the standard case: require `을(를)`, `이(가)`, `은(는)`, `와(과)` or
   a rewrite that needs no particle.
5. Script and name conventions: transliteration source (the glossary), long
   vowels, no invented honorifics.
6. Only for a target that expands relative to the source: a reminder to re-check
   labels that grew much longer.

Add a block only for a language the project translates into.

## Verification

Always, before the report: parse the language-instructions value as a JSON
object, and count characters of `persona`, `style` and every language block with
a script. Every block must be at most 1000 characters, `persona` and `style`
inside their ranges.

When the session already runs inside an HCGameLoc checkout with the dev
container up, also run [references/verification-gate.md](references/verification-gate.md).
Otherwise skip it silently in conversation and say in the appendix that only the
character and JSON checks ran.

## Report

The producer reads the top; a reviewer reads the appendix. In Russian, in this
order:

1. **Куда вставить** - three short steps: open the project, «Операции» ->
   «Автоматические предложения», press «Настроить» next to the service that is
   set up (OpenRouter or LiteLLM, whichever the list shows), paste, «Сохранить».
2. **The three texts**, each in its own copy-paste code block, headed with the
   screen label: «Личность переводчика», «Стиль перевода», «Инструкции для
   конкретного языка» (paste that block whole, braces included).
3. **Два предупреждения**, in plain words: the new text replaces whatever is in
   those fields now (send the old text if it should be kept); and after the
   change the AI check re-evaluates strings from scratch, which costs money, so
   paste before a big translation run, not in the middle of one.
4. **Что выбрано без ответа** - every default taken instead of an answer, one line
   each, so the producer can correct it.
5. **Технические детали** - clearly labelled as optional for the producer:
   one line of evidence per `style` rule and per `persona` claim (a count, a
   key, or a producer answer); character counts; the verification output; and,
   separately, what belongs in other artifacts rather than in the prompt -
   missing glossary terms, flags to propose, kit `Explanation` gaps.

## Related skills

- `preparing-weblate-loc-kits` produces the import file this skill measures and
  settles the source language with the producer. Its `Explanation` column is
  per-string context, a different artifact from the project-wide prompt.
- `game-glossary-builder` produces the glossary and its `flags` decisions. Route
  every term-level finding of this skill there instead of writing it into
  `style`.

## Red flags

- A question the producer cannot answer from knowing the game: engine, slug,
  path, field contents, codes, JSON.
- More than three questions, or questions asked before the kit was read.
- A question without a proposed answer when the kit suggested one.
- Second-person role assignment in `persona` or `style`.
- Lines that restate masked placeholders, markup, or the fixed prompt's rules.
- Terminology, term lists or per-term bans inside `style`.
- A hard character or ratio cap that can be satisfied by dropping content.
- Lore, platform, audience or tone claimed without a kit key, a glossary entry or
  a producer answer.
- A bare `zh` key, or a language block that depends on another block.
- Claiming the live project was verified: this skill never reads or writes a
  live instance.
