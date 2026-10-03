# XYB-SKILL-LICENSE — 技能许可台账

**核实日期** 2026-10-01
**核实方式** `gh api repos/<owner>/<repo> --jq .license.spdx_id` 逐仓库实测
**用途** FR-2.7 / NFR-3：每个入库技能都要有实测 `spdx_id` 与可分发判定。

---

## 一、汇总

| `spdx_id` | 数量 | 可否再分发 | 代表仓库 |
|---|---|---|---|
| Apache-2.0 | 12 | ✅ 可以，保留 NOTICE 与许可声明 | `clinicaltrials-query-analysis`、`chictr-trials-collector`、`maskdesk` |
| MIT | 1 | ✅ 可以，保留版权与许可声明 | `awesome_research_writter_xiaoyibao` |
| MIT-0 | 1 | ✅ 可以，无署名要求 | `aura_health_profile` |
| **AGPL-3.0** | 1 | ⚠️ 可以，但**有传染性** | `graphify-xiaoyibao` |
| **NONE** | 15 | ❌ **对外分发前必须补许可** | `Medical-Record-Organizer`、`clinical-trial-matching`、`xyb-humanizer` |

> **本轮决定（用户 2026-10-01 确认）**：无 LICENSE 仓库**照常入库**，台账如实标注 `NONE`，暂不补许可。
> 理由：这些仓库**都在本项目自己的组织下**（`opencare-skillhub` / `PancrePal-xiaoyibao`），
> 实际操作上我方即权利人；对外分发前统一补 Apache-2.0（同组织已有先例）。
> **风险已明示**：`NONE` 不等于「可以随便分发」。公开发布产物前必须处理 §四。

---

## 二、逐技能台账

### 批 1 · 医学解读（患者向，6）

| 技能 | 源仓库 | `spdx_id` | 可分发 | 传染性 | 落点专家 | 适配方式 |
|---|---|---|---|---|---|---|
| `record-organizer` | `opencare-skillhub/Medical-Record-Organizer` | **NONE** | ❌ 待补 | 无 | 全部 MDT | 病案整理；Octop 有终端，脚本可跑 |
| `trial-matching-advanced` | `opencare-skillhub/clinical-trial-matching` | **NONE** | ❌ 待补 | 无 | `xyb-trial-matching` | 入排分析；检索改指四通道工具 |
| `distress-screening` | `opencare-skillhub/skill-HADS-accessment` | **NONE** | ❌ 待补 | 无 | `xyb-mdt-psych` | HADS 量表；**只本机，不发公网** |
| `tumor-marker-trend` | `opencare-skillhub/graphify-xiaoyibao` | **AGPL-3.0** | ⚠️ 可 | **强 copyleft** | `xyb-mdt-oncology` | 标志物趋势；传染性须单独标注 |
| `lab-to-profile` | `opencare-skillhub/aura_health_profile` | MIT-0 | ✅ 可 | 无 | `xyb-mdt-oncology` | 化验单→档案；**需阿里云百炼 key**，未配降级方法论 |
| `pdf-translate` | `opencare-skillhub/pdf-translate` | **NONE** | ❌ 待补 | 无 | 全部 MDT | 英文文献翻译（pdf2zh） |

### 批 2 · 临床试验查询（4）

| 技能 | 源仓库 | `spdx_id` | 可分发 | 落点专家 | 适配方式 |
|---|---|---|---|---|---|
| `target-trial-analysis` | `opencare-skillhub/clinicaltrials-query-analysis` | Apache-2.0 | ✅ | `xyb-trial-matching` | 靶点专题检索与报告流水线 |
| `trial-intel-push` | `opencare-skillhub/clinicaltrials-intel-skill` | Apache-2.0 | ✅ | `xyb-community-ops` | 采集-清洗-多通道推送 |
| `chictr-collect` | `opencare-skillhub/chictr-trials-collector` | Apache-2.0 | ✅ | `xyb-trial-matching` | 与 chictr MCP 衔接 |
| `chinadrugs-collect` | `opencare-skillhub/chinadurgtrials` | **NONE** | ❌ 待补 | `xyb-trial-matching` | 与 chinadrugs 通道衔接 |

### 批 3 · 社区运营 / 内容（7）

