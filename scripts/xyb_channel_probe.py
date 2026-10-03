#!/usr/bin/env python3
"""XYB clinical-channel health probe (stdlib only).

Answers, per channel, "can a real query be served right now?" and — when it
cannot — *which* precondition is missing. That distinction is the whole point of
FR-5.3: a channel that is not built or not logged in must never be reported to a
patient as "no matching trials".

Channels and their preconditions:

==============  ==========================================================
clinicaltrials  ClinicalTrials.gov API v2; public, no credentials
chinadrugs      needs the patient's own browser session cookie on this machine
chictr          npm server; may hit a site verification (captcha) page
veeva           local stdio server; needs a local index built first
==============  ==========================================================

Status vocabulary (kept identical to the design doc):

``OK``          channel answered
``EMPTY``       channel answered and genuinely matched nothing
``INDEX_EMPTY`` veeva has no local index yet
``NO_SESSION``  chinadrugs has no browser session
``CHALLENGED``  chictr hit a verification page
``UNREACHABLE`` network/endpoint failure
``NOT_INSTALLED`` the channel's runtime is not present on this machine
``LOCAL_SSL_TRUST`` this host's Python cannot verify TLS (proxy CA missing);
                  distinct from a remote failure, and reported as such

Usage::

    python3 scripts/xyb_channel_probe.py             # all four channels
    python3 scripts/xyb_channel_probe.py veeva       # one channel
    python3 scripts/xyb_channel_probe.py --list
    python3 scripts/xyb_channel_probe.py --json

Exit code 0 when every requested channel is OK/EMPTY, 1 otherwise, 2 on usage.
"""

from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from xyb_mcp_probe import build_servers, probe  # noqa: E402

CHANNELS = ("clinicaltrials", "chinadrugs", "chictr", "veeva")

#: MCP server name that carries each channel, when the channel has one.
#: MCP server carrying each channel. chinadrugs has none: it is a
#: session-cookie-backed CLI skill (see the trial-matching expert), so it is
#: checked through its local session config instead of a handshake.
CHANNEL_SERVER = {
    "clinicaltrials": "xyb-clinicaltrials",
    "chictr": "xyb-chictr",
    "veeva": "xyb-veeva",
}

CTA_V2 = "https://clinicaltrials.gov/api/v2/studies"
HTTP_TIMEOUT = float(os.environ.get("XYB_HTTP_TIMEOUT", "30"))


@dataclass
class ChannelResult:
    channel: str
    status: str
    detail: str = ""
    hint: str = ""
    sample: list[str] = field(default_factory=list)

    @property
    def ok(self) -> bool:
        return self.status in {"OK", "EMPTY"}

    def as_dict(self) -> dict:
        return {
            "channel": self.channel,
            "status": self.status,
            "ok": self.ok,
            "detail": self.detail,
            "hint": self.hint,
            "sample": self.sample,
        }


def _servers() -> dict[str, object]:
    return {s.name: s for s in build_servers()}


def _probe_via_mcp(channel: str, timeout: float) -> ChannelResult:
    """Run the shared MCP handshake and translate the outcome for this channel."""
    servers = _servers()
    server = servers.get(CHANNEL_SERVER.get(channel, ""))
    if server is None:
        return ChannelResult(channel, "NOT_INSTALLED", "no MCP server configured")
    result = probe(server, timeout)  # type: ignore[arg-type]

    if result.ok:
        return ChannelResult(
            channel,
            "OK",
            f"{len(result.tools)} tool(s), server {result.version or '?'}",
            sample=result.tools[:6],
        )
    if result.status == "MISSING_SOURCE":
        if channel == "veeva":
            return ChannelResult(
                channel,
                "NOT_INSTALLED",
                result.error,
                hint="build the local ctv-mcp-server, then build its index "
                "(import_csv_export or sync_sitemap) before searching",
            )
        return ChannelResult(channel, "NOT_INSTALLED", result.error, hint=result.hint)
    if result.status == "MISSING_BINARY":
        return ChannelResult(channel, "NOT_INSTALLED", result.error, hint=result.hint)

    # Classify on the *error* only. The hint for chictr mentions "verification"
    # for guidance, so including it made every failure -- timeout, DNS, JSON-RPC
    # error -- look like a captcha challenge.
    blob = result.error.lower()
    if channel == "chictr" and any(
        token in blob for token in ("challenge", "captcha", "verif", "验证")
    ):
        return ChannelResult(
            channel,
            "CHALLENGED",
            "the registry asked for human verification",
            hint="open the site and complete the verification, then retry; this probe "
            "does not bypass it",
        )
    if channel == "veeva" and any(token in blob for token in ("index", "no such column", "empty")):
        return ChannelResult(
            channel,
            "INDEX_EMPTY",
            "the server is up but its local index is not usable",
            hint="run import_csv_export with a CTV CSV export, or sync_sitemap, then retry",
        )
    # A missing Playwright browser is an installation gap, not a captcha: the
    # operator needs an install command, not "go complete a verification".
    if "playwright" in blob or "executable doesn" in blob:
        return ChannelResult(
            channel,
            "NOT_INSTALLED",
            "the scraping runtime is missing its browser",
            hint=(
                "install it into a writable path: "
                "PLAYWRIGHT_BROWSERS_PATH=<dir> npx playwright@1.49.1 install chromium, "
                "then set XYB_PLAYWRIGHT_BROWSERS_PATH to the same directory"
            ),
        )
    if channel == "chinadrugs" and any(
        token in blob for token in ("session", "cookie", "login", "auth")
    ):
        return ChannelResult(
            channel,
            "NO_SESSION",
            "no usable browser session",
            hint="set the session cookie in ~/.xyb-chinadrugtrials/config.json (0600)",
        )
    return ChannelResult(channel, "UNREACHABLE", result.error or result.status, hint=result.hint)


