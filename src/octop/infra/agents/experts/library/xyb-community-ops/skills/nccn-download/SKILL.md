---
name: nccn-download
description: 当需要按主题、语言与癌种下载 NCCN 指南与患者手册时使用。只提供**下载流程与脚本**；需要本人 NCCN 账号会话，且**不分发任何指南 PDF**（指南正文受版权保护）。Use to download NCCN guidelines/patient manuals with the user's own account.
metadata:
  octop:
    emoji: "📘"
    label:
      zh: "NCCN 指南下载"
      en: "NCCN Guideline Download"
    summary:
      zh: "按主题/语言/癌种下载 NCCN 指南；需本人账号；只发流程不发 PDF。"
      en: "Download NCCN guidelines with your own account; process only, no PDFs."
source_repo: opencare-skillhub/nccn-guideline-downloader
source_license: Apache-2.0
adapted: 2026-10-02
readiness: 需配置（需要本人 NCCN 账号会话；未配置时只给获取步骤）
---
> ## 版权与凭据（优先级高于本文其余内容）
>
> - 本技能**只提供下载流程与脚本**。NCCN 指南与患者手册正文受版权保护，**不得随本项目分发、不得上传到任何公开知识库**。
> - 需要你**本人**的 NCCN 账号会话才能下载；凭据只落在你本机，不进仓库、不回显、不进日志。
> - 未配置账号时，只给出获取步骤，不假装能下载。


# NCCN Guideline Downloader

Download NCCN (National Comprehensive Cancer Network) clinical guidelines and patient manuals through a guided conversational workflow.

## Configuration Check (Run First)

Before downloading, the script automatically checks configuration at startup. Two files must exist in the **`scripts/`** directory (same folder as the script):

| File | Path | Purpose |
|------|------|---------|
| Config | `scripts/config.json` | Authentication method and settings |
| Cookie | `scripts/extracted_cookies.txt` | Cookie string for authentication |

**If config is missing**, the script prints a detailed guide and exits. Do NOT proceed with download until config is complete.

### Setup Steps

1. **Install dependencies:**
   ```bash
   pip install -r scripts/requirements.txt
   ```

2. **Create config file** (copy from template):
   ```bash
   cp assets/config.json.template scripts/config.json
   ```
   Default `scripts/config.json` uses cookie auth — no edits needed for cookie method.

3. **Get NCCN Cookie and save to `scripts/extracted_cookies.txt`:**
   - Login at https://www.nccn.org/
   - Press F12 → Network tab → refresh page → click any request
   - Copy the `Cookie:` header value from Request Headers
   - Paste the entire string into `scripts/extracted_cookies.txt` (one line only)

4. **Verify config** by running the script — it will confirm:
   ```
   ✅ 成功读取配置文件: .../scripts/config.json
   ✅ 认证方式: Cookie 文件  (.../scripts/extracted_cookies.txt)
   ```

### Config File Reference

**Cookie auth (recommended)** — `scripts/config.json`:
```json
{
  "authentication": {
    "method": "cookie",
    "cookie_file": "extracted_cookies.txt"
  }
}
```

**Username/password auth** — `scripts/config.json`:
```json
{
  "authentication": {
    "method": "username_password",
    "username": "your@email.com",
    "password": "your_password"
  }
}
```

**Environment variables** (override config file):
```bash
export NCCN_COOKIE="name1=val1; name2=val2; ..."   # highest priority
export NCCN_AUTH_METHOD="username_password"
export NCCN_USERNAME="your@email.com"
export NCCN_PASSWORD="your_password"
```

## Workflow

### 1. Identify Theme

Map user intent to one of 6 themes:

| # | Theme | URL Pattern |
|---|-------|-------------|
| 1 | Cancer Treatment (English) | `guidelines/category_1` |
| 2 | Supportive Care | `guidelines/category_3` |
| 3 | Patient Guidelines (English) | `patientresources/patient-resources/guidelines-for-patients` (English) |
| 4 | Clinical Guidelines (Chinese Translation) | `patientresources/patient-resources/guidelines-for-patients` (Chinese) |
| 5 | Patient Guidelines (Chinese Translation) | Translation page |
| 6 | Patient Guidelines (Chinese Version) | Translation page (direct) |

### 2. Language Filter

```
0. Chinese    1. English (default)    2. Japanese/Other    3. All
```

Default to English (1) unless user specifies Chinese.

### 3. Cancer Type Filter

65 cancer types with Chinese/English alias matching. See [references/cancer_types.md](references/cancer_types.md) for the full list.

Common shortcuts: `breast`/`乳腺`, `lung`/`肺`, `pancreatic`/`胰腺`, `colon`/`结肠`, `gastric`/`胃`, `prostate`/`前列腺`, `ovarian`/`卵巢`, `thyroid`/`甲状腺`.

Chinese keywords auto-expand to all English aliases (e.g., `胰腺` → `pancreatic adenocarcinoma`, `pancreatic`, `pancreas`).

Options: `0` = all, `L` = browse list from NCCN, `K` = manual keyword.

### 4. PDF List Selection

After parsing, show numbered list. User selects by number: `1,3,5-8` or `A`/Enter for all.

### 5. Confirm & Download

Show summary, confirm, then run:

```bash
python3 scripts/download_nccn.py
```

## Execution

**Interactive (recommended):**

```bash
cd ~/.agents/skills/nccn-guideline-downloader
python3 scripts/download_nccn.py
```

**Guided:** Orchestrate the conversation, collect choices, then run the script with the collected parameters.

## Key Behaviors

- Config files are always resolved relative to **`scripts/`** directory (where the script lives)
- Downloads go to `scripts/nccn_downloads/` subdirectory (auto-created)
- Existing valid PDFs are skipped (checks `%PDF` header + 100KB minimum)
- Failed downloads retry up to 3 times with exponential backoff
- Domain whitelist enforced: only `nccn.org` and subdomains
- Download stats saved to `scripts/nccn_downloads/logs/stats_*.json`
- 42 offline tests available: `python3 scripts/test_offline.py`

## Troubleshooting

- **Config missing:** Run `cp assets/config.json.template scripts/config.json`
- **Cookie file missing:** Save browser Cookie string to `scripts/extracted_cookies.txt`
- **Auth failure:** Cookie expired — refresh browser Cookie and overwrite `scripts/extracted_cookies.txt`
- **No PDFs found:** NCCN site structure may have changed; try `L` to refresh cancer list
- **Corrupted files:** Script validates `%PDF` header; check logs for file sizes
