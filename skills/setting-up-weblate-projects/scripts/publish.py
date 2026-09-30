#!/usr/bin/env python3
"""Publish a prepared localization project to HCGameLoc (Weblate) through the REST API.

Reads the upload folder written by build_upload.py (manifest.json plus the ZIP
and JSON files it names) and creates, in this order: the project, the glossary
component (before the strings, or Weblate adds a second empty glossary), each
strings component, the source-string explanations, the `terminology` flag on
every glossary term, and the project's openrouter prompt configuration.

Subcommands (all print one JSON document to stdout; progress goes to stderr):

  plan      DIR                 what `run` would do; no network
  preflight DIR --base-url ...  read-only: token works, slugs free, languages exist
  run       DIR --base-url ...  create everything; --resume continues a partial run
  verify    DIR --base-url ...  compare the server with the manifest

The token is read from the environment variable named by --token-env, or from
that variable inside --env-file. It is never printed or written anywhere.
Standard library only.
"""

from __future__ import annotations

import argparse
import io
import json
import os
import sys
import time
import uuid
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import NoReturn
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

SOURCE_SCOPED_FLAGS = ("read-only", "forbidden")


def fail(code: str, **details) -> NoReturn:
    print(json.dumps({"error": code, **details}, ensure_ascii=False, indent=2))
    sys.exit(2)


def log(message: str) -> None:
    print(message, file=sys.stderr, flush=True)


class Api:
    def __init__(self, base_url: str, token: str) -> None:
        self.base = base_url.rstrip("/") + "/"
        if not self.base.endswith("/api/"):
            self.base += "api/"
        self.token = token

    def call(self, method, path, *, json_body=None, form=None, zip_bytes=None, ok=(200, 201)):
        url = path if path.startswith("http") else self.base + path.lstrip("/")
        headers = {"Authorization": f"Token {self.token}", "Accept": "application/json"}
        data = None
        if form is not None:
            data, headers["Content-Type"] = multipart(form, zip_bytes)
        elif json_body is not None:
            data = json.dumps(json_body).encode()
            headers["Content-Type"] = "application/json"
        request = Request(url, data=data, method=method, headers=headers)
        try:
            with urlopen(request, timeout=300) as response:
                status, body = response.status, response.read()
        except HTTPError as error:
            status, body = error.code, error.read()
        except URLError as error:
            fail("server_unreachable", url=url, reason=str(error.reason))
        if status not in ok:
            fail("http_error", method=method, url=url, status=status,
                 body=body.decode(errors="replace")[:3000])
        return status, (json.loads(body) if body else None)

    def get(self, path, ok=(200,)):
        return self.call("GET", path, ok=ok)

    def paged(self, path):
        url = path + ("&" if "?" in path else "?") + "page_size=1000"
        while url:
            _status, page = self.get(url)
            yield from page["results"]
            url = page["next"]


