# Repository guidance for agents

This repository distributes three Agent Skills for Hero Craft game
localization. It contains no application code: the product is the prose inside
`skills/*/SKILL.md`.

## Layout

| Path | Purpose |
|---|---|
| `skills/<name>/SKILL.md` | the skills themselves, flat one level deep |
| `install.sh` | installs the skills into every harness on the machine |
| `tools/validate_skills.py` | the only quality gate; also runs in CI |
| `docs/compatibility.md` | per-harness discovery paths with source URLs |
| `docs/workflow.md` | how the three skills chain together |
| `examples/demo-kit/` | fictional sample data, safe to use in public |

`CLAUDE.md` is a symlink to this file, because Claude Code reads `CLAUDE.md`
and not `AGENTS.md` (<https://github.com/anthropics/claude-code/issues/34235>).
Edit `AGENTS.md`; never replace the symlink with a second copy.

## Rules for editing a skill

- Frontmatter carries only open-standard keys: `name`, `description`,
  `license`, `compatibility`, `metadata`. Harness-specific extensions are
  prohibited here, because the same file has to behave identically in nine
  harnesses.
- `name` equals the directory name; `description` states what the skill does
  and when to trigger it, within 1024 characters.
- Keep the body under 500 lines; long reference material goes into
  `references/` inside the skill directory and is linked from the body.
- Instructions are written in English. The skill's interaction with the user -
  interview questions, progress notes, final report - is Russian, and every
  skill states that explicitly in its own scope section.
- Every rule inside a skill must be traceable: a repository path, a documented
  behaviour, or a decision the user made. Do not add advice that cannot be
  acted on or verified.
- Run `python3 tools/validate_skills.py` before committing. It is the same
  check CI runs.

## Rules for the repository docs

- `README.md` is Russian and primary; `README.en.md` mirrors it. Change both
  when the install flow, the skill list, or the compatibility table changes.
- `docs/compatibility.md` claims must each carry a link to official
  documentation. If a harness does not document a path, write "not documented"
  instead of guessing, and do not add it to `install.sh`.
- Version entries in `CHANGELOG.md` are calendar-based (`YYYY.MM`).
