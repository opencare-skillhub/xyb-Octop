# china-drug-trials-skills

可独立部署的 WorkBuddy Skill：采集中国药物临床试验登记与信息公示平台记录，并输出原始 HTML、网页原样 Word 与 RAG JSON。

## 独立性

本目录不依赖父项目路径。所有可执行代码与依赖声明均在 `scripts/` 中：

```text
china-drug-trials-skills/
├── SKILL.md
├── README.md
├── scripts/
│   ├── scraper.py
│   ├── main.py
│   ├── cookie_tools.py
│   ├── session_bootstrap.py
│   ├── build_json_from_raw.py
│   ├── verify_output.py
│   ├── config.example.json
│   └── requirements.txt
└── references/
    └── platform-workflow.md
```

## 作为 Skill 部署

将整个 `china-drug-trials-skills/` 目录复制到目标环境的 Skill 目录，或使用 `china-drug-trials-skills.zip` 安装。不要只复制 `SKILL.md`，脚本目录是完整工作流的一部分。

## 直接命令行使用

```bash
cd china-drug-trials-skills
python3 -m venv .venv
source .venv/bin/activate
pip install -r scripts/requirements.txt
python3 -m playwright install chromium
cp scripts/config.example.json config.json
python3 scripts/main.py
```

`main.py` 会在当前目录读取/创建 `config.json`。Cookie 管理优先选择菜单 **3. 刷新浏览器会话**：它只启动并使用本 Skill 自己的 Chromium Profile，自动导出 `chinadrugtrials.org.cn` Cookie，验证一次真实搜索，并把本地 cURL 保存到 `.session/latest-search.curl`。不会读取日常 Chrome Profile；如站点要求人工验证，只需在该专用窗口中按正常流程完成后回到终端按回车。

也可直接运行：

```bash
# 打开可见的专用浏览器并刷新会话
python3 scripts/session_bootstrap.py --config config.json --keywords "胰腺癌" --state "招募中"

# 检测到挑战页时自动尝试刷新会话，然后只重试一次
python3 scripts/scraper.py --config config.json --incremental --auto-refresh-session
```

`.browser-profile/`、`.session/`、`config.json` 都被 `.gitignore` 排除，可能含会话凭证，不能提交或发送。若程序仍报告会话未验证，不会把结果误报为“0 条”；请完成网站正常要求的人工确认后再次执行刷新。

也可以直接运行：

```bash
python3 scripts/scraper.py --config config.json
python3 scripts/scraper.py --config config.json --incremental

# 核对最近一次成功登记号的归档完整性
python3 scripts/verify_output.py --output "output/胰腺癌"
```

在 Linux 或 Windows 上，脚本仍可保存网页原样 WordML `.doc`；若无 macOS `textutil`，用下列命令在验收时忽略可选的 `.docx`：

```bash
python3 scripts/verify_output.py --output "output/胰腺癌" --allow-missing-docx
```

## 安全与合规

- Cookie 仅保存在本地；不要提交、发送或打包真实 `config.json`。
- 仅处理有权访问的信息，遵守目标平台规则和适用要求。
- 保持合理请求间隔，不并发访问、不规避访问控制。

完整操作说明见 `SKILL.md`。
