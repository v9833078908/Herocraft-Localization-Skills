---
name: weblate-machinery-prompts
description: "Use when writing or reviewing the automatic-suggestion prompt fields of an HCGameLoc Weblate project (Translator persona, Translator style, Language-specific instructions) from a game loc kit and its glossary. Triggers on \"промпты для машинери\", \"persona и style для проекта\", \"language instructions\", \"настроить openrouter/litellm промпт\", \"machinery prompts\", \"MT prompt for a game project\", or a request to improve LLM suggestion quality for a project through its prompt configuration."
---

# Weblate machinery prompts

Write the three prompt fields of one project's automatic-suggestion engine from
the evidence in its loc kit and glossary. The fields are `persona`, `style` and
`language_instructions` on `/machinery/<project>/<engine>/`, where `<engine>` is
`openrouter` or `litellm`.

Every sentence you write is paid on every request and is read by the AI judge as
well as by the translator. Write only what the product does not already say and
what the kit proves.

## Language and scope

Keep these instructions in English. Interview, progress notes and the final
report go in plain Russian: say "личность переводчика", "стиль перевода",
"инструкции по языкам", "исходный язык", "целевые языки". Field values
themselves are written in English (`persona`, `style`) or in the target language
(`language_instructions`), never in the conversation language by default.

This skill is offline. Read the kit, the glossary and the HCGameLoc source tree.
Do not query a live Weblate instance, do not call an LLM, do not upload, and do
not change any project setting. The deliverable is text a human pastes into the
form.

Ask once for the HCGameLoc checkout path (or read `HCGAMELOC_ROOT`) and cite
every code and doc file repository-relative from there. Never hardcode another
machine's absolute paths.

Refuse two things explicitly: writing a prompt for a project whose current field
values are unknown (see interview question 1), and inventing lore. If the user
only asks to review or edit this skill, do not start an interview.

## What the three fields actually do

Verify these against the checkout; they are the whole reason the field contracts
below look the way they do.

| Field | Where it lands | Who reads it |
|---|---|---|
| `persona` | `{persona}` slot of the fixed prompt, `weblate/machinery/llm.py:143` | translator **and** judge |
| `style` | `{style}` slot, `weblate/machinery/llm.py:145` | translator **and** judge |
| `language_instructions` | `{language_instructions}`, rendered as `Target-language project instructions:` — `weblate/machinery/llm.py:425-429`, assembled in `_get_prompt`, `llm.py:1251-1255` | translator only |

1. **persona + style are the judge's project context.** `judge_project_context()`
   (`weblate/trans/judge_loop.py:267-285`) concatenates exactly those two fields
   with a blank line and substitutes the result into the first sentence of
   `weblate/trans/judge_prompts/verdict.txt:1`:
   `You are an MQM annotator for a <source> to <target> video game localization. <persona>\n\n<style>`.
   Documented behaviour: `docs/admin/checks.rst:265-273`. Consequences:
   anything stated there becomes a review criterion; an unstated register is
   reported less often than a wrongly assumed one; and a role sentence
   ("You are a translator of…") contradicts the annotator role the judge prompt
   already assigns.
2. **language_instructions never reach the judge.** Per-language typography,
   politeness levels and grammar traps go there. Anything the judge must enforce
   must live in `persona`/`style`.
3. **One language block is chosen, never merged.** `_get_language_instructions()`
   (`llm.py:675-701`) tries the exact key, then a fuzzy match, then the base
   language code, and returns the first hit; documented in
   `docs/admin/machine.rst:83-88`. Each block must be self-contained. Hard cap
   **1000 characters per language** (`weblate/machinery/forms.py:23`, validated
   at `forms.py:537-586`).
4. **The fixed prompt already states 28 rules** (`llm.py:140-267`): placeholder
   integrity, markup preservation, glossary flags (`exact`, `forbidden`,
   `read-only`, `terminology`), "use the existing translation as the base",
   "treat note/explanation/key as reference only, never emit them", and rule 27 —
   the final punctuation of the target must match the source. Do not restate any
   of it.
