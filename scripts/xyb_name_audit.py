#!/usr/bin/env python3
"""XYB naming-surface audit.

One executable gate for the xiaoyibao rebrand. It answers a single question per
surface: *is this a name we are allowed to change, a name we must keep, or a name
we have not decided yet?*

Three groups are checked.

I*  IDENTITY  brand/release surfaces that must become ``xyb-octop`` (artifacts)
              or 小胰宝 (what a patient reads).
C*  CONTRACT  package/data/protocol surfaces that must stay ``octop``.
R*  RESIDUAL  brand copy left on user-visible surfaces (must reach 0).

Two surface classes, two targets -- the product decision is that the **UI shows
the Chinese brand** while every artifact that travels outside the UI keeps the
ASCII name. See ``XYB-UPSTREAM-DIFF.md`` section 5. Machine identifiers are also
checked for CJK, because a Chinese character inside a package, script or artifact
name is a hard failure.

Scope of the residual scan, and why it is shaped this way:

* locale bundles are scanned **value by value**, so a JSON key (``"octop"``) is
  never mistaken for copy;
* dashboard components are scanned through :func:`visible_copy`, which extracts
  only JSX text nodes and translation fallbacks. A whole-file scan of
  ``dashboard/src`` yields a hundred false positives (storage keys, route paths,
  internal URLs, JSDoc) and buries the real finds;
* release plumbing (workflows, Dockerfile, Makefile) is reported as R1b rather
  than gated, because those files are full of contract identifiers by design.

Usage::

    python3 scripts/xyb_name_audit.py             # human summary
    python3 scripts/xyb_name_audit.py --json      # machine summary
    python3 scripts/xyb_name_audit.py --explain   # list the residual copy
    python3 scripts/xyb_name_audit.py --phase pre # expect the pre-rename state

Exit code is 0 when every check passes for the requested phase, else 1.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import tomllib
from dataclasses import dataclass, field
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]

TARGET = "xyb-octop"
UPSTREAM_SLUG = "opencare-skillhub/xyb-Octop"

#: What a patient reads. The product is presented in Chinese; the ASCII target
#: above applies to artifacts only.
DISPLAY_NAME = "小胰宝"

CJK = re.compile(r"[\u3000-\u303f\u4e00-\u9fff\uff00-\uffef]")

# ------------------------------------------------------------------ surfaces

#: Release-visible names. Every entry is also rewritten by scripts/xyb_rebrand.py.
IDENTITY_FILES: tuple[str, ...] = (
    "pyproject.toml",
    "dashboard/public/manifest.json",
    "dashboard/index.html",
    "dashboard/src/locales/en.json",
    "dashboard/src/locales/zh.json",
    "src/octop/i18n/en.json",
    "src/octop/i18n/zh.json",
    "fnos/docker/manifest",
    "fnos/native/manifest",
    "fnos/docker/app/docker/docker-compose.yaml",
    "fnos/docker/Dockerfile",
    "docker/docker-compose.yml",
    "docker/Dockerfile",
    "docker/docker-compose.postgres.yml",
    "docker/docker-compose.mobile.yml",
    "docker/docker_build.sh",
    "desktop/portable/_common.sh",
    "desktop/portable/package.sh",
    "scripts/release_download_links.py",
    "Makefile",
    "README.md",
    "README_CN.md",
    ".github/workflows/release.yml",
    ".github/workflows/docker-publish.yml",
    ".github/workflows/octop-desktop.yml",
    ".github/workflows/fnos-build-fpk.yml",
)

#: Surfaces a patient actually reads. R1 gates these.
USER_VISIBLE_FILES: tuple[str, ...] = (
    "dashboard/index.html",
    "dashboard/public/manifest.json",
    "dashboard/src/locales/zh.json",
    "dashboard/src/locales/en.json",
    "src/octop/i18n/zh.json",
    "src/octop/i18n/en.json",
    "fnos/docker/manifest",
    "fnos/native/manifest",
)

#: Component trees whose hard-coded fallback strings also reach the patient.
USER_VISIBLE_GLOBS: tuple[str, ...] = ("dashboard/src/**/*.tsx",)
SKIP_PATH_PARTS = frozenset({"node_modules", "dist", "__tests__"})

ARTIFACT_NAME_PATTERNS: dict[str, str] = {
    "desktop/portable/_common.sh": r'"[A-Za-z0-9_.{}$-]*[Oo]ctop-[A-Za-z0-9_.{}$-]*"',
    "scripts/release_download_links.py": r'f"[A-Za-z0-9_.{}$-]*[Oo]ctop-[A-Za-z0-9_.{}$-]*"',
    ".github/workflows/octop-desktop.yml": r"[A-Za-z0-9_.{}$-]*[Oo]ctop-[A-Za-z0-9_.{}$-]*",
    ".github/workflows/fnos-build-fpk.yml": r"[A-Za-z0-9_.{}$-]*[Oo]ctop-[A-Za-z0-9_.{}$-]*",
}

# ------------------------------------------------------------------ matching

#: Tokens that legitimately keep the legacy spelling: the console script, the
#: import package, the on-disk layout, environment prefixes, protocol headers,
#: upstream distributions and internal configuration values. Every entry is also
#: preserved by scripts/xyb_rebrand.py -- the two lists describe the same
#: contract from two directions (allow vs. preserve).
CONTRACT_TOKENS = re.compile(
    r"(?:"
    r"octop-(?:harness|memory|gateway|browser)"
    r"|src/octop/"
    r"|octop-item-"
    r"|octop\.[a-z_]+"
    r"|\.octop(?:-auth|-root-probe)?\b"
    r"|octop\.example\.com"
    r"|OctopBot"
    r"|OCTOP_[A-Z_]+"
    r"|X-Octop-[A-Za-z-]+"
    r"|octop-desktop-[a-z-]+\.service"
    r"|octop-login\.txt"
    r"|octop-boot[a-z-]*"
    r"|octop:chunk-reload"
    r"|octop:latest"
    r"|octop\.Application"
    r"|octop-native"
    r"|octop_sandbox"
    r"|octop-data\b"
    r"|octop\.db\b"
    r"|octop\[[a-z,\s]+\]"
    r"|octop[-_]assistant"
    r"|octopbot[A-Za-z_]*"
    r"|askOctop[A-Za-z]*"
    r"|copyErrorForOctop"
    r"|octopDesc|sectionOctop|preset-Octop"
    r"|XYB-OCTOP"
    # Prose that tells the user which command to run. Rewriting the command name
    # here made the instruction unexecutable, so it is kept verbatim.
    r"|octop 命令"
    r"|octop command"
    r"|octop（"
    r"|octop[ ](?:run|update|init|user|agent|config|service|backup|clean|skills|models|"
    r"channel|cron|plugin|acp|install-browsers|login|memory|version|completion|xyb)[ \t(（]"
    r"|`octop[^`]*`"
    r")"
)

#: A bare brand word, with identifier boundaries so ``xyb-octop`` and
#: ``octop-harness`` never trigger it.
BRAND_WORD = re.compile(r"(?<![A-Za-z0-9-])[Oo]ctop(?![A-Za-z0-9-])")

#: Contexts in which a nearby brand word is a name we keep, not copy we missed.
PRESERVED_CONTEXTS: tuple[str, ...] = (
    "octop run",
    "octop update",
    "octop init",
    "octop acp",
    "octop install-browsers",
    "octop plugin install",
    "octop service restart",
    "octop --help",
    "octop CLI",
    "octop provider list",
    "octop user passwd",
    "octop 命令",
    "octop command",
    "octop（",
    "octop is not found",
    "~/.octop",
    "octop.example.com",
    "octop-native",
    "octop_sandbox",
    "octop[browser]",
    "octop-data",
    "octop:latest",
    "octop.cmd",
    "octop.db",
    "octop_token",
    '"octop":',
    " octop:",
    "octop-assistant",
    "octop_assistant",
    "octop-boot",
    "octop:chunk-reload",
    "octop.Application",
    "Octop mascot",
    "X-Octop-",
    "storageKey",
    'path: "/octop/',
)

#: Locale keys whose value is a template or a machine label rather than prose.
PRESERVED_KEYS: frozenset[str] = frozenset(
    {
        "skills.contentPlaceholder",
        "skills.newSkillTemplate",
        "slash.fields.octop",
    }
)

# ---------------------------------------------------------------- extraction

#: JSX text node containing a brand word: `>some copy<`.
_JSX_TEXT = re.compile(r">([^<>{}]*\b[Oo]ctop\b[^<>{}]*)<")
#: t("key", "fallback") -- the fallback is what ships if a key is missing.
_T_CALL = re.compile(r"\bt\(\s*(\"[^\"]*\"|'[^']*')\s*,\s*(\"[^\"]*\"|'[^']*')")


def read(rel: str) -> str | None:
    path = REPO / rel
    if not path.is_file():
        return None
    return path.read_text(encoding="utf-8", errors="replace")


def _context_ok(text: str, start: int, end: int, window: int = 40) -> bool:
    snippet = text[max(0, start - window) : end + window]
    return any(marker in snippet for marker in PRESERVED_CONTEXTS)


def display_leaks(text: str) -> list[str]:
    """Brand words used as product copy, with surrounding context."""
    out: list[str] = []
    for match in BRAND_WORD.finditer(text):
        if _context_ok(text, match.start(), match.end()):
            continue
        out.append(text[max(0, match.start() - 40) : match.end() + 40].replace("\n", "\\n"))
    return out


def token_hits(text: str) -> int:
    """Brand tokens that are not part of a documented contract identifier."""
    allowed = [m.span() for m in CONTRACT_TOKENS.finditer(text)]
    hits = 0
    for match in BRAND_WORD.finditer(text):
        start, end = match.span()
        if any(a <= start and end <= b for a, b in allowed):
            continue
        hits += 1
    return hits


def locale_value_leaks(rel: str) -> list[tuple[str, str]]:
    """Scan only the *values* of a locale bundle, which is where prose lives."""
    text = read(rel)
    if text is None:
        return []
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        return []

    found: list[tuple[str, str]] = []

    def walk(node: object, prefix: str) -> None:
        if isinstance(node, dict):
            for key, value in node.items():
                walk(value, f"{prefix}.{key}" if prefix else str(key))
        elif isinstance(node, list):
            for index, value in enumerate(node):
                walk(value, f"{prefix}[{index}]")
        elif isinstance(node, str):
            if prefix in PRESERVED_KEYS:
                return
            if display_leaks(node):
                found.append((prefix, node))

    walk(data, "")
    return found


def visible_copy(path: Path) -> list[str]:
    """Strings in a component a patient could read.

    Only JSX text nodes and translation fallbacks: a whole-file scan produces a
    hundred false positives and stops being a gate.
    """
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []
    found = list(_JSX_TEXT.findall(text))
    found.extend(fallback for _key, fallback in _T_CALL.findall(text))
    return found


def _globbed_visible_sources() -> list[str]:
    out: list[str] = []
    for pattern in USER_VISIBLE_GLOBS:
        for path in sorted(REPO.glob(pattern)):
            if not path.is_file() or ".test." in path.name:
                continue
            if SKIP_PATH_PARTS & set(path.parts):
                continue
            out.append(path.relative_to(REPO).as_posix())
    return out


def _component_leaks(rel: str) -> list[str]:
    return [snippet for snippet in visible_copy(REPO / rel) if display_leaks(snippet)]


def _visible_leaks(rel: str) -> int:
    if rel.endswith(".json"):
        return len(locale_value_leaks(rel))
    if rel.endswith(".tsx"):
        return len(_component_leaks(rel))
    text = read(rel)
    return len(display_leaks(text)) if text else 0


# ------------------------------------------------------------------- results


@dataclass
class Check:
    cid: str
    title: str
    ok: bool
    detail: str = ""


@dataclass
class Audit:
    checks: list[Check] = field(default_factory=list)

    def add(self, cid: str, title: str, ok: bool, detail: str = "") -> None:
        self.checks.append(Check(cid, title, ok, detail))

    @property
    def failed(self) -> list[Check]:
        return [c for c in self.checks if not c.ok]


def pyproject() -> dict:
    return tomllib.loads((REPO / "pyproject.toml").read_text(encoding="utf-8"))


# ---------------------------------------------------------------------- main


def _explain() -> int:
    found_any = False
    for rel in (*USER_VISIBLE_FILES, *_globbed_visible_sources()):
        if rel.endswith(".json"):
            leaks = [f"{key}: {value[:100]}" for key, value in locale_value_leaks(rel)]
        elif rel.endswith(".tsx"):
            leaks = _component_leaks(rel)
        else:
            text = read(rel) or ""
            leaks = display_leaks(text)
        if not leaks:
            continue
        found_any = True
        print(f"\n{rel}: {len(leaks)}")
        for leak in leaks:
            print(f"    {leak}")
    if not found_any:
        print("no residual brand copy on user-visible surfaces")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit the XYB naming surfaces.")
    parser.add_argument("--json", action="store_true", help="emit JSON instead of text")
    parser.add_argument(
        "--explain",
        action="store_true",
        help="list the residual brand copy per file, then exit",
    )
    parser.add_argument(
        "--phase",
        choices=("pre", "post"),
        default="post",
        help="'post' asserts the rebrand landed, 'pre' asserts the legacy state",
    )
    args = parser.parse_args()

    if args.explain:
        return _explain()

    expect_new = args.phase == "post"
    audit = Audit()

    # -------------------------------------------------------------- pyproject
    project = pyproject().get("project", {})
    dist_name = str(project.get("name", ""))
    audit.add(
        "I1",
        f"pyproject [project].name == {TARGET}",
        dist_name == TARGET if expect_new else dist_name == "octop",
        f"found {dist_name!r}",
    )

    authors = project.get("authors") or [{}]
    author = str(authors[0].get("name", ""))
    audit.add(
        "I2",
        "pyproject author string rebranded",
        (TARGET in author) if expect_new else (author == "octop contributors"),
        f"found {author!r}",
    )

    scripts = project.get("scripts", {})
    audit.add(
        "I3",
        "console script 'octop' retained (compat)",
        "octop" in scripts,
        f"scripts: {sorted(scripts)}",
    )
    audit.add(
        "I4",
        f"console script {TARGET} published",
        (TARGET in scripts) if expect_new else True,
        f"scripts: {sorted(scripts)}",
    )

    deps = " ".join(str(d) for d in project.get("dependencies", []))
    for mod in ("octop-harness", "octop-memory", "octop-gateway", "octop-browser"):
        audit.add(
            f"C-dep-{mod}",
            f"upstream dependency {mod} unchanged",
            mod in deps,
            "missing from [project].dependencies",
        )

    # ---------------------------------------------------------- PWA + shell
    manifest_raw = read("dashboard/public/manifest.json") or "{}"
    manifest = json.loads(manifest_raw)
    pwa_short = str(manifest.get("short_name", ""))
    audit.add(
        "I5-short_name",
        f"PWA short_name == {DISPLAY_NAME}",
        (pwa_short == DISPLAY_NAME) if expect_new else (pwa_short == "Octop"),
        f"found {pwa_short!r}",
    )
    pwa_name = str(manifest.get("name", ""))
    audit.add(
        "I5-name",
        f"PWA name is the {DISPLAY_NAME} brand",
        (pwa_name.startswith(DISPLAY_NAME)) if expect_new else (pwa_name == "Octop"),
        f"found {pwa_name!r}",
    )

    index_html = read("dashboard/index.html") or ""
    apple_title = ""
    if match := re.search(r'name="apple-mobile-web-app-title"\s+content="([^"]*)"', index_html):
        apple_title = match.group(1)
    index_title = ""
    if match := re.search(r"<title>([^<]*)</title>", index_html):
        index_title = match.group(1).strip()
    audit.add(
        "I6-title",
        f"index.html <title> shows {DISPLAY_NAME}",
        (DISPLAY_NAME in index_title) if expect_new else (index_title == "Octop"),
        f"<title>={index_title!r}",
    )
    audit.add(
        "I6-apple",
        f"index.html apple title shows {DISPLAY_NAME}",
        (DISPLAY_NAME in apple_title) if expect_new else (apple_title == "Octop"),
        f"apple={apple_title!r}",
    )

    # ----------------------------------------------------------- FnOS store
    for rel in ("fnos/docker/manifest", "fnos/native/manifest"):
        text = read(rel)
        if text is None:
            audit.add(f"I8-{rel}", f"{rel} exists", False, "file missing")
            continue
        display = appname = ""
        for line in text.splitlines():
            if line.startswith("display_name="):
                display = line.split("=", 1)[1]
            elif line.startswith("appname="):
                appname = line.split("=", 1)[1]
        # display_name is what the store shows a person, so it carries the
        # Chinese brand; appname is the machine identifier and stays ASCII.
        audit.add(
            f"I8-{rel}",
            f"{rel} display_name rebranded",
            (DISPLAY_NAME in display) if expect_new else (display == "OCTOP"),
            f"found {display!r}",
        )
        audit.add(
            f"I8b-{rel}",
            f"{rel} appname rebranded",
            appname.startswith(TARGET) if expect_new else appname.startswith("octop"),
            f"found {appname!r}",
        )

    # ------------------------------------------------------- release plumbing
    release_yml = read(".github/workflows/release.yml") or ""
    audit.add(
        "I9",
        "release notes install line rebranded",
        (f"pip install {TARGET}==" in release_yml)
        if expect_new
        else ("pip install octop==" in release_yml),
        "no matching pip install line",
    )

    # Check the actual publish step, not a comment that happens to mention it.
    docker_publish = read(".github/workflows/docker-publish.yml") or ""
    hub_lines = [line for line in docker_publish.splitlines() if "hub=" in line]
    audit.add(
        "I10",
        "Docker Hub image suffix rebranded",
        any(f"/{TARGET}" in line for line in hub_lines)
        if expect_new
        else any("/octop" in line for line in hub_lines),
        f"hub lines: {hub_lines or 'none found'}",
    )

    links_py = read("scripts/release_download_links.py") or ""
    audit.add(
        "I11",
        f"release_download_links GITHUB_REPO == {UPSTREAM_SLUG}",
        (UPSTREAM_SLUG in links_py) if expect_new else ("TencentCloud/Octop" in links_py),
        "GITHUB_REPO not switched to the fork",
    )
    asset_prefix = f"{TARGET}-" if expect_new else "Octop-"
    audit.add(
        "I11b",
        f"release asset prefix == {asset_prefix}",
        f'"{asset_prefix}' in links_py or f"{asset_prefix}{{" in links_py,
        "asset filename prefixes not updated",
    )

    common_sh = read("desktop/portable/_common.sh") or ""
    audit.add(
        "I12",
        "portable/desktop artifact names rebranded",
        (f"{TARGET}-portable-" in common_sh) if expect_new else ("Octop-portable-" in common_sh),
        "desktop/portable/_common.sh filename helper not updated",
    )

    desktop_yml = read(".github/workflows/octop-desktop.yml") or ""
    audit.add(
        "I13",
        "desktop workflow artifact globs rebranded",
        (f"{TARGET}-" in desktop_yml) if expect_new else ("Octop-" in desktop_yml),
        "workflow does not reference the rebranded artifact names",
    )

    # ----------------------------------------------------------- ASCII gate
    # Only identifiers that travel outside the UI must be ASCII: package
    # metadata, console scripts, artifact filenames and store identifiers. The
    # display name is deliberately Chinese and is gated by I5/I6 instead.
    name_fields: list[tuple[str, str]] = [
        ("pyproject.toml [project].name", dist_name),
        ("pyproject.toml [project].authors[0].name", author),
    ]
    name_fields.extend((f"pyproject.toml script {key}", key) for key in scripts)
    name_fields.append(("manifest.json id", str(manifest.get("id", ""))))
    for rel in ("fnos/docker/manifest", "fnos/native/manifest"):
        text = read(rel) or ""
        for line in text.splitlines():
            key, _, value = line.partition("=")
            if key in {"appname", "desktop_applaunchname"}:
                name_fields.append((f"{rel} {key}", value))

    bad_fields = [(label, value) for label, value in name_fields if CJK.search(value)]
    audit.add(
        "I14",
        "artifact / package name fields are ASCII-only",
        not bad_fields,
        "; ".join(f"{label}={value!r}" for label, value in bad_fields[:4]),
    )

    bad_artifacts: list[str] = []
    for rel, pattern in ARTIFACT_NAME_PATTERNS.items():
        text = read(rel)
        if not text:
            continue
        for match in re.finditer(pattern, text):
            if CJK.search(match.group(0)):
                bad_artifacts.append(f"{rel}: {match.group(0)}")
    audit.add(
        "I15",
        "artifact filename tokens are ASCII-only",
        not bad_artifacts,
        "; ".join(bad_artifacts[:4]),
    )

    # ------------------------------------------------------------ contracts
    paths_py = read("src/octop/infra/utils/paths.py") or ""
    audit.add(
        "C1",
        "default data directory stays ~/.octop",
        'Path.home() / ".octop"' in paths_py,
        "paths.py no longer resolves ~/.octop",
    )
    audit.add(
        "C2",
        "OCTOP_HOME override still honoured",
        "OCTOP_HOME" in paths_py,
        "OCTOP_HOME override removed",
    )
    audit.add(
        "C3",
        "import package src/octop/ intact",
        (REPO / "src" / "octop" / "__init__.py").is_file(),
        "package dir missing",
    )
    password_py = read("src/octop/infra/setup/password_file.py") or ""
    audit.add(
        "C4",
        "generated file octop-login.txt unchanged",
        "octop-login.txt" in password_py,
        "password file name changed (breaks existing installs)",
    )
    desktop_setup = read("src/octop/infra/desktop/setup.py") or ""
    audit.add(
        "C5",
        "systemd unit names octop-desktop-* unchanged",
        "octop-desktop-xvnc.service" in desktop_setup,
        "systemd unit names changed",
    )
    dockerfile = read("docker/Dockerfile") or ""
    audit.add(
        "C6",
        "container data path /data/.octop unchanged",
        "/data/.octop" in dockerfile,
        "container data path changed",
    )
    compose = read("docker/docker-compose.yml") or ""
    audit.add(
        "C7",
        "compose volume still mounts OCTOP_DATA -> /data/.octop",
        "OCTOP_DATA" in compose and "/data/.octop" in compose,
        "compose data mount changed",
    )
    audit.add(
        "C8",
        "HTTP header X-Octop-Agent-Id unchanged",
        all(
            "X-Octop-Agent-Id" in (read(rel) or "")
            for rel in ("dashboard/src/api/request.ts", "src/octop/api/routers/mbti.py")
        ),
        "protocol header renamed (breaks mixed-version dashboards)",
    )

    # ------------------------------------------------------------- residual
    visible_residual: dict[str, int] = {}
    for rel in USER_VISIBLE_FILES:
        count = _visible_leaks(rel)
        if count:
            visible_residual[rel] = count
    for rel in _globbed_visible_sources():
        count = _visible_leaks(rel)
        if count:
            visible_residual[rel] = count
    audit.add(
        "R1",
        "no residual brand copy on user-visible surfaces",
        not visible_residual if expect_new else True,
        json.dumps(visible_residual, ensure_ascii=False) if visible_residual else "",
    )

    plumbing_residual = 0
    for rel in IDENTITY_FILES:
        if rel in USER_VISIBLE_FILES:
            continue
        text = read(rel)
        if text is None:
            continue
        plumbing_residual += token_hits(text)
    audit.add(
        "R1b",
        "release-plumbing identifier tokens (informational)",
        True,
        str(plumbing_residual),
    )

    total_brand = 0
    contract_hits = 0
    scanned = 0
    skip = {".git", "node_modules", ".venv", "__pycache__", "dist", "build", ".workbuddy"}
    binary = {".png", ".jpg", ".jpeg", ".ico", ".svg", ".woff", ".woff2", ".lock"}
    for path in REPO.rglob("*"):
        if not path.is_file() or set(path.parts) & skip:
            continue
        if path.suffix.lower() in binary:
            continue
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        scanned += 1
        total_brand += token_hits(text)
        contract_hits += len(CONTRACT_TOKENS.findall(text))
    audit.add("R2", "repo-wide non-contract brand tokens (informational)", True, str(total_brand))
    audit.add(
        "R3",
        "repo-wide contract tokens that a blind replace would break (informational)",
        True,
        str(contract_hits),
    )
    audit.add("R4", "files scanned (informational)", True, str(scanned))

    # --------------------------------------------------------------- output
    if args.json:
        print(
            json.dumps(
                {
                    "phase": args.phase,
                    "target": TARGET,
                    "failed": len(audit.failed),
                    "residual_by_file": visible_residual,
                    "plumbing_residual_tokens": plumbing_residual,
                    "repo_wide_brand_tokens": total_brand,
                    "checks": [c.__dict__ for c in audit.checks],
                },
                indent=2,
                ensure_ascii=True,
            )
        )
        return 0 if not audit.failed else 1

    for check in audit.checks:
        mark = "PASS" if check.ok else "FAIL"
        line = f"[{mark}] {check.cid:<16} {check.title}"
        # `detail` explains what went wrong, so printing it on a PASS line reads
        # as a contradiction ("PASS ... package dir missing").
        if check.detail and not check.ok:
            line += f"  ({check.detail})"
        print(line)
    print()
    print(
        f"phase={args.phase} target={TARGET} failed={len(audit.failed)} "
        f"repo_wide_brand_tokens={total_brand}"
    )
    return 0 if not audit.failed else 1


if __name__ == "__main__":
    sys.exit(main())
