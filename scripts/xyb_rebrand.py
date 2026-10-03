#!/usr/bin/env python3
"""Rebrand user-visible product strings for the xiaoyibao distribution.

A blind ``sed -i 's/octop/xyb-octop/g'`` would corrupt the import package, the
``~/.octop`` data directory, the ``OCTOP_*`` environment contract and the
upstream distribution names. So the replacement is expressed as an explicit,
ordered rule table and every rule is applied only to files that carry
user-visible copy.

Two surfaces, two different targets (see XYB-UPSTREAM-DIFF.md section 5):

* **Display name** -> 小胰宝, on user-visible copy: titles, PWA names, settings
  help text, error messages, documentation prose.
* **Technical name** -> xyb-octop, on artifacts: distribution name, console
  script, release asset prefixes, container image names, store identifiers.

Rules are ordered: the CLI-invocation protections must run before the generic
product-name replacement, or they would rewrite ``octop run`` into
``小胰宝 run``.

Usage::

    python3 scripts/xyb_rebrand.py --dry-run     # show what would change
    python3 scripts/xyb_rebrand.py               # apply
    python3 scripts/xyb_rebrand.py --check       # exit 1 if anything is left
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

DISPLAY = "小胰宝"
ARTIFACT = "xyb-octop"
ARTIFACT_SNAKE = "xyb_octop"
UPSTREAM_SLUG = "opencare-skillhub/xyb-Octop"

#: Files whose *content* is user-visible product copy.
LOCALE_FILES: tuple[str, ...] = (
    "dashboard/src/locales/zh.json",
    "dashboard/src/locales/en.json",
    "src/octop/i18n/zh.json",
    "src/octop/i18n/en.json",
)

#: Files that carry artifact / release identifiers.
ARTIFACT_FILES: tuple[str, ...] = (
    "pyproject.toml",
    "scripts/release_download_links.py",
    "desktop/portable/_common.sh",
    "desktop/portable/package.sh",
    ".github/workflows/octop-desktop.yml",
    ".github/workflows/fnos-build-fpk.yml",
    ".github/workflows/release.yml",
    ".github/workflows/docker-publish.yml",
    "fnos/docker/manifest",
    "fnos/native/manifest",
    "fnos/docker/app/docker/docker-compose.yaml",
    "fnos/docker/Dockerfile",
    "fnos/README.md",
    "docker/docker-compose.yml",
    "docker/docker-compose.postgres.yml",
    "docker/docker-compose.mobile.yml",
    "docker/Dockerfile",
    "docker/docker_build.sh",
    "Makefile",
)

#: Documentation. Prose only -- no artifact rules are applied here.
DOC_FILES: tuple[str, ...] = ("README.md", "README_CN.md")

#: Explicit English -> Chinese titles for the HTML shell.
HTML_TITLE_FILES: tuple[str, ...] = ("dashboard/index.html",)


@dataclass(frozen=True)
class Rule:
    """One ordered replacement."""

    name: str
    pattern: re.Pattern[str]
    replacement: str
    #: Which file groups this rule applies to.
    groups: tuple[str, ...] = ("locale",)


def _r(name: str, pattern: str, replacement: str, groups: tuple[str, ...]) -> Rule:
    return Rule(name, re.compile(pattern), replacement, groups)


#: ORDER MATTERS. Anything that must survive verbatim (shell commands, package
#: and environment names) is expressed as a rule with an identical replacement,
#: consuming its match before a broader rule can see it.
RULES: tuple[Rule, ...] = (
    # ---------------------------------------------------------------- protected
    _r(
        "keep-cli-commands",
        r"octop(?= (?:run|update|user|agent|config|service|init|backup|clean|skills|models|channel|cron|plugin|acp|install-browsers|login)\b)",
        "octop",
        ("locale",),
    ),
    _r(
        "keep-installer-paths",
        r"~/\.octop/bin/octop(?:\.cmd)?",
        lambda m: m.group(0),
        ("locale",),
    ),
    _r("keep-data-dir", r"~/\.octop", "~/.octop", ("locale", "artifact", "doc")),
    _r(
        "keep-python-package-dir",
        r"src/octop\b",
        "src/octop",
        ("artifact", "doc"),
    ),
    _r(
        "keep-db-example",
        r"postgresql://octop:octop@[\w.]+:\d+/octop",
        lambda m: m.group(0),
        ("artifact",),
    ),
    _r(
        "keep-local-image-example",
        r"myreg/octop(?=:\w)",
        lambda m: m.group(0),
        ("artifact",),
    ),
    _r("keep-home-env", r"OCTOP_HOME", "OCTOP_HOME", ("locale", "artifact", "doc")),
    _r(
        "keep-env-prefix",
        r"OCTOP_[A-Z_]+",
        lambda m: m.group(0),  # type: ignore[arg-type]
        ("locale", "artifact", "doc"),
    ),
    _r(
        "keep-upstream-dists",
        r"octop-(?:harness|memory|gateway|browser)",
        lambda m: m.group(0),  # type: ignore[arg-type]
        ("locale", "artifact", "doc"),
    ),
    _r(
        "keep-third-party-platform",
        r"OctopBot",
        "OctopBot",
        ("locale",),
    ),
    _r(
        "keep-placeholder-host",
        r"octop\.example\.com",
        "octop.example.com",
        ("locale",),
    ),
    _r(
        "keep-sandbox-prefix",
        r"octop_sandbox",
        "octop_sandbox",
        ("locale",),
    ),
    _r(
        "keep-python-extras",
        r"octop\[[a-z,\s]+\]",
        lambda m: m.group(0),
        ("locale",),
    ),
    _r(
        "keep-data-volume",
        r"octop-data",
        "octop-data",
        ("locale", "artifact"),
    ),
    _r(
        "keep-login-file",
        r"~/octop-login\.txt",
        "~/octop-login.txt",
        ("locale",),
    ),
    _r(
        "keep-bundled-skill-ids",
        r"octop[-_]assistant",
        lambda m: m.group(0),
        ("locale",),
    ),
    _r(
        "keep-tool-invocations",
        r"octop (?=install-browsers|plugin install|service restart|--help|CLI|provider list)",
        "octop ",
        ("locale",),
    ),
    _r(
        "keep-skill-metadata-key",
        r"\"octop\"(?=\s*:)",
        lambda m: m.group(0),
        ("locale",),
    ),
    _r(
        "keep-yaml-metadata-key",
        r"(?m)^(\s*)octop(?=:\s*$)",
        lambda m: m.group(0),
        ("locale",),
    ),
    _r(
        "keep-store-launch-name",
        r"octop-native\.Application",
        "octop-native.Application",
        ("artifact",),
    ),
    _r(
        "keep-acp-cli",
        r"octop acp\b",
        "octop acp",
        ("locale",),
    ),
    _r(
        "keep-bare-cli",
        r"octop(?= (?:update|service|user|install-browsers)\b)",
        "octop",
        ("locale",),
    ),
    _r(
        "keep-image-tag",
        r"octop:latest",
        "octop:latest",
        ("artifact",),
    ),
    _r(
        "keep-scope-identifiers",
        r"octop[-_](?:harness|memory|gateway|browser|desktop|data|login|sandbox)",
        lambda m: m.group(0),
        ("locale",),
    ),
    # ------------------------------------------------------------- artifact names
    _r("artifact-repo-slug", r"TencentCloud/Octop", UPSTREAM_SLUG, ("artifact",)),
    _r(
        "artifact-asset-prefix",
        r"\bOctop-(?=desktop|portable|fnos)",
        f"{ARTIFACT}-",
        ("artifact",),
    ),
    _r(
        "artifact-dist-name",
        r'(?m)^name = "octop"$',
        f'name = "{ARTIFACT}"',
        ("artifact",),
    ),
    _r(
        "artifact-author",
        r'name = "octop contributors"',
        f'name = "{ARTIFACT} contributors"',
        ("artifact",),
    ),
    _r(
        "artifact-workflow-name",
        r"(?m)^name: (?:Octop|XYB-OCTOP)([^\n]*)$",
        lambda m: f"name: {DISPLAY}{m.group(1)}",
        ("artifact",),
    ),
    _r("artifact-pip-install", r"pip install octop==", f"pip install {ARTIFACT}==", ("artifact",)),
    # Only the published image name, anchored to the docker-publish workflow.
    # A broader "anything/octop" rule would also rewrite `src/octop`, the
    # postgres example credentials and local build examples.
    _r(
        "artifact-registry-org",
        r"ghcr\.io/tencentcloud/",
        "ghcr.io/opencare-skillhub/",
        ("artifact",),
    ),
    _r(
        "artifact-hub-image",
        r"(?<=ghcr\.io/tencentcloud/)octop\b",
        ARTIFACT,
        ("artifact",),
    ),
    _r("artifact-appname", r"^appname=octop", f"appname={ARTIFACT}", ("artifact",)),
    _r(
        "artifact-appname-native",
        r"^appname=octop-native",
        f"appname={ARTIFACT}-native",
        ("artifact",),
    ),
    _r(
        "artifact-store-label",
        # Negative lookbehind: never re-match the OCTOP inside XYB-OCTOP.
        r"(?<!XYB-)\bOCTOP\b",
        "XYB-OCTOP",
        ("artifact",),
    ),
    # ------------------------------------------------------------------ display
    # `octop` is the console script (pyproject [project.scripts]) and the name of
    # the container image. A rule that rewrote it in prose produced instructions
    # telling users to run a command that does not exist -- so the command name
    # is protected here and the product name is what changes.
    _r(
        "keep-cli-name-in-prose",
        r"octop(?= (?:command|update|run|init|service|plugin|user|provider|models)\b)"
        r"|octop(?=（)"
        r"|octop(?= 命令)",
        "octop",
        ("locale",),
    ),
    _r(
        "keep-container-image-name",
        r"(?<=/)(?:octop)(?=:)",
        "octop",
        ("artifact",),
    ),
    _r("display-title", r"\bOctop\b", DISPLAY, ("locale", "html", "doc")),
    _r("display-title-lower", r"\boctop\b", DISPLAY, ("html",)),
)


def _apply(text: str, groups: tuple[str, ...]) -> str:
    """Apply every rule whose group matches, in declaration order."""
    for rule in RULES:
        if not set(rule.groups) & set(groups):
            continue
        replacement = rule.replacement
        if callable(replacement):
            text = rule.pattern.sub(replacement, text)
        else:
            text = rule.pattern.sub(replacement, text)
    return text


def _dedupe_console_scripts(text: str) -> str:
    """Collapse the ``[project.scripts]`` block to one entry per command.

    Implemented as a post-pass rather than a regex so re-running the rebrand can
    never append ``xyb-octop = ...`` twice (which would make the file invalid
    TOML). Order is preserved: the legacy alias first, then the new name.
    """
    header = "[project.scripts]"
    if header not in text:
        return text
    head, _, rest = text.partition(header)
    block, newline, tail = rest.partition("\n\n")
    seen: list[str] = []
    for line in block.splitlines():
        stripped = line.strip()
        if not stripped or stripped in seen:
            continue
        seen.append(stripped)
    rebuilt = "\n".join(seen)
    return f"{head}{header}\n{rebuilt}{newline}{tail}" if newline else f"{head}{header}\n{rebuilt}"


def _json_strings(path: Path) -> dict[str, str]:
    """Flatten every string value in a locale bundle to key -> text."""
    data = json.loads(path.read_text(encoding="utf-8"))
    flat: dict[str, str] = {}

    def walk(node: object, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{prefix}.{key}" if prefix else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{prefix}[{index}]")
        elif isinstance(node, str):
            flat[prefix] = node

    walk(data, "")
    return flat


def _rewrite_json(path: Path, dry_run: bool) -> list[tuple[str, str, str]]:
    """Rebrand the string values of a locale bundle, leaving keys alone."""
    original = path.read_text(encoding="utf-8")
    data = json.loads(original)
    changes: list[tuple[str, str, str]] = []

    def walk(node: object, prefix: str) -> object:
        if isinstance(node, dict):
            return {key: walk(value, f"{prefix}.{key}" if prefix else str(key)) for key, value in node.items()}
        if isinstance(node, list):
            return [walk(value, f"{prefix}[{index}]") for index, value in enumerate(node)]
        if isinstance(node, str):
            updated = _apply(node, ("locale",))
            if updated != node:
                changes.append((prefix, node, updated))
            return updated
        return node

    updated_data = walk(data, "")
    if changes and not dry_run:
        path.write_text(
            json.dumps(updated_data, ensure_ascii=False, indent=2) + "\n",
            encoding="utf-8",
        )
    return changes


def _rewrite_text(path: Path, groups: tuple[str, ...], dry_run: bool) -> list[tuple[str, str, str]]:
    original = path.read_text(encoding="utf-8")
    updated = _apply(original, groups)
    if updated == original:
        return []
    changes: list[tuple[str, str, str]] = []
    for before, after in zip(original.splitlines(), updated.splitlines(), strict=False):
        if before != after:
            changes.append(("", before, after))
    if path.name == "pyproject.toml":
        deduped = _dedupe_console_scripts(updated)
        if deduped != updated:
            updated = deduped
    if not dry_run:
        path.write_text(updated, encoding="utf-8")
    return changes


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dry-run", action="store_true", help="report, do not write")
    parser.add_argument("--check", action="store_true", help="exit 1 if anything remains")
    args = parser.parse_args()

    total = 0
    for rel in LOCALE_FILES:
        path = REPO / rel
        if not path.is_file():
            continue
        changes = _rewrite_json(path, args.dry_run or args.check)
        total += len(changes)
        if changes:
            print(f"{rel}: {len(changes)} string(s)")
            if args.dry_run:
                for key, before, after in changes[:4]:
                    print(f"    {key}\n      - {before[:110]}\n      + {after[:110]}")

    for rel in ARTIFACT_FILES:
        path = REPO / rel
        if not path.is_file():
            continue
        changes = _rewrite_text(path, ("artifact",), args.dry_run or args.check)
        total += len(changes)
        if changes:
            print(f"{rel}: {len(changes)} line(s)")
            if args.dry_run:
                for _key, before, after in changes[:3]:
                    print(f"      - {before[:110]}\n      + {after[:110]}")

    for rel in DOC_FILES:
        path = REPO / rel
        if not path.is_file():
            continue
        changes = _rewrite_text(path, ("doc",), args.dry_run or args.check)
        total += len(changes)
        if changes:
            print(f"{rel}: {len(changes)} line(s)")

    for rel in HTML_TITLE_FILES:
        path = REPO / rel
        if not path.is_file():
            continue
        with_title = path.read_text(encoding="utf-8")
        with_title = re.sub(
            r'(name="apple-mobile-web-app-title" content=")[^"]*(")',
            rf"\g<1>{DISPLAY}\g<2>",
            with_title,
        )
        with_title = re.sub(r"<title>[^<]*</title>", f"<title>{DISPLAY}</title>", with_title)
        if with_title != path.read_text(encoding="utf-8"):
            total += 1
            print(f"{rel}: title")
            if not (args.dry_run or args.check):
                path.write_text(with_title, encoding="utf-8")

    if args.check:
        if total:
            print(f"\n{total} surface(s) still carry the legacy brand", file=sys.stderr)
            return 1
        print("rebrand complete: no legacy brand copy left")
        return 0

    verb = "would change" if args.dry_run else "changed"
    print(f"\n{verb} {total} surface(s)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
