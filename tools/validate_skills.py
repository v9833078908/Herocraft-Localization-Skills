#!/usr/bin/env python3
"""Validate every skill in ./skills against the Agent Skills contract.

Checks only rules that actually break loading in a real harness, each one
sourced in docs/compatibility.md:

* `SKILL.md` exists, is the exact filename, and starts with `---` on line 1
  (Gemini CLI silently skips a file with anything before the delimiter).
* frontmatter carries non-empty `name` and `description` (required everywhere).
* `name` matches `^[a-z0-9]+(-[a-z0-9]+)*$`, is 1-64 characters and equals the
  directory name (Cursor, OpenCode, Zed enforce this; Claude Code derives the
  command from the directory).
* `description` is 1-1024 characters.
* only frontmatter keys from the open standard are used, so no harness has to
  ignore or reject an unknown field.
* the skill directory is flat: `SKILL.md` one level under `skills/`, with
  optional `scripts/`, `references/`, `assets/` (Zed, omp and Gemini CLI do
  not discover deeper nesting).
* every relative Markdown link in the body resolves on disk.

Usage: python3 tools/validate_skills.py [--skills-dir skills]
Exit code 0 means every skill is loadable; 1 lists the failures.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

NAME_RE = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
KEY_RE = re.compile(r"^([A-Za-z][A-Za-z0-9_-]*):\s*(.*)$")
LINK_RE = re.compile(r"\[[^\]]*\]\(([^)#]+)")
STANDARD_KEYS = {"name", "description", "license", "compatibility", "metadata"}
ALLOWED_DIRS = {"scripts", "references", "assets"}
MAX_BODY_LINES = 500


def split_frontmatter(text: str) -> tuple[dict[str, str], str] | None:
    if not text.startswith("---\n"):
        return None
    end = text.find("\n---\n", 3)
    if end == -1:
        return None
    block, body = text[4 : end + 1], text[end + 5 :]
    fields: dict[str, str] = {}
    for line in block.splitlines():
        if not line.strip() or line.startswith((" ", "\t", "#")):
            continue
        match = KEY_RE.match(line)
        if match:
            value = match.group(2).strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            fields[match.group(1)] = value
    return fields, body


def check_skill(directory: Path) -> list[str]:
    problems: list[str] = []
    skill_file = directory / "SKILL.md"
    if not skill_file.is_file():
        return [f"{directory.name}: no SKILL.md"]

    parsed = split_frontmatter(skill_file.read_text(encoding="utf-8"))
    if parsed is None:
        return [f"{directory.name}: frontmatter must open with '---' on line 1 and close with '---'"]
    fields, body = parsed

    name = fields.get("name", "")
    description = fields.get("description", "")
    if not name:
        problems.append(f"{directory.name}: missing 'name'")
    else:
        if not NAME_RE.match(name):
            problems.append(f"{directory.name}: 'name' must match ^[a-z0-9]+(-[a-z0-9]+)*$, got {name!r}")
        if not 1 <= len(name) <= 64:
            problems.append(f"{directory.name}: 'name' must be 1-64 characters, got {len(name)}")
        if name != directory.name:
            problems.append(f"{directory.name}: 'name' is {name!r} but the directory is {directory.name!r}")
    if not description:
        problems.append(f"{directory.name}: missing 'description'")
    elif len(description) > 1024:
        problems.append(f"{directory.name}: 'description' is {len(description)} characters, max 1024")

    unknown = sorted(set(fields) - STANDARD_KEYS)
    if unknown:
        problems.append(f"{directory.name}: non-standard frontmatter keys {unknown}")

    body_lines = body.count("\n")
    if body_lines > MAX_BODY_LINES:
        problems.append(f"{directory.name}: body is {body_lines} lines, keep it under {MAX_BODY_LINES}")

    for entry in sorted(directory.iterdir()):
        if entry.is_dir() and entry.name not in ALLOWED_DIRS:
            problems.append(f"{directory.name}: unexpected subdirectory {entry.name!r} (allowed: {sorted(ALLOWED_DIRS)})")
        if entry.is_dir() and entry.name in ALLOWED_DIRS:
            for nested in entry.rglob("SKILL.md"):
                problems.append(f"{directory.name}: nested SKILL.md at {nested.relative_to(directory)} is not discovered")

    for link in LINK_RE.findall(body):
        link = link.strip()
        if link.startswith(("http://", "https://", "mailto:", "skill://", "/")):
            continue
        if not (directory / link).exists():
            problems.append(f"{directory.name}: broken relative link {link!r}")

    return problems


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skills-dir", default="skills")
    args = parser.parse_args()

    root = Path(args.skills_dir)
    if not root.is_dir():
        print(f"error: {root} is not a directory", file=sys.stderr)
        return 1

    directories = sorted(d for d in root.iterdir() if d.is_dir())
    if not directories:
        print(f"error: no skills found in {root}", file=sys.stderr)
        return 1

    failures: list[str] = []
    seen: dict[str, Path] = {}
    for directory in directories:
        problems = check_skill(directory)
        failures.extend(problems)
        status = "FAIL" if problems else "ok"
        print(f"[{status}] {directory}")
        if directory.name in seen:
            failures.append(f"{directory.name}: duplicate skill name")
        seen[directory.name] = directory

    if failures:
        print()
        for failure in failures:
            print(f"  - {failure}")
        print(f"\n{len(failures)} problem(s) in {len(directories)} skill(s)")
        return 1

    print(f"\n{len(directories)} skill(s) valid")
    return 0


if __name__ == "__main__":
    sys.exit(main())
