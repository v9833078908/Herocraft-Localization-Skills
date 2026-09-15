# What the three fields actually do

These facts are verified against the HCGameLoc source tree; every citation is
repository-relative from an HCGameLoc checkout. The producer never needs a
checkout for the skill to use them. Re-verify a citation only when the session
already runs inside a checkout and something here looks stale.

| Field (UI label, Russian UI) | Where it lands | Who reads it |
|---|---|---|
| `persona` - Translator persona, «Личность переводчика» | `{persona}` slot of the fixed prompt, `weblate/machinery/llm.py:143` | translator **and** judge |
| `style` - Translator style, «Стиль перевода» | `{style}` slot, `weblate/machinery/llm.py:145` | translator **and** judge |
| `language_instructions` - Language-specific instructions, «Инструкции для конкретного языка» | `{language_instructions}`, rendered as `Target-language project instructions:` - `weblate/machinery/llm.py:425-429`, assembled in `_get_prompt`, `llm.py:1251-1255` | translator only |

The form lives at `/machinery/<project>/<engine>/`; in the UI the producer
reaches it through the project menu «Операции» -> «Автоматические предложения»
-> «Настроить» next to the OpenRouter or LiteLLM service. Both services use the
same three fields and only one is used project-wide (`ROUTED_ENGINES`,
`weblate/trans/forms.py`), so the text does not depend on which one is set up.

1. **persona + style are the judge's project context.** `judge_project_context()`
   (`weblate/trans/judge_loop.py:267-285`) concatenates exactly those two fields
   with a blank line and substitutes the result into the first sentence of
   `weblate/trans/judge_prompts/verdict.txt:1`:
   `You are an MQM annotator for a <source> to <target> video game localization. <persona>\n\n<style>`.
   Documented behaviour: `docs/admin/checks.rst:265-273`. Consequences:
   anything stated there becomes a review criterion; an unstated register is
   reported less often than a wrongly assumed one; and a role sentence
   ("You are a translator of...") contradicts the annotator role the judge prompt
   already assigns.
2. **language_instructions never reach the judge.** Per-language typography,
   politeness levels and grammar traps go there. Anything the judge must enforce
   must live in `persona`/`style`.
3. **One language block is chosen, never merged.** `_get_language_instructions()`
   (`llm.py:675-701`) tries the exact key, then a fuzzy match, then the base
   language code, and returns the first hit; documented in
   `docs/admin/machine.rst:83-88`. Each block must be self-contained. Hard cap
   **1000 characters per language** (`weblate/machinery/forms.py:23`, validated
   at `forms.py:537-586`). The field must be a JSON object; anything else is
   rejected with «Инструкции для конкретного языка должны быть JSON-объектом».
4. **The fixed prompt already states 28 rules** (`llm.py:140-267`): placeholder
   integrity, markup preservation, glossary flags (`exact`, `forbidden`,
   `read-only`, `terminology`), "use the existing translation as the base",
   "treat note/explanation/key as reference only, never emit them", and rule 27 -
   the final punctuation of the target must match the source. Do not restate any
   of it.
5. **Engine markup and placeholders are masked before the request.**
   `GameMarkupCheck.check_highlight` (`weblate_customization/src/weblate_customization/checks.py:413-428`)
   is always on, and `weblate/trans/protected_tokens.py:11-18` covers
   `<color=...>`, `</color>`, `<link>`, `<size>`, `<b>`, `<i>`, `<u>`, `<s>`,
   `<sprite>`, `{0}`, `%KEY%` and printf tokens. Weblate replaces them with
   `@@PHn@@` and restores them afterwards, so an instruction about them talks
   about tokens the model never sees. A literal two-character `\n` and the `$`
   line separator are **not** masked; `game-line-break` enforces `$` only when
   the source uses it tightly (`separator_is_tight`, `checks.py:175`).
6. **Glossary terms usually travel with the request, conditionally.**
   `_get_full_glossary()` (`llm.py:703-725`) counts project glossary units for
   that language pair with `state >= STATE_TRANSLATED`; between 1 and 300
   (`LLM_FULL_GLOSSARY_LIMIT`, `llm.py:295`) the whole term base is sent with
   every batch, explanations included; at 0 or above 300 it falls back to exact
   source matching, which an inflected term escapes. Terminology therefore
   belongs in the glossary, not in the prompt.
7. **Cost and cache.** The three fields sit in the cached prompt prefix and are
   paid on every request. Editing persona or style changes `project_context_hash`
   (`judge_loop.py:307`), which invalidates the project's judge verdict cache: a
   re-run costs money. Editing only these three fields does not trigger a live
   service check (`prompt_only_fields`, `weblate/machinery/forms.py:486-487`).
8. **Active checks.** `game-markup`, `game-line-break`, `cyrillic-leak`,
   `game-number`, `game-token`, `game-length`
   (`weblate_customization/src/weblate_customization/checks.py:381-856`). A check
   that is always on makes a prompt line about the same defect redundant for the
   judge and still useful for the translator. `game-length` tiers
   (`checks.py:831-837`: <=10 chars -> 3.0x, <=30 -> 2.0x, <=80 -> 1.5x, else
   1.35x, with 28/40/90-character floors) are overflow heuristics, not a
   per-string budget.

Authoritative reading order when something here looks stale: source code first,
then `docs/admin/machine.rst:17-21` and `:70-96` for the field contract,
`docs/admin/checks.rst` for judge semantics, and
`docs/product/guides/producer-guide-weblate.md:766-832` for a shipped example of
a filled-in configuration. That example is second-person and predates the judge
reading the same text; treat it as precedent, not as a template.