def multipart(fields: dict, zip_bytes: bytes | None) -> tuple[bytes, str]:
    boundary = uuid.uuid4().hex
    out = io.BytesIO()
    for name, value in fields.items():
        out.write(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n'.encode())
        out.write(str(value).encode() + b"\r\n")
    if zip_bytes is not None:
        out.write(
            f'--{boundary}\r\nContent-Disposition: form-data; name="zipfile"; '
            f'filename="upload.zip"\r\nContent-Type: application/zip\r\n\r\n'.encode()
        )
        out.write(zip_bytes + b"\r\n")
    out.write(f"--{boundary}--\r\n".encode())
    return out.getvalue(), f"multipart/form-data; boundary={boundary}"


def load_manifest(folder: Path) -> dict:
    path = folder / "manifest.json"
    if not path.is_file():
        fail("manifest_missing", path=str(path))
    manifest = json.loads(path.read_text(encoding="utf-8"))
    if not manifest.get("project", {}).get("slug"):
        fail("manifest_incomplete", missing="project")
    if not manifest.get("components"):
        fail("manifest_incomplete", missing="components")
    for entry in [manifest.get("glossary"), *manifest["components"]]:
        if entry and not (folder / entry["zip"]).is_file():
            fail("file_missing", path=str(folder / entry["zip"]))
    return manifest


def read_token(args) -> str:
    token = os.environ.get(args.token_env, "")
    if not token and args.env_file:
        for line in Path(args.env_file).read_text(encoding="utf-8").splitlines():
            name, _, value = line.strip().removeprefix("export ").partition("=")
            if name.strip() == args.token_env:
                token = value.strip().strip("'\"")
    if not token:
        fail("token_missing", token_env=args.token_env, env_file=args.env_file)
    return token


def languages(manifest: dict) -> list[str]:
    found = set()
    for entry in [manifest.get("glossary"), *manifest["components"]]:
        if entry:
            found.update(entry["languages"])
    return sorted(found)


def plan(manifest: dict) -> dict:
    slug = manifest["project"]["slug"]
    steps = [f"create project {manifest['project']['name']!r} ({slug}), "
             "translation reviews on, check_flags=repeat-drift"]
    glossary = manifest.get("glossary")
    if glossary:
        steps.append(f"create glossary component {glossary['slug']}: {glossary['terms']} terms, "
                     f"{len(glossary['languages'])} languages")
    for component in manifest["components"]:
        steps.append(f"create strings component {component['slug']}: {component['units']} strings, "
                     f"{len(component['languages'])} languages")
    for component in manifest["components"]:
        if component.get("explanations"):
            steps.append(f"set explanations on {component['slug']} source strings")
    if glossary:
        steps.append("flag every glossary term as terminology")
    if manifest.get("machinery"):
        steps.append("save openrouter prompts (the server makes one test call to the model)")
    steps.append("verify against the manifest")
    return {"project": slug, "source_language": manifest["source_language"],
            "languages": languages(manifest), "steps": steps}


def preflight(api: Api, manifest: dict) -> dict:
    status, _ = api.get("projects/?page_size=1", ok=(200, 401, 403))
    if status != 200:
        fail("token_rejected", status=status)
    slug = manifest["project"]["slug"]
    status, _ = api.get(f"projects/{quote(slug)}/", ok=(200, 404))
    missing = [code for code in languages(manifest)
               if api.get(f"languages/{quote(code)}/", ok=(200, 404))[0] == 404]
    return {"token": "ok", "project_exists": status == 200,
            "languages_missing_on_server": missing,
            "note": "the right to create projects is checked only when the project is created"}


def wait_loaded(api: Api, slug: str, component: str, language: str, expected: int, timeout=900) -> int:
    path = f"translations/{slug}/{component}/{language}/"
    deadline = time.monotonic() + timeout
    total = 0
    while time.monotonic() < deadline:
        status, translation = api.get(path, ok=(200, 404))
        if status == 200:
            total = translation["total"]
            if total >= expected:
                return total
        time.sleep(3)
    fail("load_timeout", translation=path, expected=expected, loaded=total)


def component_exists(api: Api, slug: str, component: str) -> bool:
    return api.get(f"components/{slug}/{component}/", ok=(200, 404))[0] == 200


def create_component(api, folder, manifest, entry, *, glossary: bool) -> None:
    slug, source = manifest["project"]["slug"], manifest["source_language"]
    fields = {"name": entry["name"], "slug": entry["slug"], "source_language": source}
    if glossary:
        fields.update(file_format="tbx", filemask="tbx/*.tbx", is_glossary="true", new_lang="none")
    else:
        fields.update(file_format="po-mono", filemask="*.po",
                      template=f"{source}.po", new_base=f"{source}.po")
    api.call("POST", f"projects/{slug}/components/", form=fields,
             zip_bytes=(folder / entry["zip"]).read_bytes())
    expected = entry["terms"] if glossary else entry["units"]
    wait_loaded(api, slug, entry["slug"], source, expected)


def patch_all(api: Api, items: list[tuple[int, dict]], workers: int) -> None:
    with ThreadPoolExecutor(max_workers=workers) as pool:
        list(pool.map(lambda item: api.call("PATCH", f"units/{item[0]}/", json_body=item[1]), items))


def apply_explanations(api, folder, manifest, entry, workers) -> dict:
    slug, source = manifest["project"]["slug"], manifest["source_language"]
    wanted = json.loads((folder / entry["explanations"]).read_text(encoding="utf-8"))
    units = {u["context"]: u for u in api.paged(f"translations/{slug}/{entry['slug']}/{source}/units/")}
    todo = [(units[key]["id"], {"explanation": text}) for key, text in wanted.items()
            if key in units and units[key]["explanation"] != text]
    patch_all(api, todo, workers)
    return {"set": len(todo), "already_set": len(wanted) - len(todo),
            "keys_not_found": sorted(set(wanted) - set(units))[:20]}


def flag_terminology(api, manifest, workers) -> dict:
    """Mirror the web wizard: every source term gets `terminology`, and
    read-only/forbidden set on a target are promoted to the source term."""
    slug, component = manifest["project"]["slug"], manifest["glossary"]["slug"]
    sources, promoted = {}, {}
    for translation in api.paged(f"components/{slug}/{component}/translations/"):
        for unit in api.paged(f"translations/{slug}/{component}/{translation['language_code']}/units/"):
            if translation["is_source"]:
                sources[unit["url"]] = unit
            else:
                flags = f"{unit['flags']},{unit['extra_flags']}"
                modes = {mode for mode in SOURCE_SCOPED_FLAGS if mode in flags}
                promoted.setdefault(unit["source_unit"], set()).update(modes)
    todo = []
    for url, unit in sources.items():
        flags = [f.strip() for f in unit["extra_flags"].split(",") if f.strip()]
        for mode in [*sorted(promoted.get(url, ())), "terminology"]:
            if mode not in flags:
                flags.append(mode)
        if ",".join(flags) != unit["extra_flags"]:
            todo.append((unit["id"], {"extra_flags": ",".join(flags)}))
    patch_all(api, todo, workers)
    return {"flagged": len(todo), "terms": len(sources)}


def run(api: Api, folder: Path, manifest: dict, resume: bool, workers: int) -> dict:
    slug = manifest["project"]["slug"]
    result: dict = {"project": slug}
    status, _ = api.get(f"projects/{quote(slug)}/", ok=(200, 404))
    if status == 200 and not resume:
        fail("project_exists", project=slug,
             hint="rerun with --resume to finish a partial run of this same project")
    if status == 404:
        log("creating project")
        # Reviews on is the Hero Craft rule for every new project; the web wizard's
        # repeat-drift flag is not set by the API on its own.
        project = {"name": manifest["project"]["name"], "slug": slug,
                   "translation_review": True, "check_flags": "repeat-drift"}
        api.call("POST", "projects/", json_body=project)
        result["project_created"] = True

    glossary = manifest.get("glossary")
    if glossary and not component_exists(api, slug, glossary["slug"]):
        log("creating glossary")
        create_component(api, folder, manifest, glossary, glossary=True)
    for entry in manifest["components"]:
        if not component_exists(api, slug, entry["slug"]):
            log(f"creating strings component {entry['slug']}")
            create_component(api, folder, manifest, entry, glossary=False)
    for entry in manifest["components"]:
        if entry.get("explanations"):
            log(f"setting explanations on {entry['slug']}")
            result.setdefault("explanations", {})[entry["slug"]] = apply_explanations(
                api, folder, manifest, entry, workers)
    if glossary:
        log("flagging glossary terms")
        result["terminology"] = flag_terminology(api, manifest, workers)
    if manifest.get("machinery"):
        log("saving prompts")
        _status, response = api.call("PATCH", f"projects/{slug}/machinery_settings/",
                                     json_body=manifest["machinery"])
        result["machinery"] = response["message"]
    result["verify"] = verify(api, folder, manifest)
    return result


def verify(api: Api, folder: Path, manifest: dict) -> dict:
    slug, source = manifest["project"]["slug"], manifest["source_language"]
    problems = []
    report: dict = {"components": {}}
    entries = [(e, False) for e in manifest["components"]]
    if manifest.get("glossary"):
        entries.insert(0, (manifest["glossary"], True))
    for entry, is_glossary in entries:
        if not component_exists(api, slug, entry["slug"]):
            problems.append(f"component {entry['slug']} is missing")
            continue
        expected = entry["terms"] if is_glossary else entry["units"]
        rows = {t["language_code"]: (t["total"], t["translated"])
                for t in api.paged(f"components/{slug}/{entry['slug']}/translations/")}
        report["components"][entry["slug"]] = rows
        for code in entry["languages"]:
            if code not in rows:
                problems.append(f"{entry['slug']}: language {code} is missing")
            elif rows[code][0] != expected:
                problems.append(f"{entry['slug']}/{code}: {rows[code][0]} strings, expected {expected}")
        if not is_glossary:
            units = list(api.paged(f"translations/{slug}/{entry['slug']}/{source}/units/"))
            with_explanation = sum(1 for u in units if u["explanation"])
            wanted = len(json.loads((folder / entry["explanations"]).read_text(encoding="utf-8"))) \
                if entry.get("explanations") else 0
            report["components"][entry["slug"]]["explanations"] = with_explanation
            report["components"][entry["slug"]]["notes"] = sum(1 for u in units if u["note"])
            if with_explanation < wanted:
                problems.append(f"{entry['slug']}: {with_explanation} explanations, expected {wanted}")
    glossaries = [c["slug"] for c in api.paged(f"projects/{slug}/components/") if c["is_glossary"]]
    if len(glossaries) > 1:
        problems.append(f"more than one glossary component: {glossaries}")
    _status, machinery = api.get(f"projects/{slug}/machinery_settings/")
    report["machinery"] = {name: sorted(conf) for name, conf in machinery.items()}
    if manifest.get("machinery") and manifest["machinery"]["service"] not in machinery:
        problems.append("prompt configuration is missing")
    _status, project = api.get(f"projects/{slug}/")
    report["web_url"] = project["web_url"]
    report["check_flags"] = project["check_flags"]
    report["translation_review"] = project["translation_review"]
    if not project["translation_review"]:
        problems.append("translation reviews are off")
    report["problems"] = problems
    report["manual"] = ["access control cannot be read or set through the API: "
                        "check the project's Access control page in the web interface"]
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("command", choices=["plan", "preflight", "run", "verify"])
    parser.add_argument("folder", type=Path, help="upload folder with manifest.json")
    parser.add_argument("--base-url", help="instance URL, e.g. https://l10n.herocraft.com")
    parser.add_argument("--token-env", default="WEBLATE_API_TOKEN")
    parser.add_argument("--env-file", help="dotenv file that holds --token-env")
    parser.add_argument("--resume", action="store_true", help="allow an existing project from a partial run")
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()

    manifest = load_manifest(args.folder)
    if args.command == "plan":
        output = plan(manifest)
    else:
        if not args.base_url:
            fail("base_url_missing")
        api = Api(args.base_url, read_token(args))
        if args.command == "preflight":
            output = preflight(api, manifest)
        elif args.command == "run":
            output = run(api, args.folder, manifest, args.resume, args.workers)
        else:
            output = verify(api, args.folder, manifest)
    print(json.dumps(output, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
