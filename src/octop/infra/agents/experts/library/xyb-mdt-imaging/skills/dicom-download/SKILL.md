---
name: dicom-download
description: 当患者要把自己在医院影像平台上的 CT / MRI 原始影像（DICOM）取回本地时使用。脚本用 **Playwright 在本机**驱动医院门户，账号与影像都只留在本机；**只做取回**，不做影像判读，也不绕开医院授权。Use to fetch a patient's own DICOM studies from hospital portals, locally.
metadata:
  octop:
    emoji: "🩻"
    label:
      zh: "影像资料取回（DICOM）"
      en: "DICOM Study Download"
    summary:
      zh: "用本人账号把医院影像平台的原始 DICOM 取回本机；只取回不判读。"
      en: "Fetch your own DICOM studies from hospital portals; retrieval only."
source_repo: opencare-skillhub/xyb_dicom_download_skills
source_license: Apache-2.0
adapted: 2026-10-02
readiness: 需配置（需要患者本人的医院门户账号与检查链接；依赖 Playwright，浏览器缓存见 .cache/xyb-playwright）
---
> ## 本项目的使用范围（优先级高于本文其余内容）
>
> - **只做取回，不做判读。** 本技能把 DICOM 取回本机；影像怎么看、说明什么，由影像科视角按 `imaging-report-reading` 另行处理，且不替代放射科医生。
> - **需要患者本人账号**：用你自己的医院门户账号登录。账号、检查链接与影像**只留在本机**，不上传、不转发、不进日志。
> - **不绕开任何授权或访问控制**，不尝试下载不属于本人或未授权共享的影像。
> - **不收费**：患者取回自己的影像资料不应产生费用；如遇平台要求付费，如实说明并建议走医院正式流程。
> - 依赖 Playwright。浏览器缓存在 `<repo>/.cache/xyb-playwright`；未安装时如实告知，不要假装已开始下载。
> - 与本视角的「不使用浏览器工具」约定不冲突：这里是**本机脚本**在跑，不是让 agent 去浏览网页。


# xyb-dicom-download-skill

Use this skill when working on the `dicom_download` project or when drafting guidance for the Xyb DICOM download workflow.

## What this skill should do

- Help maintain the downloader repo and its docs.
- Write or update beginner-friendly quick-start instructions.
- Keep uv, Python virtual environment, and Playwright setup clear for Windows, macOS, and Linux.
- Preserve the project's safety and ethics language, especially around patient data and charging.
- Keep examples aligned with the current repo commands and behavior.

## Core workflow

1. Inspect the target files first.
   - Read `README.md`, `pyproject.toml`, and any relevant script before editing.
   - Prefer the existing repo patterns over introducing a new style.

2. Keep the quick start explicit.
   - Show the order: install Python, install `uv`, run `uv sync`, install Playwright browsers, then run the downloader.
   - Prefer `uv run python ...` in examples so the same instructions work across Windows, macOS, and Linux.

3. Treat browser installation as a separate step.
   - Python dependencies belong in `pyproject.toml`.
   - Playwright browser binaries should be installed with an explicit command in the docs.
   - If the user asks for automation, prefer a separate helper command or script, not a hidden install hook.

4. Keep the README beginner-friendly.
   - Start with a quick start section near the top.
   - Add a troubleshooting section for missing Python packages and missing Playwright browsers.
   - Keep command examples short and copy-pasteable.

5. Preserve the project’s ethics notes.
   - Always include acknowledgement of the upstream project.
   - Always include thanks to the 小胰宝 volunteer open-source contributors.
   - Always state that the tool must not be used to charge patients or to disguise charging as service, support, training, or any other indirect form.

## Style guidance

- Prefer short sections with clear headings.
- Use concrete commands, not vague descriptions.
- Keep wording consistent with the surrounding repository language.
- When updating docs, keep the recommended path easy for beginners.

## Good default content for a quick start

- `uv sync`
- `uv run python -m playwright install chromium`
- `uv run python multi_download.py --urls-file urls.txt --out-parent ./downloads`

## If you need more detail

Read the files in `references/` for the current quick-start wording, acknowledgement text, and command conventions.