5. **Engine markup and placeholders are masked before the request.**
   `GameMarkupCheck.check_highlight` (`weblate_customization/src/weblate_customization/checks.py:413-428`)
   is always on, and `weblate/trans/protected_tokens.py:11-18` covers
   `<color=…>`, `</color>`, `<link>`, `<size>`, `<b>`, `<i>`, `<u>`, `<s>`,
   `<sprite>`, `{0}`, `%KEY%` and printf tokens. Weblate replaces them with
   `@@PHn@@` and restores them afterwards, so an instruction about them talks
   about tokens the model never sees. A literal two-character `\n`, and the `$`
   line separator when the component does not use it tightly, are **not** masked.
6. **Glossary terms usually travel with the request, conditionally.**
   `_get_full_glossary()` (`llm.py:703-725`) counts project glossary units for
   that language pair with `state >= STATE_TRANSLATED`; between 1 and 300
   (`LLM_FULL_GLOSSARY_LIMIT`, `llm.py:295`) the whole term base is sent with
   every batch, explanations included; at 0 or above 300 it falls back to exact
   source matching, which an inflected term escapes. Terminology therefore
   belongs in the glossary, not in the prompt. Never claim the count without
   checking it per language pair.
7. **Cost and cache.** The three fields sit in the cached prompt prefix and are
   paid on every request. Editing them changes `project_context_hash`
   (`judge_loop.py:307`), which invalidates the project's judge verdict cache: a
   re-run costs money. Editing only these three fields does not trigger a live
   service check (`prompt_only_fields`, `weblate/machinery/forms.py:486-487`).

Authoritative reading order when something here looks stale: source code first,
then `docs/admin/machine.rst:17-21` and `:70-96` for the field contract,
`docs/admin/checks.rst` for judge semantics, and
`docs/product/guides/producer-guide-weblate.md:766-832` for a shipped example of
a filled-in configuration.

## Required interview

Ask in one short Russian batch, at most six questions, one decision each, then
wait. Do not scan the kit for lore before the answers; measuring the file
(question-free facts: encoding, columns, counts) is allowed at any time.

1. **Current values.** "Пришлите текущие значения полей `persona`, `style` и
   `language_instructions` из формы `/machinery/<project>/<engine>/` — текстом
   или скриншотом. Если поля пустые, так и напишите." Without this answer you
   cannot tell replacement from duplication. If the user cannot supply them,
   deliver the values labelled as a **replacement set** and state in the report
   that an existing prompt layer may be overwritten.
2. **Project and engine.** "Слаг проекта и какой движок настроен — `openrouter`
   или `litellm`?" Both use the same three fields; only one is project-wide
   (`ROUTED_ENGINES`, `weblate/trans/forms.py`).
3. **Source language.** Russian (`ru`) is the default, so confirm rather than
   ask: "Исходный язык — русский, верно?". Proceed on the default when there is
   no objection and say so in the report. Never derive it from column order or
   population; leave `ru` only on an explicit statement or on kit evidence
   against it, and note that a Russian source is what licenses the standard
   `style` rules about impersonal phrasing and added referents.
4. **Target languages and codes.** "Для каких языков нужны инструкции?" Convert
   names to codes that exist in Weblate; verify with `Language.objects.fuzzy_get_strict`
   in the container, or `loc_kit_ingest/langcode.py` for kit-side codes. Always
   distinguish `zh_Hans` and `zh_Hant`.
5. **Register decisions the producer owns.** "Регистр: где обращаемся к игроку
   неформально, где формально? Мат и грубость сохраняем в силе источника?
   Нужны ли ограничения по вежливости для ja/ko?" A wrong guess here is the most
   expensive error in the whole skill: it becomes judge ground truth.
6. **Glossary state.** "Глоссарий уже импортирован в проект как компонент, или
   пока это только файл?" This decides whether item 6 above holds and whether
   terminology may be omitted from the prompt.

