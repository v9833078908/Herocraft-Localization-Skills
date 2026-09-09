# Hero Craft Localization Skills

**Three agent skills that turn a raw game string export into a working
localization project: the import kit, the glossary, and the prompts of the
automatic-suggestion engine.**

[Русский](README.md) · English

The skills run in any agent that supports the open
[Agent Skills](https://agentskills.io/specification) standard: Claude Code,
Codex CLI, Cursor, OpenCode, Gemini CLI, GitHub Copilot CLI, Amp, Zed, omp.
One `SKILL.md` per skill, different install directories - `install.sh` handles
that part.

## Install

```sh
git clone https://github.com/v9833078908/Herocraft-Localization-Skills.git
cd Herocraft-Localization-Skills
./install.sh
```

> [!IMPORTANT]
> **Restart your agent after installing.** Almost every harness reads the skill
> list once, at session start. In an already-running session the new files sit
> on disk invisibly: the skill is neither offered nor invocable by name. The
> same applies to updates - `git pull` without a restart changes nothing.

`./install.sh --list` shows which harnesses exist on this machine, `--dry-run`
prints the plan, `--copy` writes copies instead of symlinks (Windows),
`--project ~/path` installs into a single project, `--uninstall` removes them.

To confirm the skills loaded: `/skills list` (Claude Code, Copilot CLI, Gemini
CLI), `/skills` (Codex CLI), **Customize → Skills** (Cursor); in omp, just ask
which skills are available.

## What is inside

| Step | Skill | What it does | When to call it |
|---|---|---|---|
| 1 | [`preparing-weblate-loc-kits`](skills/preparing-weblate-loc-kits/SKILL.md) | Converts a CSV/TSV/XLSX/TXT export into a file the component-creation UI accepts, without dropping languages or inventing keys | "A kit arrived from the developers and has to go into Weblate" |
| 2 | [`game-glossary-builder`](skills/game-glossary-builder/SKILL.md) | Builds the glossary from the same kit: terms, translations, explanations, and - as a separate decision - exception flags | "We need a glossary for a new project" |
| 3 | [`weblate-machinery-prompts`](skills/weblate-machinery-prompts/SKILL.md) | Writes `persona`, `style` and `language_instructions` for `/machinery/<project>/<engine>/` from evidence in the kit and the glossary | "Configure the suggestion and judge prompts" |

The order matters: each step consumes the previous step's artifact. See
[docs/workflow.md](docs/workflow.md).

## How the skills behave

- **They ask instead of guessing.** Each one opens with a short interview:
  source language, meaning of the columns, register, profanity policy,
  glossary state. No answer means no invented fact. Interviews and reports are
  conducted in Russian; machine-readable headers, language codes and flag
  tokens stay in English.
- **They never deploy.** File-level work only: no queries against a live
  Weblate, no filling of empty cells, no paid model calls. The deliverable is
  a file or a block of text a human reviews and applies.
- **They verify.** A kit counts as ready only after a `loc_kit_ingest` run; the
  prompts only after the form and the rendered prompt were exercised in the
  HCGameLoc dev container.

## Compatibility

`install.sh` uses three directories, which is enough for eight harnesses:

| Directory | Read by |
|---|---|
| `~/.agents/skills/` | Codex CLI, Cursor, OpenCode, Amp, Zed, Copilot CLI, omp |
| `~/.claude/skills/` | Claude Code |
| `~/.gemini/skills/` | Gemini CLI |

The full table of paths, limits and per-harness documentation links is in
[docs/compatibility.md](docs/compatibility.md) (Russian).

## Update

```sh
cd Herocraft-Localization-Skills && git pull && ./install.sh
```

With the default symlink install, `git pull` already updated the files; re-run
`install.sh` only to pick up newly added skills. With `--copy`, re-running the
installer after every `git pull` is mandatory.

## Try it without your own data

[examples/demo-kit](examples/demo-kit) holds a fictional kit for a small game
plus its glossary, so all three steps can be walked through without touching
production files.

## What this does not solve

The skills encode the contracts of HCGameLoc, Hero Craft's Weblate fork
(`l10n.herocraft.com`): its own game-markup checks, its own suggestion engines,
its own LLM judge. In stock Weblate some paths and checks will not match. The
skills do not translate strings for a translator, do not decide for a producer,
and do not replace LQA.

## Validation and contributions

```sh
python3 tools/validate_skills.py     # frontmatter, names, lengths, nesting, links
```

The same check runs in CI on every push and pull request. See
[CONTRIBUTING.md](CONTRIBUTING.md) (Russian) for how to propose a wording fix
without using git.

## Trust and security

A skill is a set of instructions your agent executes. Install skills only from
sources you trust, and read the `SKILL.md` first - there are three files here,
each of a reviewable size. No skill in this repository reaches out to external
network sources or asks for pre-approved command execution.

## License

[MIT](LICENSE). Change history in [CHANGELOG.md](CHANGELOG.md).