def _ssl_context() -> ssl.SSLContext | None:
    """Build a verification context, honouring an operator-supplied CA bundle.

    On a machine behind a TLS-inspecting proxy the system trust store is not
    reachable from Python, so the honest move is to let the operator point at
    their proxy CA. Verification is never disabled: a silent
    ``CERT_NONE`` fallback would hide exactly the failure this probe exists to
    report.
    """
    for var in ("XYB_HTTP_CA_BUNDLE", "REQUESTS_CA_BUNDLE", "SSL_CERT_FILE"):
        bundle = os.environ.get(var)
        if bundle and Path(bundle).is_file():
            try:
                return ssl.create_default_context(cafile=bundle)
            except (OSError, ssl.SSLError):
                continue
    return None


def _is_local_trust_failure(exc: BaseException) -> bool:
    """True when the failure is our TLS trust, not the remote endpoint."""
    text = f"{exc}"
    return "CERTIFICATE_VERIFY_FAILED" in text or "certificate verify failed" in text


def _probe_clinicaltrials_direct(timeout: float) -> ChannelResult:
    """Hit ClinicalTrials.gov API v2 directly.

    Independent of the npm server, so a broken package cannot mask a working API
    (and vice versa).
    """
    query = urllib.parse.urlencode(
        {"query.cond": "pancreatic cancer", "pageSize": "1", "countTotal": "true"}
    )
    url = f"{CTA_V2}?{query}"
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": "xyb-channel-probe/1.0 (+local health check)",
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout, context=_ssl_context()) as response:
            payload = json.loads(response.read().decode("utf-8", errors="replace"))
    except ssl.SSLError as exc:
        return ChannelResult(
            "clinicaltrials",
            "LOCAL_SSL_TRUST",
            f"TLS verification failed locally: {exc}",
            hint="this machine's Python cannot reach the system trust store (commonly a "
            "TLS-inspecting proxy). Export the proxy CA and point XYB_HTTP_CA_BUNDLE at "
            "it, or rely on the MCP channel which uses Node's trust store",
        )
    except urllib.error.HTTPError as exc:
        return ChannelResult(
            "clinicaltrials",
            "UNREACHABLE",
            f"HTTP {exc.code} from {CTA_V2}",
            hint="check network access to clinicaltrials.gov",
        )
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        if _is_local_trust_failure(exc):
            return ChannelResult(
                "clinicaltrials",
                "LOCAL_SSL_TRUST",
                f"TLS verification failed locally: {exc}",
                hint="export the proxy CA and set XYB_HTTP_CA_BUNDLE, or use the MCP channel",
            )
        return ChannelResult(
            "clinicaltrials",
            "UNREACHABLE",
            f"{type(exc).__name__}: {exc}",
            hint="check network access to clinicaltrials.gov",
        )
    except json.JSONDecodeError as exc:
        return ChannelResult("clinicaltrials", "UNREACHABLE", f"invalid JSON: {exc}")

    total = payload.get("totalCount")
    studies = payload.get("studies")
    sample: list[str] = []
    if isinstance(studies, list):
        for study in studies[:3]:
            if not isinstance(study, dict):
                continue
            ident = study.get("protocolSection", {}).get("identificationModule", {})
            nct = ident.get("nctId")
            if nct:
                sample.append(str(nct))
    if total == 0:
        return ChannelResult(
            "clinicaltrials", "EMPTY", "the API is healthy and matched 0 studies", sample=sample
        )
    return ChannelResult(
        "clinicaltrials", "OK", f"API v2 healthy; totalCount={total}", sample=sample
    )