Ask a seventh question only about a real blocker found later. "Решай сам"
authorizes ordinary conservative choices, not invented facts about the game.

## Evidence pass over the kit

Measure before writing. Every prompt line must trace to one of these numbers or
to a producer decision; no line may rest on "games usually".

Collect, with a deterministic script over the kit (and over the already-shipped
target columns when the kit has them):

- row count; how many rows carry each markup family (`<color`, `<b>`, `<size>`,
  `<sprite>`, `<link>`), indexed placeholders (`{0}`), `%KEY%`, the conditional
  DSL (`[…|…]`), the `$` separator, and a literal `\n`;
- source length distribution: median, p90, max, and the count of rows at or
  below 20 characters — the share of pure UI labels versus prose;
- how many source rows end in `.`, `!`, `?` (rule 27 exposure);
- explanation coverage, if the kit has an `Explanation` column;
- samples: 5–10 UI labels, 5–10 tooltips with placeholders, 5–10 dialogue lines,
  the longest rows, and rows whose shipped target visibly deviates (added
  subject, softened profanity, moved punctuation, broken tag, register drift).
  These deviations are the raw material for `style`: a rule that fixes an
  observed defect is worth its tokens, a rule that fixes an imagined one is not.

Also read the glossary file: term count, which target columns are populated,
which flags are set, and which frequent kit names are **missing** from it. A
name that appears in dozens of strings and has no glossary entry is a glossary
task, not a prompt line.

Check which checks are active for this content, because a check that is always
on makes a prompt line about the same defect redundant *for the judge* and still
useful *for the translator*: `game-markup`, `game-line-break`, `cyrillic-leak`,
`game-number`, `game-token`, `game-length`
(`weblate_customization/src/weblate_customization/checks.py:381-856`).

## What never goes into a prompt

- A role sentence, a job title, or "you are…" in any field. See mechanics 1.
  The shipped `col4` example
  (`docs/product/guides/producer-guide-weblate.md:773-779`) is second-person and
  predates the judge reading the same text; prefer third-person descriptive
  prose and treat that example as precedent, not as a template.
- Anything from the 28 fixed rules: placeholder integrity, markup preservation,
  glossary-flag semantics, "do not emit note/explanation", final punctuation.
- Instructions about `{0}`, `%KEY%` or `<color=…>`: they are masked (mechanics 5).
  A literal `\n` and a tightly used `$` are the exceptions worth stating.
- The glossary itself, or individual terms: they travel with the request.
- A hard length cap. `game-length` tiers
  (`checks.py:831-837`: ≤10 chars → 3.0x, ≤30 → 2.0x, ≤80 → 1.5x, else 1.35x,
  with 28/40/90-character floors) are overflow heuristics, not a per-string
  budget, and the fixed prompt forbids omission and summarization. State the
  priority instead: a target that says less than the source is a defect, an
  over-long UI label is a layout risk. The judge is told length is not an error
  (`verdict.txt`), so a length line cannot buy you flags either.
- Unverifiable lore: a plot point, a character relation, a platform, an audience
  age, a marketing adjective. If the kit and the glossary do not show it, and the
  producer did not state it, it does not go in.
- Praise, meta-instructions about JSON, or anything about the reply format.

## Field contracts

### persona

Descriptive prose about the product, third person, no imperatives, 400–900
characters. It answers only: what the game is, what the strings are, what the
register is.

Include, in this order, and only when evidenced:

1. Genre, setting and the player's role, in one sentence.
2. What the text consists of — the actual mix measured in the evidence pass
   (short UI labels and numeric tooltips / dialogue / narration), because one
   component holds several registers and the judge otherwise measures prose with
   a label's ruler.
3. The register, ending with the explicit permission clause modelled on the
   measured phrasing: "… and that is intended, not an error". Name what would
   otherwise be reported as a style defect: mild profanity, bluntness,
   deliberately plain wording, deliberate archaism.