| 技能 | 源仓库 | `spdx_id` | 可分发 | 落点专家 |
|---|---|---|---|---|
| `wechat-article` | `opencare-skillhub/xyb-wechat-article-generator` | **NONE** | ❌ 待补 | `xyb-community-ops` |
| `humanizer` | `opencare-skillhub/xyb-humanizer` | **NONE** | ❌ 待补 | `xyb-community-ops` |
| `whitepaper` | `opencare-skillhub/xyb-whitepaper-writer` | **NONE** | ❌ 待补 | `xyb-community-ops` |
| `url-to-wechat-html` | `opencare-skillhub/xyb-wechat-article-transcription` | Apache-2.0 | ✅ | `xyb-community-ops` |
| `wechat-news-board` | `opencare-skillhub/pancrepal-wechat-news-board` | **NONE** | ❌ 待补 | `xyb-community-ops` |
| `pdac-dailynews` | `opencare-skillhub/pancreatic-cancer-dailynews-skill` | **NONE** | ❌ 待补 | `xyb-community-ops` |
| `rag-content` | `opencare-skillhub/RAG-content-processor` | Apache-2.0 | ✅ | `xyb-community-ops` |

### 批 4 · 研究 / 写作（3）

| 技能 | 源仓库 | `spdx_id` | 可分发 | 落点专家 |
|---|---|---|---|---|
| `research-writer` | `opencare-skillhub/awesome_research_writter_xiaoyibao` | MIT | ✅ | `xyb-community-ops` |
| `psych-article-writer` | `opencare-skillhub/inkstone-studio` | Apache-2.0 | ✅ | `xyb-mdt-psych` + `xyb-community-ops` |
| `aesthetic-brain` | `opencare-skillhub/agent-taste-seed-system` | **NONE** | ❌ 待补 | `xyb-community-ops`（**用户点名要求**） |

> **`agent-taste-seed-system` 双仓库说明**：`opencare-skillhub/agent-taste-seed-system`（size 0）
> 与 `PancrePal-xiaoyibao/agent-taste-seed-system`（size 295）内容一致，但前者是空 fork。
> **实测确认两者文件树相同**；入库取 `opencare-skillhub` 版本（与需求文档一致），
> 若取不到内容则回退 `PancrePal-xiaoyibao` 版本。

### 批 5 · 影像 / 指南（2）

