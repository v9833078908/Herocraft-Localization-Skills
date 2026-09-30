# Publishing through the API

Facts behind `scripts/publish.py`, verified against HCGameLoc on 2026-09-30
(dev instance, then one production project). Read this when a step
fails or when the producer asks what exactly will happen on the server.

## Contents

- Permissions
- Order and why
- What the API does differently from the web wizard
- Errors and what to tell the producer
- Resuming
- Manual steps

## Permissions

| Step | What the account needs |
|---|---|
| Create the project | the site role «Добавление новых проектов» (Add new projects), or the right to add projects to a workspace. A regular administrator of another project does not have it |
| Everything after that | nothing extra: the creator becomes an administrator of the new project automatically (superusers already are) |
| Explanations | `source.edit`, which project administrators have |
| Prompts | `project.edit`, which project administrators have |

`preflight` proves the key works and reads languages and slugs. It cannot prove
the project-creation right without creating a project, so a refusal arrives on
the first step of `run`, before anything else is written.

## Order and why

1. **Project** with `translation_review` on (Hero Craft rule: every
   new Hero Craft project has reviews enabled, so imported translations wait
   for a reviewer's approval) and `check_flags=repeat-drift` (the web wizard
   sets it and the API does not).
2. **Glossary component** (`tbx`, `tbx/*.tbx`, `is_glossary`, `new_lang=none`)
   before any strings component: Weblate adds an empty automatic glossary
   after the first non-glossary component unless the project already has one.
3. **Strings components** (`po-mono`, `*.po`, template and new base
   `<source>.po`) from a ZIP of flat per-language PO files. Loading is
   asynchronous; the script waits until the source translation has the
   expected number of strings.
4. **Explanations**: one `PATCH /api/units/<id>/` per source string. There is
   no bulk endpoint; about 0.35 s per string, four in parallel, so 1600
   strings take one to five minutes.
5. **Terminology flags** on every glossary term, and `read-only`/`forbidden`
   promoted from targets to the source term, as the web wizard does. Without
   `terminology`, languages that the glossary file does not contain receive no
   terms at all.
6. **Prompts**: `PATCH /api/projects/<slug>/machinery_settings/` with service
   `openrouter` and only `persona`, `style`, `language_instructions`. The key,
   the endpoint and the per-language model routing are inherited from the
   server-wide configuration. Validation makes one live test call to the model
   and rejects an instruction block over 1000 characters or keyed by an
   unknown language code.
7. **Verify**: counts per language against the manifest, explanations, a
   single glossary, the stored prompt fields.

## What the API does differently from the web wizard

- `access_control` is not accepted: it is silently dropped. The project gets
  the server default, which on production is meant to be private. Check it by
  hand.
- CSV, TSV and XLSX kits are not accepted by the API, only Weblate's own
  formats in a ZIP; this is why `build_upload.py` renders PO and TBX.
- Explanations from the kit's `Explanation` column are applied by the wizard
  after loading; through the API they are separate unit updates (step 4).
- The wizard flags glossary terms as terminology in the background; through
  the API it is step 5.

## Errors and what to tell the producer

| What `publish.py` printed | Say | Then |
|---|---|---|
| `token_missing` | «Не вижу ключа: пришлите его или скажите, где он лежит.» | wait |
| `token_rejected` (401/403 on a read) | «Сервер не принял ключ. Проверьте, что он скопирован целиком, или сгенерируйте новый на вкладке «Доступ к API».» | wait |
| `server_unreachable` | «Сервер не отвечает по адресу ...; проверьте адрес и VPN.» | wait |
| `http_error` 403 on `POST projects/` | «У учётной записи нет права создавать проекты. Попросите администратора выдать роль «Добавление новых проектов».» | wait; nothing was created |
| `project_exists` | «Проект с адресом ... уже есть.» Offer another slug, or `--resume` only if it is this run's own partial project | ask |
| `languages_missing_on_server` | «На сервере нет языка ...» | a code mapping error in the kit (fix the header), or ask the administrator to add the language |
| `http_error` 400 on a component | the server's `errors` explain it: usually a file-format problem | rerun `build_upload.py check`, fix, `--resume` |
| `load_timeout` | «Сервер ещё загружает строки.» | wait a few minutes, then `--resume` |
| `http_error` 400 on `machinery_settings` | usually an instruction block too long, an unknown language code, or the test call to the model failed | fix `machinery.json`, rebuild, `--resume`; if the test call fails, the model routing on the server does not cover a language - tell the producer the administrator must fix it |

Quote the server's own message in the technical section of the report, not in
the chat.

## Resuming

`run --resume` accepts an existing project and skips what already exists:
components by slug, explanations already equal, flags already present. It then
re-saves the prompts and verifies. Use it only on a project this skill created
in this run; for anything else, ask.

## Manual steps

- **Access control**: `<url>/access/<slug>/`, the setting «Контроль доступа»
  must be «Приватный».
- **Team members**: adding translators to the project is done in the same
  access page; the skill does not do it.