Every proper noun in `persona` must be traceable to the glossary or to specific
kit keys; keep that trace in the report, not in the field.

### style

Project-wide, language-neutral policy, one rule per line, 800–1800 characters.
Admission test for a line: the judge could return a verdict on it, and the
translator could act on it, and the evidence pass showed a real instance.

Rule families that usually earn their place:

- string role preserved: a label stays a label, a fragment stays a fragment, a
  spoken line stays spoken (licensed by the short-string share plus long prose
  in the same component);
- no added subject, name or referent the source does not name (impersonal
  Russian is the usual source of this defect; the judge classifies it as
  `addition`);
- quantities, prices, durations and levels exactly as stated, never rounded,
  converted or invented (`game-number`);
- profanity and rudeness at source strength, in both directions;
- names, factions, items, modes follow the glossary and stay identical across
  strings;
- unmasked engine syntax stated literally: the two-character `\n`, a tight `$`;
- no source-script leakage into a target that does not use that script
  (`cyrillic-leak`);
- concision with the explicit "never drop content" priority described above.

Write each line as an observable requirement, not as an aspiration. "Keep tone
appropriate" is unusable; "keep mild profanity at source strength, do not soften
and do not add profanity the source lacks" is usable.

### language_instructions

A JSON object mapping exact Weblate language codes to one self-contained block
per language, each ≤1000 characters, written **in that target language** when
the rules are about its own typography and grammar (the model follows them
better, and the block is shorter). Content families, in order of value:

1. Variant and region policy where two variants exist: which script, which
   vocabulary, and the explicit ban on the other one (`zh_Hans` vs `zh_Hant` is
   the canonical case; a single shared `zh` block cannot do this, and a bare `zh`
   key resolves to Simplified and also serves as the base-code fallback for
   `zh_Hant`, silently giving Traditional the Simplified rules).
2. Typography: punctuation width, quotation marks, ellipsis, spacing, digits and
   Latin runs — stated because the kit mixes markup and digits into CJK text.
3. Register and politeness level per string class (UI/system versus dialogue),
   anchored to what the already-shipped corpus does, so machine output does not
   diverge from thousands of existing strings and the judge does not report the
   corpus as inconsistent.
4. A genuine mechanical grammar trap of that language around substituted values.
   Korean particle alternation after `{0}` is the standard example: the final
   sound of the inserted value is unknown, so require `을(를)`, `이(가)`,
   `은(는)`, `와(과)` or a rewrite that needs no particle.
5. Script and name conventions: transliteration source (the glossary), long
   vowels, no invented honorifics.
6. Only for a target that expands relative to the source (typically English): a
   reminder to re-check labels that grew much longer.

Do not add a block for a language nobody translates: an absent block is
harmless, and `resolve_model`'s `*` fallback still routes the request.

## Verification gate

Run this offline against the dev container before delivering. It proves the
values are accepted, sized, routed to the right language and visible in the
rendered prompt; it proves nothing about translation quality.

Write the three fields plus a routing map into a JSON file under the container's
mounted data directory (`dev-docker/data/`, mounted at `/app/data`), then:

```python
import json
D = json.loads(open("/app/data/prompts.json", encoding="utf-8").read())
from weblate_customization.machinery import RoutedLLMTranslation, RoutedLLMMachineryForm
from weblate.trans.judge_loop import judge_project_context

form = RoutedLLMMachineryForm(RoutedLLMTranslation, data={
    "key": "dummy-key", "base_url": "https://openrouter.ai/api/v1",
    "routing": json.dumps(D["routing"]), "persona": D["persona"], "style": D["style"],
    "language_instructions": json.dumps(D["language_instructions"])})
form.is_valid()
print("field errors:", {k: v for k, v in form.errors.items() if k != "__all__"} or "none")
print("non-field:", [str(e) for e in form.errors.get("__all__", [])])
c = dict(form.cleaned_data)
print("caps:", {k: len(v) for k, v in c["language_instructions"].items()})
s = RoutedLLMTranslation(c)
for lang in [*D["language_instructions"], "fr"]:
    head = s._get_prompt(lang).split("Input is provided as JSON")[0]
    own = D["language_instructions"].get(lang, "")
    print(lang, "| model", s.resolve_model(lang),
          "| own:", bool(own) and own[:30] in head,
          "| header:", "Target-language project instructions:" in head,
          "| persona+style:", D["persona"][:30] in head and D["style"][:30] in head,
          "| leak:", any(v[:30] in head for k, v in D["language_instructions"].items() if k != lang))
class P:
    def get_machinery_settings(self): return {"openrouter": c}
ctx = judge_project_context(P())
print("judge context:", len(ctx), ctx == D["persona"] + "\n\n" + D["style"])
```

