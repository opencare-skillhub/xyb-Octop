#!/usr/bin/env bash
# Shared interpreter resolution for the XYB check scripts.
#
# Why this exists: the audit scripts need Python 3.11+ (`tomllib`), but on macOS
# the `python3` on PATH is frequently 3.9/3.10 while the project ships a 3.12
# virtualenv. Picking the wrong one fails with a confusing `No module named
# tomllib`, so every wrapper sources this file instead of trusting `python3`.
#
# Resolution order:
#   1. $XYB_PYTHON                        explicit operator override
#   2. $REPO_ROOT/.venv/bin/python        the project's own interpreter
#   3. python3.13/3.12/3.11 on PATH       first that reports >= 3.11
#   4. python3 on PATH                    last resort, version unchecked
#
# Sets XYB_PYTHON_BIN to an absolute path. Callers must have already set
# REPO_ROOT and should exit 2 when this file cannot find anything.

xyb_resolve_python() {
  if [[ -n "${XYB_PYTHON:-}" && -x "${XYB_PYTHON}" ]]; then
    XYB_PYTHON_BIN="${XYB_PYTHON}"
    return 0
  fi

  local candidate
  for candidate in \
    "${REPO_ROOT}/.venv/bin/python" \
    "$(command -v python3.13 2>/dev/null || true)" \
    "$(command -v python3.12 2>/dev/null || true)" \
    "$(command -v python3.11 2>/dev/null || true)"
  do
    [[ -n "${candidate}" && -x "${candidate}" ]] || continue
    if "${candidate}" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 11) else 1)' 2>/dev/null; then
      XYB_PYTHON_BIN="${candidate}"
      return 0
    fi
  done

  candidate="$(command -v python3 2>/dev/null || true)"
  if [[ -n "${candidate}" && -x "${candidate}" ]]; then
    XYB_PYTHON_BIN="${candidate}"
    return 0
  fi

  return 1
}
