#!/usr/bin/env bash
# XYB branding residue check (FR-1.6).
#
# Wraps scripts/xyb_name_audit.py so the branding gate has one entry point and a
# shell-friendly exit code. The audit understands two classes of "octop" text:
#
#   IDENTITY  user-visible / release-visible names -> must become xiaoyibao
#   CONTRACT  import paths, ~/.octop, OCTOP_*, upstream distribution names
#             -> must NOT change
#
# A blind global replace would corrupt the CONTRACT surfaces, so this script
# never rewrites anything; it only reports.
#
# Usage:
#   scripts/xyb-check-branding.sh              # gate (exit 1 on residue)
#   scripts/xyb-check-branding.sh --json       # machine-readable report
#   scripts/xyb-check-branding.sh --phase pre  # assert the pre-rebrand state
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
AUDIT="${REPO_ROOT}/scripts/xyb_name_audit.py"

if [[ ! -f "${AUDIT}" ]]; then
  echo "xyb-check-branding: missing ${AUDIT}" >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  # shellcheck source=scripts/xyb_python.sh
  source "${REPO_ROOT}/scripts/xyb_python.sh"
  if ! xyb_resolve_python; then
    echo "xyb-check-branding: no usable python3 (needs 3.11+ for tomllib)" >&2
    echo "  set XYB_PYTHON=/path/to/python3.12 to override" >&2
    exit 2
  fi
  PYTHON_BIN="${XYB_PYTHON_BIN}"
fi

exec "${PYTHON_BIN}" "${AUDIT}" "$@"
