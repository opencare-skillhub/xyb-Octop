#!/usr/bin/env bash
# XYB MCP handshake check (FR-3.1 / FR-3.2).
#
# Verifies, for every configured MCP server, that the process starts and answers
# a real JSON-RPC `initialize` + `tools/list`. Reports the tool count and the
# `serverInfo.version` the server actually returns, so version drift is visible
# instead of assumed.
#
# Nothing here needs an LLM or the Octop server: it speaks MCP over stdio the
# same way the connector gateway does.
#
# Usage:
#   scripts/xyb-check-mcp.sh                 # check every known server
#   scripts/xyb-check-mcp.sh xyb-veeva       # check one server by name
#   scripts/xyb-check-mcp.sh --list          # list known servers and the plan
#   scripts/xyb-check-mcp.sh --json          # machine-readable report
#
# Exit code 0 when all requested servers hand shake, 1 otherwise, 2 on bad usage.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="${REPO_ROOT}/scripts/xyb_mcp_probe.py"

if [[ ! -f "${RUNNER}" ]]; then
  echo "xyb-check-mcp: missing ${RUNNER}" >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  # shellcheck source=scripts/xyb_python.sh
  source "${REPO_ROOT}/scripts/xyb_python.sh"
  if ! xyb_resolve_python; then
    echo "xyb-check-mcp: no usable python3 (needs 3.11+)" >&2
    echo "  set XYB_PYTHON=/path/to/python3.12 to override" >&2
    exit 2
  fi
  PYTHON_BIN="${XYB_PYTHON_BIN}"
fi

exec "${PYTHON_BIN}" "${RUNNER}" "$@"
