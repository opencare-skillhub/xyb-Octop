#!/usr/bin/env bash
# XYB clinical-channel smoke test (FR-5.1 / FR-5.3 / FR-5.4).
#
# The four patient-facing channels are:
#
#   clinicaltrials  ClinicalTrials.gov API v2      (npm, no credentials)
#   chinadrugs      China drug trial registry      (local session cookie)
#   chictr          China clinical trial registry  (npm, may hit a captcha)
#   veeva           Veeva CTV                      (local stdio, index required)
#
# This script reports, per channel, whether a real query can be served or which
# precondition is missing. It exists to make the four failure states explicit:
#
#   INDEX_EMPTY  veeva has no local index yet        -> "not built", NOT "0 hits"
#   NO_SESSION   chinadrugs has no browser session   -> "needs login", NOT "0"
#   CHALLENGED   chictr hit a site verification page -> ask the user to verify
#   EMPTY        a healthy query that matched nothing -> genuinely 0 results
#
# Usage:
#   scripts/xyb-check-channels.sh            # probe all four channels
#   scripts/xyb-check-channels.sh veeva      # probe one channel
#   scripts/xyb-check-channels.sh --json
#
# Exit code 0 when every requested channel is reachable, 1 otherwise, 2 on usage.
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
RUNNER="${REPO_ROOT}/scripts/xyb_channel_probe.py"

if [[ ! -f "${RUNNER}" ]]; then
  echo "xyb-check-channels: missing ${RUNNER}" >&2
  exit 2
fi

PYTHON_BIN="${PYTHON_BIN:-}"
if [[ -z "${PYTHON_BIN}" ]]; then
  # shellcheck source=scripts/xyb_python.sh
  source "${REPO_ROOT}/scripts/xyb_python.sh"
  if ! xyb_resolve_python; then
    echo "xyb-check-channels: no usable python3 (needs 3.11+)" >&2
    echo "  set XYB_PYTHON=/path/to/python3.12 to override" >&2
    exit 2
  fi
  PYTHON_BIN="${XYB_PYTHON_BIN}"
fi

exec "${PYTHON_BIN}" "${RUNNER}" "$@"