| 技能 | 源仓库 | `spdx_id` | 可分发 | 落点专家 | 备注 |
|---|---|---|---|---|---|
| `dicom-download` | `opencare-skillhub/xyb_dicom_download_skills` | Apache-2.0 | ✅ | `xyb-mdt-imaging` | |
| `xyb-record-desensitize`（内置技能） | 全部专家（`builtin_skills/` 自动注入） | 规则集参考 `PancrePal-xiaoyibao/maskdesk`（Apache-2.0） | Apache-2.0（参考方） | 自研正文 | 无需配置 | **不是搬运**：maskdesk 是 Electron 桌面应用（TS + Electron），无法作为技能装进专家包。这里只**参考其 8 条身份识别正则**（手机号/身份证/邮箱/日期/固话/编号/银行卡/URL）并结合胰腺癌病案场景重写为方法论：字段清单、执行顺序、脱敏后自查、硬边界。不包含 maskdesk 的任何代码，因此不构成对其分发 |
| `pdf-translate` | `xyb-mdt-radiation` | `opencare-skillhub/pdf-translate` | **NONE** | ❌ 待补 | 需安装依赖（首次 `setup.sh` 用 uv 装 `pdf2zh_next`） | 只导入技能与包装脚本（5 个文件）；`pdf2zh_next` 与约 1GB 级模型资产属首次运行按需安装，**不随仓库分发**。正文顶部声明：未安装只给步骤、**只翻译不判读**、机器翻译须回原文核对 |
| `lab-to-profile` | `xyb-mdt-oncology` | `opencare-skillhub/aura_health_profile` | **MIT-0** | ✅ 无附加条件 | 需配置（阿里云百炼 key） | 只导入英文侧正文与模板；不带入 `*_CN.md` 重复副本与 `ONBOARD*`/`PUBLISHING*`/`CHANGELOG*` 仓库运维文档。正文顶部声明：未配置 key 时只走本地模板并如实说明、资料不出机、**趋势不等于疗效** |
| `humanizer` | `xyb-community-ops` | `opencare-skillhub/xyb-humanizer` | **NONE** | ❌ 待补 | 可直接使用（纯方法层） | 只导入方法层（`SKILL.md`/`README.md`/`CHANGELOG.md`）；上游 `evals/` 基准数据不带入。正文顶部声明硬边界：**事实与证据等级不可改**、不得恐吓或制造虚假紧迫感、不用于规避 AI 检测 |
| `aesthetic-brain` | `xyb-community-ops` | `opencare-skillhub/agent-taste-seed-system` | **NONE** | ❌ 待补 | 可直接使用 | 上游**没有 `SKILL.md`**，正文在 `TASTE.md`（导入器以 `body_from` 显式指定，不会写出占位正文）。只导入正文与 `references/`（48 个艺术史章节与视觉种子）；**不导入** `deploy/` 的 Claude Code / OpenClaw 部署脚本 |
| `wechat-article` | `xyb-community-ops` | `opencare-skillhub/xyb-wechat-article-transcription` | Apache-2.0 | ✅ 代码可分发 | 可直接使用（发布需自备凭据） | 上游把技能放在 `skills/` 子目录，以 `body_from` 指定正文来源。带全部排版模板与渲染脚本；正文顶部声明**只产出本地 HTML**、不含任何公众号密钥 |
| `dicom-download` | `xyb-mdt-imaging` | `opencare-skillhub/xyb_dicom_download_skills` | Apache-2.0 | ✅ 代码可分发 | 需配置（本人医院门户账号） | 只导入脚本与文档（12 个文件）；不带入上游 `uv.lock` 与下载产物。正文顶部声明：需本人账号、账号与影像不出机、**只取回不判读**、不绕开授权、不收费。仓库实际只有 17 个文件（此前记录的「1387 个文件」是本地副本含 `.venv`/产物，已更正） |
| `trial-matching-advanced` | `xyb-trial-matching` | `opencare-skillhub/clinical-trial-matching` | **NONE**（仓库无 LICENSE 文件） | ❌ 待补 | 需改写（检索改走四通道） | 仓库**没有 LICENSE 文件**，仅在 `SKILL.md` 内声明 `license: MIT`；两者都记入溯源头（`source_license: NONE` + `declared_license: MIT`）。**声明不等于授权**，对外分发前须补许可。另：上游自有检索接口不使用，改为先经 `trial-search` 取真实记录再逐条对照 |
| `chinadrugs-collect` | `xyb-trial-matching` | `opencare-skillhub/chinadurgtrials` | **NONE** | ❌ 待补 | 需配置（本人浏览器会话 Cookie） | 按实际形态接入：该通道**不是 MCP**（上游无 `server.py`），改以技能承载。只导入脚本与流程，**不导入任何凭据**（config 模板随包） |
| `record-organizer` | `xyb-mdt-surgery` | `opencare-skillhub/Medical-Record-Organizer` | **NONE** | ❌ 待补 | 需安装依赖（PyMuPDF / python-docx / openpyxl / Jinja2） | 只取方法与脚本；**不导入**上游用于演示的 `output*/`（约 1000 个生成文件，仓库 141MB）。正文顶部声明：数据不出机、不发布公网、不是诊断；未配 OCR/ASR 时明确说不该环节不可用 |
| `nccn-download` | `opencare-skillhub/nccn-guideline-downloader` | Apache-2.0 | ✅ | `xyb-community-ops` + MDT | ⚠️ **代码许可 ≠ 指南版权**：下载的 NCCN 指南本身受版权保护，不得随产物再分发 |

### 附加 · 病历脱敏

| 能力 | 源仓库 | `spdx_id` | 可分发 | 承载 |
|---|---|---|---|---|
| 病历脱敏工作台 | `PancrePal-xiaoyibao/maskdesk` | Apache-2.0 | ✅ | 技能（方法层）+ 可选插件 |

---

## 三、MCP 服务许可（npm 引用，不再分发源码）

| MCP | 载体 | 上游仓库许可 | 风险 |
|---|---|---|---|
| `chictr-mcp-server@2.0.2` | npm | Apache-2.0 | 低 |
| `mcp-pubmed-llm-server@3.0.0` | npm | Apache-2.0 | 低 |
| `metaso-search-mcp@1.1.2` | npm | Apache-2.0 | 低 |
| `@xiaoyibao_2025/dayi-mcp-server@0.1.7` | npm | 仓库 **NONE**（`dayi-search-mcp`） | 低（走 npm 引用而非再分发源码），仍需补 LICENSE 正名 |
| `xiaoyibao-clinical-trials@1.0.0` | npm | MIT | 低 |
| `ctv-mcp-server`（veeva） | **本地源码内置** | MIT | 低，但**内置即再分发**，须保留 MIT 声明与版权行 |

