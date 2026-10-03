#!/usr/bin/env python3
"""XYB MCP handshake probe (stdlib only).

Speaks real MCP over stdio to each configured server and reports what the server
*actually* answers: ``serverInfo.version`` from ``initialize`` and the tool names
from ``tools/list``. This is the FR-3.1/FR-3.2 gate: a server is "connected" only
when it completes the JSON-RPC exchange, not when its config line exists.

Servers are declared in :data:`SERVERS`. Every one of them can be redirected with
an environment variable, so the probe works on a machine that has the sources in
a different place than the author's.

Usage::

    python3 scripts/xyb_mcp_probe.py             # probe every server
    python3 scripts/xyb_mcp_probe.py xyb-veeva   # probe one server by name
    python3 scripts/xyb_mcp_probe.py --list      # show the plan, start nothing
    python3 scripts/xyb_mcp_probe.py --json      # machine-readable report

Exit code 0 when every requested server handshakes, 1 otherwise, 2 on bad usage.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

PROTOCOL_VERSION = "2024-11-05"
CLIENT_INFO = {"name": "xyb-check-mcp", "version": "1.0.0"}


@dataclass(frozen=True)
class Server:
    """One MCP endpoint and how to start it."""

    name: str
    channel: str
    argv: tuple[str, ...]
    env: dict[str, str] = field(default_factory=dict)
    cwd: str | None = None
    #: Extra note printed when the probe fails, e.g. how to install the package.
    hint: str = ""
    #: Set for servers that are optional (need a key the user may not have).
    optional: bool = False


def _npx(package: str, binary: str | None = None) -> tuple[str, ...]:
    """An npx argv.

    ``binary`` is needed when a package ships more than one bin, or a single bin
    not named after the package: ``npx -y <pkg>`` then cannot choose and exits
    with "could not determine executable to run".
    """
    if binary:
        return ("npx", "-y", "-p", package, binary)
    return ("npx", "-y", package)


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[1]


def xyb_playwright_browsers_path() -> Path:
    """Our own Playwright browser cache, kept out of the OS default location.

    The OS default (``~/Library/Caches/ms-playwright`` on macOS) can be locked by
    TCC, which makes ``playwright install`` abort and leaves a scraping server
    that starts but answers nothing. A plain cache directory we own avoids that
    entirely, and is what ``scripts/xyb-bootstrap.sh`` installs into.
    """
    configured = os.environ.get("XYB_PLAYWRIGHT_BROWSERS_PATH")
    if configured:
        return Path(configured).expanduser()
    # Inside the checkout: writable in a sandbox, ignored by git, and a sensible
    # place for a self-hosted install to keep a browser it owns.
    return _repo_root() / ".cache" / "xyb-playwright"


def _playwright_browsers_path() -> str:
    """The value to hand chictr, or "" to leave the child's environment alone.

    An explicit ``XYB_PLAYWRIGHT_BROWSERS_PATH`` or ``PLAYWRIGHT_BROWSERS_PATH``
    always wins. Otherwise we only override when our own cache actually exists,
    so a host that is happy with the OS default keeps using it.
    """
    explicit = os.environ.get("XYB_PLAYWRIGHT_BROWSERS_PATH") or os.environ.get(
        "PLAYWRIGHT_BROWSERS_PATH"
    )
    if explicit:
        return explicit
    ours = xyb_playwright_browsers_path()
    return str(ours) if ours.is_dir() else ""


def _veeva_dir() -> str:
    """Resolve the local ctv-mcp-server checkout.

    ``XYB_VEEVA_DIR`` wins; otherwise fall back to a sibling ``Downloads``
    checkout, which is where the source currently lives on the author's machine.
    """
    configured = os.environ.get("XYB_VEEVA_DIR")
    if configured:
        return configured
    return str(Path.home() / "Downloads" / "ctv-mcp-server")


def build_servers() -> list[Server]:
    """Return the server table, with paths resolved from the environment."""
    veeva_dir = _veeva_dir()
    return [
        Server(
            name="xyb-veeva",
            channel="veeva",
            argv=("node", str(Path(veeva_dir) / "dist" / "index.js")),
            cwd=veeva_dir,
            hint=(
                f"build it first: cd {veeva_dir} && npm install && npm run build "
                "(override the location with XYB_VEEVA_DIR)"
            ),
        ),
        Server(
            name="xyb-chictr",
            channel="chictr",
            argv=_npx("chictr-mcp-server@2.0.2"),
            # This server scrapes with Playwright. Its postinstall runs
            # `playwright install chromium`, and on macOS the default cache
            # (~/Library/Caches/ms-playwright) can be locked by TCC so the
            # install aborts and the package never finishes, leaving the server
            # with no stdout. Pointing the browser cache at a writable directory
            # is what makes the handshake work here; see the hint below.
            env={"PLAYWRIGHT_BROWSERS_PATH": _playwright_browsers_path()},
            hint=(
                "first run downloads the package and a Chromium; if the install "
                "aborts on a locked ~/Library/Caches/ms-playwright, set "
                "PLAYWRIGHT_BROWSERS_PATH to a writable dir and run "
                "`npx playwright@1.49.1 install chromium`. The site may still ask "
                "for human verification, which this probe does not bypass"
            ),
        ),
        Server(
            name="xyb-clinicaltrials",
            channel="clinicaltrials",
            argv=_npx("xiaoyibao-clinical-trials@1.0.0"),
            hint="no credentials needed; needs network access to ClinicalTrials.gov",
        ),
        # chinadrugs is deliberately NOT here: upstream ships it as a CLI +
        # session-cookie *skill* (scripts/main.py, no MCP server), so it is
        # imported as a skill into the trial-matching expert rather than probed
        # as an MCP endpoint. Listing a non-existent server produced a permanent
        # false FAIL.
        Server(
            name="xyb-pubmed",
            channel="literature",
            argv=_npx("mcp-pubmed-llm-server@3.0.0"),
            env={"PUBMED_EMAIL": os.environ.get("PUBMED_EMAIL", "")},
            hint="works without a key (rate limited); PUBMED_API_KEY raises the limit",
            optional=True,
        ),
        Server(
            name="xyb-metaso",
            channel="search",
            argv=_npx("metaso-search-mcp@1.1.2", binary="metaso-mcp"),
            env={"METASO_API_KEY": os.environ.get("METASO_API_KEY", "")},
            hint="requires METASO_API_KEY; skipped when unset",
            optional=True,
        ),
        Server(
            name="xyb-dayi",
            channel="drug-search",
            argv=_npx("@xiaoyibao_2025/dayi-mcp-server@0.1.7"),
            hint="no credentials; queries m.dayi.org.cn",
            optional=True,
        ),
    ]


@dataclass
class ProbeResult:
    name: str
    channel: str
    ok: bool
    status: str
    version: str = ""
    tools: list[str] = field(default_factory=list)
    error: str = ""
    hint: str = ""
    skipped: bool = False

    def as_dict(self) -> dict:
        return {
            "name": self.name,
            "channel": self.channel,
            "ok": self.ok,
            "status": self.status,
            "version": self.version,
            "tool_count": len(self.tools),
            "tools": self.tools,
            "error": self.error,
            "hint": self.hint,
            "skipped": self.skipped,
        }


class StdioSession:
    """Minimal blocking MCP stdio client: one request, one response."""

    def __init__(self, server: Server, timeout: float) -> None:
        self.server = server
        self.timeout = timeout
        self._proc: subprocess.Popen[str] | None = None
        self._next_id = 0

    def __enter__(self) -> StdioSession:
        env = dict(os.environ)
        env.update({k: v for k, v in self.server.env.items() if v})
        self._proc = subprocess.Popen(
            list(self.server.argv),
            cwd=self.server.cwd,
            env=env,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        self._stderr: list[str] = []
        self._err_thread = threading.Thread(target=self._drain_stderr, daemon=True)
        self._err_thread.start()
        return self

    def _drain_stderr(self) -> None:
        proc = self._proc
        if proc is None or proc.stderr is None:
            return
        try:
            for line in proc.stderr:
                self._stderr.append(line)
        except (ValueError, OSError):
            return

    def __exit__(self, *exc: object) -> None:
        proc = self._proc
        if proc is None:
            return
        for stream in (proc.stdin, proc.stdout):
            try:
                if stream is not None:
                    stream.close()
            except OSError:
                pass
        try:
            proc.terminate()
            proc.wait(timeout=5)
        except (subprocess.TimeoutExpired, OSError):
            try:
                proc.kill()
                proc.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                pass

    @property
    def stderr_tail(self) -> str:
        return "".join(getattr(self, "_stderr", [])[-15:]).strip()

    def _send(self, payload: dict) -> None:
        proc = self._proc
        if proc is None or proc.stdin is None:
            raise RuntimeError("process not started")
        proc.stdin.write(json.dumps(payload) + "\n")
        proc.stdin.flush()

    def request(self, method: str, params: dict | None = None) -> dict:
        """Send one request and return its result, or raise on JSON-RPC error."""
        self._next_id += 1
        request_id = self._next_id
        body: dict = {"jsonrpc": "2.0", "id": request_id, "method": method}
        if params is not None:
            body["params"] = params
        self._send(body)
        return self._read_response(request_id)

    def notify(self, method: str, params: dict | None = None) -> None:
        body: dict = {"jsonrpc": "2.0", "method": method}
        if params is not None:
            body["params"] = params
        self._send(body)

    def _read_response(self, request_id: int) -> dict:
        """Block until the reply to ``request_id`` arrives, or the timeout fires.

        Uses ``select`` on the child's stdout descriptor rather than a bare
        blocking read, so a server that starts but never answers cannot hang the
        probe. A first run may have to download an npm package, hence the
        generous default timeout.
        """
        proc = self._proc
        if proc is None or proc.stdout is None:
            raise RuntimeError("process not started")

        import select

        fd = proc.stdout.fileno()
        deadline = time.monotonic() + self.timeout
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError(f"no reply to {request_id} within {self.timeout:.0f}s")
            try:
                ready, _, _ = select.select([fd], [], [], remaining)
            except (OSError, ValueError) as exc:
                raise RuntimeError(f"stdout closed while waiting for reply: {exc}") from exc
            if not ready:
                continue
            line = proc.stdout.readline()
            if not line:
                raise RuntimeError("server closed stdout before replying")
            line = line.strip()
            if not line:
                continue
            try:
                message = json.loads(line)
            except json.JSONDecodeError:
                # Servers sometimes print banners; ignore non-JSON lines.
                continue
            if not isinstance(message, dict):
                continue
            if message.get("id") != request_id:
                continue
            if "error" in message:
                error = message["error"]
                if isinstance(error, dict):
                    raise RuntimeError(
                        f"JSON-RPC error {error.get('code')}: {error.get('message')}"
                    )
                raise RuntimeError(f"JSON-RPC error: {error}")
            result = message.get("result")
            return result if isinstance(result, dict) else {}


def probe(server: Server, timeout: float) -> ProbeResult:
    """Run one full handshake against ``server``."""
    if shutil.which(server.argv[0]) is None:
        return ProbeResult(
            name=server.name,
            channel=server.channel,
            ok=False,
            status="MISSING_BINARY",
            error=f"{server.argv[0]!r} not found on PATH",
            hint=server.hint,
        )
    if server.cwd and not Path(server.cwd).is_dir():
        return ProbeResult(
            name=server.name,
            channel=server.channel,
            ok=False,
            status="MISSING_SOURCE",
            error=f"working directory not found: {server.cwd}",
            hint=server.hint,
        )
    entry = (
        Path(server.argv[1]) if len(server.argv) > 1 and server.argv[1].endswith(".js") else None
    )
    if entry is not None and not entry.is_file():
        return ProbeResult(
            name=server.name,
            channel=server.channel,
            ok=False,
            status="MISSING_SOURCE",
            error=f"entrypoint not found: {entry}",
            hint=server.hint,
        )

    try:
        with StdioSession(server, timeout) as session:
            init = session.request(
                "initialize",
                {
                    "protocolVersion": PROTOCOL_VERSION,
                    "capabilities": {},
                    "clientInfo": CLIENT_INFO,
                },
            )
            session.notify("notifications/initialized")
            listing = session.request("tools/list")
            info = init.get("serverInfo")
            version = ""
            if isinstance(info, dict):
                version = str(info.get("version", ""))
            tools_raw = listing.get("tools")
            tools: list[str] = []
            if isinstance(tools_raw, list):
                for item in tools_raw:
                    if isinstance(item, dict) and item.get("name"):
                        tools.append(str(item["name"]))
            return ProbeResult(
                name=server.name,
                channel=server.channel,
                ok=True,
                status="OK",
                version=version,
                tools=tools,
            )
    except TimeoutError as exc:
        return ProbeResult(
            name=server.name,
            channel=server.channel,
            ok=False,
            status="TIMEOUT",
            error=str(exc),
            hint=server.hint,
        )
    except FileNotFoundError as exc:
        return ProbeResult(
            name=server.name,
            channel=server.channel,
            ok=False,
            status="MISSING_BINARY",
            error=str(exc),
            hint=server.hint,
        )
    except (RuntimeError, OSError, ValueError) as exc:
        return ProbeResult(
            name=server.name,
            channel=server.channel,
            ok=False,
            status="FAILED",
            error=str(exc),
            hint=server.hint,
        )


def _should_skip(server: Server, *, include_optional: bool) -> str:
    """Return a reason to skip, or '' to run.

    Two different things are being decided here, and conflating them produced a
    false FAIL: `--include-optional` is about *credentials the operator has not
    set up yet*, not about software that is simply absent. A missing checkout or
    entrypoint is a hard prerequisite, so it is skipped (or reported as
    MISSING_SOURCE) regardless of that flag -- running it would only ever produce
    "server closed stdout before replying".
    """
    # Hard prerequisites: nothing to run at all.
    if server.cwd and not Path(server.cwd).is_dir():
        return f"checkout not found at {server.cwd}"
    entry = Path(server.argv[1]) if len(server.argv) > 1 and server.argv[1].endswith(".js") else None
    if entry is not None and not entry.is_file():
        return f"entrypoint not found at {entry}"

    if include_optional or not server.optional:
        return ""
    if server.name == "xyb-metaso" and not os.environ.get("METASO_API_KEY"):
        return "METASO_API_KEY not set"
    return ""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("names", nargs="*", help="server names to probe (default: all)")
    parser.add_argument("--list", action="store_true", help="print the plan and exit")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("XYB_MCP_TIMEOUT", "60")),
        help="seconds to wait for each handshake (default 60)",
    )
    parser.add_argument(
        "--include-optional",
        action="store_true",
        help="probe optional servers even when their precondition is missing",
    )
    args = parser.parse_args()

    servers = build_servers()
    known = {s.name: s for s in servers}

    if args.list:
        for server in servers:
            optional = " (optional)" if server.optional else ""
            print(f"{server.name:<20} {server.channel:<16}{optional}  $ {' '.join(server.argv)}")
            if server.hint:
                print(f"{'':<20} hint: {server.hint}")
        return 0

    if args.names:
        unknown = [n for n in args.names if n not in known]
        if unknown:
            print(f"unknown server(s): {', '.join(unknown)}", file=sys.stderr)
            print(f"known: {', '.join(sorted(known))}", file=sys.stderr)
            return 2
        selected = [known[n] for n in args.names]
    else:
        selected = servers

    results: list[ProbeResult] = []
    for server in selected:
        reason = _should_skip(server, include_optional=args.include_optional)
        if reason:
            results.append(
                ProbeResult(
                    name=server.name,
                    channel=server.channel,
                    ok=True,
                    status="SKIPPED",
                    error=reason,
                    hint=server.hint,
                    skipped=True,
                )
            )
            continue
        results.append(probe(server, args.timeout))

    if args.json:
        print(
            json.dumps(
                {
                    "ok": all(r.ok for r in results),
                    "servers": [r.as_dict() for r in results],
                },
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        for result in results:
            mark = "SKIP" if result.skipped else ("PASS" if result.ok else "FAIL")
            line = f"[{mark}] {result.name:<20} {result.channel:<16} {result.status}"
            if result.ok and not result.skipped:
                line += f"  version={result.version or '?'} tools={len(result.tools)}"
            print(line)
            if result.ok and result.tools:
                print(f"         tools: {', '.join(result.tools)}")
            if not result.ok:
                if result.error:
                    print(f"         error: {result.error}")
                if result.hint:
                    print(f"         hint:  {result.hint}")
        failed = [r for r in results if not r.ok]
        skipped = [r for r in results if r.skipped]
        print()
        print(
            f"passed={len([r for r in results if r.ok and not r.skipped])} "
            f"failed={len(failed)} skipped={len(skipped)}"
        )

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