def _chinadrugs_precondition() -> ChannelResult | None:
    """Return a precondition failure for chinadrugs, or None when it looks ready."""
    config = Path.home() / ".xyb-chinadrugtrials" / "config.json"
    if not config.is_file():
        return ChannelResult(
            "chinadrugs",
            "NO_SESSION",
            f"no session config at {config}",
            hint="chinadrugs requires the patient's own browser session; set it in "
            f"{config} (0600)",
        )
    mode = config.stat().st_mode & 0o777
    if mode & 0o077:
        return ChannelResult(
            "chinadrugs",
            "NO_SESSION",
            f"{config} is readable by other users (mode {mode:o})",
            hint="chmod 600 the session file; credentials must stay private to this account",
        )
    try:
        data = json.loads(config.read_text(encoding="utf-8", errors="replace"))
    except (OSError, json.JSONDecodeError) as exc:
        return ChannelResult("chinadrugs", "NO_SESSION", f"unreadable session config: {exc}")
    if not isinstance(data, dict) or not data:
        return ChannelResult(
            "chinadrugs", "NO_SESSION", "session config is empty", hint="re-authenticate"
        )
    return None


def run_channel(channel: str, timeout: float) -> ChannelResult:
    if channel == "clinicaltrials":
        direct = _probe_clinicaltrials_direct(timeout)
        if direct.status != "LOCAL_SSL_TRUST":
            return direct
        # Python's trust store is unusable on this host, but the MCP server runs
        # under Node and may well reach the API. Report the channel as working
        # and keep the local caveat visible rather than failing the channel.
        via_mcp = _probe_via_mcp(channel, timeout)
        if via_mcp.ok:
            return ChannelResult(
                channel,
                "OK",
                f"reachable through the MCP channel ({via_mcp.detail}); "
                f"direct HTTPS from this Python is blocked by local TLS trust",
                hint="set XYB_HTTP_CA_BUNDLE to the proxy CA to restore the direct check",
                sample=via_mcp.sample,
            )
        return direct
    if channel == "chinadrugs":
        precondition = _chinadrugs_precondition()
        if precondition is not None:
            return precondition
    return _probe_via_mcp(channel, timeout)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("channels", nargs="*", help=f"one of: {', '.join(CHANNELS)}")
    parser.add_argument("--list", action="store_true", help="list channels and exit")
    parser.add_argument("--json", action="store_true", help="emit JSON")
    parser.add_argument(
        "--timeout",
        type=float,
        default=float(os.environ.get("XYB_MCP_TIMEOUT", "120")),
        help="per-channel timeout in seconds (default 120)",
    )
    args = parser.parse_args()

    if args.list:
        for channel in CHANNELS:
            print(f"{channel:<16} via {CHANNEL_SERVER[channel]}")
        return 0

    selected = args.channels or list(CHANNELS)
    unknown = [c for c in selected if c not in CHANNELS]
    if unknown:
        print(f"unknown channel(s): {', '.join(unknown)}", file=sys.stderr)
        print(f"known: {', '.join(CHANNELS)}", file=sys.stderr)
        return 2

    results = [run_channel(channel, args.timeout) for channel in selected]

    if args.json:
        print(
            json.dumps(
                {"ok": all(r.ok for r in results), "channels": [r.as_dict() for r in results]},
                indent=2,
                ensure_ascii=False,
            )
        )
    else:
        for result in results:
            mark = "PASS" if result.ok else "FAIL"
            print(f"[{mark}] {result.channel:<16} {result.status}")
            if result.detail:
                print(f"         {result.detail}")
            if result.sample:
                print(f"         sample: {', '.join(result.sample)}")
            if not result.ok and result.hint:
                print(f"         hint:   {result.hint}")
        print()
        print(f"ok={len([r for r in results if r.ok])}/{len(results)}")

    return 0 if all(r.ok for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