Run it with
`docker exec <weblate-container> weblate shell -c "exec(open('/app/data/verify.py').read())"`,
or `./rundev.sh` equivalents. Ready means:

- no field-level errors; every `language_instructions` length ≤ 1000;
- for each configured language: `own: True`, `header: True`, `leak: False`;
- for an unconfigured language such as `fr`: `own: False`, `header: False`, and a
  resolved model from the `*` route;
- `judge context` equals `persona + "\n\n" + style` byte for byte.

Two traps in this gate:

- **Never assert on the whole prompt.** Rule 24 of the fixed prompt contains the
  phrase `Target-language project instructions`, so a whole-prompt substring
  test reports an unconfigured language as configured. Split at
  `Input is provided as JSON` and assert on the head only.
- **The form as a whole will be invalid** with a dummy key: `BaseMachineryForm.clean()`
  runs `validate_settings()`, which makes one upstream call and returns
  `Could not fetch translation: Missing Authentication header`. That is expected
  and says nothing about the prompt text; a real prompt-only edit skips the
  check entirely. Report field-level validity, not form validity.

Remove the staged JSON and script from `dev-docker/data/` afterwards.

## Report

Deliver in Russian, in this order:

1. The three values, each in its own copy-paste block, labelled with the exact
   field name from the form, plus the JSON object for the language instructions.
2. The paste order and the two operational warnings: the judge verdict cache is
   invalidated by this edit, so paste before a large run, not during one; and if
   the project already had prompt text, the pasted values replace it.
3. One line of evidence per `style` rule and per `persona` claim: the count, the
   key, or the producer decision behind it. This is what makes the prompt
   reviewable by someone who was not in the session.
4. Character counts against the 1000-character cap, and the verification-gate
   output verbatim.
5. Separately: what belongs in other artifacts rather than in the prompt —
   missing glossary terms, flags to propose, kit `Explanation` gaps, checks to
   enable. Do not smuggle these into prompt text.

## Related skills

- `preparing-weblate-loc-kits` produces the import CSV this skill measures. Use
  it first when the kit has not been converted yet; its `Explanation` column is
  per-string context and is a different artifact from the project-wide prompt.
- `game-glossary-builder` produces the glossary CSV and its `flags` decisions.
  Terminology and per-term restrictions belong there, because the glossary
  travels with each request; the prompt only states that glossary identity is
  binding. Route every term-level finding of this skill into that skill's
  approval workflow instead of writing it into `style`.

## Red flags

- A prompt written without knowing the project's current field values.
- Second-person role assignment in `persona` or `style`.
- Lines that restate masked placeholders, markup, or the fixed prompt's rules.
- Terminology, term lists or per-term bans inside `style`.
- A hard character or ratio cap that can be satisfied by dropping content.
- Lore, platform, audience or tone claimed without a kit key, a glossary entry or
  a producer decision.
- A shared `zh` block, a bare `zh` key, or language codes copied from the kit
  header without checking that Weblate resolves them.
- A language block that depends on another block being read too.
- Whole-prompt substring assertions in the gate, or "form valid" claimed after a
  dummy-key submission.
- Delivering values while claiming the live project was verified: this skill
  never reads or writes a live instance.
