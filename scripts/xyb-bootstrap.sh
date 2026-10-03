#!/usr/bin/env bash
# XYB one-shot bootstrap (idempotent).
#
# Prepares a machine for the xiaoyibao clinical channels:
#
#   1. report what the local environment provides (node/npx/python/gh)
#   2. seed the default MCP servers for the acting user (add-only)
#   3. handshake every seeded server
#   4. smoke the four clinical channels
#
# Nothing here installs packages or writes anything outside Octop's own
# connector store. Missing prerequisites are reported, not fixed, so the
# operator stays in control of what lands on their machine.
#
# Usage:
#   scripts/xyb-bootstrap.sh                 # full sequence (seeds for --user)
#   scripts/xyb-bootstrap.sh --user alice
#   scripts/xyb-bootstrap.sh --dry-run       # plan only, write nothing
#   scripts/xyb-bootstrap.sh --skip-seed     # only check the environment
#
# Environment overrides:
#   XYB_VEEVA_DIR       local ctv-mcp-server checkout (veeva channel)
#   XYB_CHINADRUGS_DIR  local chinadrugtrials checkout (chinadrugs channel)
#   XYB_PYTHON          Python 3.11+ interpreter for the check scripts
#   METASO_API_KEY      enables the optional Metaso search server
set -uo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

AS_USER=""
DRY_RUN=0
SKIP_SEED=0
SKIP_CHECKS=0

while [[ $# -gt 0 ]]; do
  case "$1" in
    --user) AS_USER="${2:-}"; shift 2 ;;
    --dry-run) DRY_RUN=1; shift ;;
    --skip-seed) SKIP_SEED=1; shift ;;
    --skip-checks) SKIP_CHECKS=1; shift ;;
    -h|--help)
      sed -n '2,28p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'
      exit 0
      ;;
    *)
      echo "xyb-bootstrap: unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

say() { printf '\n\033[1m%s\033[0m\n' "$*"; }
note() { printf '  %s\n' "$*"; }

failures=0
record_failure() { failures=$((failures + 1)); }

# Keep the MCP/channel probes pointed at the same browser cache this script
# checked above. Harmless when the directory does not exist yet: the probe
# leaves the child environment alone in that case.
export XYB_PLAYWRIGHT_BROWSERS_PATH="${XYB_PLAYWRIGHT_BROWSERS_PATH:-${REPO_ROOT}/.cache/xyb-playwright}"

# ---------------------------------------------------------------- environment
say "1/4 环境检查"

check_binary() {
  local name="$1" hint="$2" required="$3"
  if command -v "${name}" >/dev/null 2>&1; then
    note "OK   ${name} — $(command -v "${name}")"
  elif [[ "${required}" == "required" ]]; then
    note "MISS ${name}（必需）— ${hint}"
    record_failure
  else
    note "MISS ${name}（可选）— ${hint}"
  fi
}

check_binary node "安装 Node.js 20+；clinicaltrials/chictr/pubmed/dayi 通道依赖它" required
check_binary npx "随 Node.js 一起安装" required
check_binary python3 "用于 chinadrugs 通道与校验脚本" required
check_binary gh "仅用于拉取技能与核对许可，运行时不依赖" optional

# The check scripts need 3.11+; make the resolution visible instead of failing
# later with a confusing tomllib import error.
# shellcheck source=scripts/xyb_python.sh
source "${REPO_ROOT}/scripts/xyb_python.sh"
if xyb_resolve_python; then
  note "OK   python(checks) — ${XYB_PYTHON_BIN}"
else
  note "MISS python 3.11+ — 校验脚本需要 tomllib；用 XYB_PYTHON 指定"
  record_failure
fi

# chictr scrapes with Playwright. Its postinstall runs `playwright install`, which
# aborts on macOS when the default cache is locked by TCC -- the package then
# finishes half-installed and the server starts but answers nothing. Installing
# into a cache we own is the fix, so check for it here.
browsers_dir="${XYB_PLAYWRIGHT_BROWSERS_PATH:-${REPO_ROOT}/.cache/xyb-playwright}"
if [[ -d "${browsers_dir}" ]] && ls "${browsers_dir}"/chromium* >/dev/null 2>&1; then
  note "OK   playwright browsers — ${browsers_dir}"
else
  note "MISS playwright browsers — chictr 通道需要它："
  note "       PLAYWRIGHT_BROWSERS_PATH=${browsers_dir} npx playwright@1.49.1 install chromium"
fi

veeva_dir="${XYB_VEEVA_DIR:-${HOME}/Downloads/ctv-mcp-server}"
if [[ -f "${veeva_dir}/dist/index.js" ]]; then
  note "OK   veeva — ${veeva_dir}/dist/index.js"
else
  note "MISS veeva — 需要 ${veeva_dir}（cd 进去 npm install && npm run build），或用 XYB_VEEVA_DIR 指定"
fi

chinadrugs_dir="${XYB_CHINADRUGS_DIR:-${HOME}/Downloads/chinadrugtrials}"
if [[ -f "${chinadrugs_dir}/server.py" ]]; then
  note "OK   chinadrugs — ${chinadrugs_dir}/server.py"
else
  note "MISS chinadrugs — 需要 ${chinadrugs_dir}，或用 XYB_CHINADRUGS_DIR 指定"
fi

if [[ -n "${METASO_API_KEY:-}" ]]; then
  note "OK   METASO_API_KEY — 已设置（秘塔检索可写入）"
else
  note "SKIP METASO_API_KEY — 未设置；秘塔检索不会写入配置"
fi

# --------------------------------------------------------------------- seeding
if [[ "${SKIP_SEED}" -eq 0 ]]; then
  say "2/4 播种 MCP 服务"
  seed_args=(xyb init-mcp)
  [[ -n "${AS_USER}" ]] && seed_args+=(--user "${AS_USER}")
  [[ "${DRY_RUN}" -eq 1 ]] && seed_args+=(--dry-run)
  if ! (cd "${REPO_ROOT}" && PYTHONPATH=src uv run python -m octop.cli.main "${seed_args[@]}"); then
    note "播种失败 — 若尚未初始化，先运行 octop init"
    record_failure
  fi
else
  say "2/4 播种 MCP 服务（已跳过）"
fi

if [[ "${SKIP_CHECKS}" -eq 1 ]]; then
  say "3/4 / 4/4 校验（已跳过）"
else
  # ------------------------------------------------------------------ handshake
  say "3/4 MCP 握手"
  if ! "${REPO_ROOT}/scripts/xyb-check-mcp.sh"; then
    note "有 MCP 未通过握手；上面每一行都给出了具体原因与安装提示"
    record_failure
  fi

  # ------------------------------------------------------------------- channels
  say "4/4 四大通道冒烟"
  if ! "${REPO_ROOT}/scripts/xyb-check-channels.sh"; then
    note "有通道未就绪；INDEX_EMPTY / NO_SESSION / CHALLENGED 都是可执行的提示，不是「没有试验」"
    record_failure
  fi
fi

# ----------------------------------------------------------------------- summary
printf '\n'
if [[ "${failures}" -eq 0 ]]; then
  printf '\033[32m小胰宝引导完成：未发现问题\033[0m\n'
  exit 0
fi
printf '\033[33m小胰宝引导完成：%d 项需要处理（见上方 MISS / 未通过项）\033[0m\n' "${failures}"
# A missing optional channel is not a hard failure of the bootstrap itself, but
# it is reported through the exit code so automation can notice.
exit 1