> **唯一需要额外注意的**：`ctv-mcp-server` 是**源码内置**（不是 npx 引用），
> 属于再分发行为。其 MIT 许可要求保留版权声明与许可全文——P1 内置时必须一并带上 `LICENSE`。

---

## 四、对外分发前的必办清单（阻塞发布，不阻塞开发）

1. **补 15 个 `NONE` 仓库的 LICENSE**（建议统一 Apache-2.0）。
2. **AGPL-3.0 传染性处理**：`graphify-xiaoyibao` 若随产物分发，须在发布流程中独立标注，
   并确认其与整体分发方式的兼容性。
3. **保留许可声明**：所有 Apache-2.0/MIT 技能的 `LICENSE` 与 `NOTICE` 随包保留；
   `ctv-mcp-server` 的 MIT 声明随内置源码保留。
4. **指南版权**：`nccn-download` 只分发**下载器**，不分发下载到的指南 PDF。
5. **论文/指南全文**：`pdf-translate` 只加工用户自备的文档，不预置受版权保护的正文。

---

## 五、复核方法

```bash
# 逐仓库复核许可（取实测值，不取印象）
for r in Medical-Record-Organizer clinical-trial-matching skill-HADS-accessment; do
  printf '%s → ' "$r"
  gh api "repos/opencare-skillhub/$r" --jq '.license.spdx_id // "NONE"'
done
```

**维护规则**：每新增一个入库技能，同一次提交内在本文件追加一行，`spdx_id` 必须是
实测输出，**`NONE` 必须显式写出，不许留空**。

---

## 二之二、已入库技能（实测，随代码一起交付）

以下技能已经实际导入到专家包，并有固定的溯源头（`source_repo` / `source_license` /
`adapted` / `readiness`）。导入由 `scripts/xyb_import_skills.py` 完成，可重跑、可审计。

| 技能 | 落点专家 | 源仓库 | `spdx_id` | 可分发 | `readiness` | 做了什么适配 |
|---|---|---|---|---|---|---|
| `distress-screening` | `xyb-mdt-psych` | `opencare-skillhub/skill-HADS-accessment` | **NONE** | ❌ 待补 | 受限（仅本机版） | **屏蔽公网发布路径**：上游会把问卷发布到外部托管平台收集作答，这与需求 §八「问卷保持本机版」直接冲突，已在正文顶部加范围声明，明确不执行该路径、不上传数据 |
| `chictr-collect` | `xyb-trial-matching` | `opencare-skillhub/chictr-trials-collector` | Apache-2.0 | ✅ | 需配置（Node 依赖自装） | 保留采集流程与字段说明作为方法与降级路径；**优先走已配置的 chictr MCP 通道** |
| `trial-intel-push` | `xyb-community-ops` | `opencare-skillhub/clinicaltrials-intel-skill` | Apache-2.0 | ✅ | 方法论层 | 只导入流程与字段规范（`SKILL.md`/`references`/`docs`/`LICENSE`），**不导入任何推送凭据**，避免把生产密钥带进仓库 |
| `nccn-download` | `xyb-community-ops` | `opencare-skillhub/nccn-guideline-downloader` | Apache-2.0 | ✅ 代码可分发 | 需配置（本人 NCCN 账号） | 只导入脚本与流程；**不导入任何凭据文件**（上游 cookie/config 模板随包，真实值由用户本机填写）。正文顶部明确：**只分发下载器，不分发指南正文**（指南受版权保护） |

### 关于「导入整仓」的取舍

只导入 `SKILL.md` 与必要参考文件，不整仓复制。原因是若干上游仓库带大量素材：
`Medical-Record-Organizer` 本地副本有 **5990 个文件**（含图片），整包入库会让专家包体积失控。
需要整仓能力的场景改为在技能正文里说明「需本机具备该源码」，而不是把素材塞进 wheel。

### 验证方法

```bash
python3 scripts/xyb_import_skills.py --list    # 看导入表
python3 scripts/xyb_import_skills.py --check   # 校验溯源头是否齐全
```

`--check` 会逐技能确认 `source_repo` / `source_license` / `adapted` / `readiness` 四个字段存在；
缺任何一个即判失败，防止「无来源的技能」混进仓库。
