# Verification gate (HCGameLoc checkout only)

Run this only when the session already runs inside an HCGameLoc checkout with
the dev container up. Never ask the producer for a path, a container name or a
command to make it possible: without a checkout, the character-count check in
SKILL.md is the whole verification, and the report says so.

The gate proves the values are accepted, sized, routed to the right language
and visible in the rendered prompt; it proves nothing about translation quality.

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

- no field-level errors; every `language_instructions` length <= 1000;
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
