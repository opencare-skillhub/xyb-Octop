---
name: wechat-article
description: 当要把一篇公众号文章改写成小胰宝风格的公众号 HTML，或需要按模板排版输出时使用。覆盖「取原文 → 改写 → 套模板 → 存成本地 HTML」整条链路；模板可指定，默认按技能说明。**只产出本地 HTML**，不代替运营发布，也不含任何公众号密钥。Use to rewrite an article into Xiaoyibao-style WeChat HTML locally.
metadata:
  octop:
    emoji: "📰"
    label:
      zh: "公众号文章改写排版"
      en: "WeChat Article Rewrite"
    summary:
      zh: "取原文→改写→套模板→存本地 HTML；不含任何发布密钥。"
      en: "Transcribe, rewrite and template an article into local WeChat HTML."
source_repo: opencare-skillhub/xyb-wechat-article-transcription
source_license: Apache-2.0
adapted: 2026-10-02
readiness: 可直接使用（改写与排版在本机完成；发表到公众号需自备凭据，本项目不含任何密钥）
---
> ## 使用范围（优先级高于本文其余内容）
>
> - 本技能**只产出本地 HTML 文件**。发布到公众号由运营人员自行操作，本项目**不含**任何公众号密钥、AppSecret 或 cookie。
> - 改写医学内容时受 `xyb-evidence-guard` / `xyb-medical-disclaimer` 约束；去 AI 腔走 `humanizer`，且**不得改动证据等级或结论强度**。
> - 涉及病友故事、患者照片与影像时，先过 `xyb-record-desensitize`：**不得使用可识别到个人的素材**。
> - 排版配色应与小胰宝品牌一致（基色薄荷绿 `#2F8F80`）；上游提供多种主题模板，选用时注意与品牌协调。


# XYB WeChat Transcribe

Use this skill to turn a WeChat article into an xyb-style公众号 HTML output.

## Input modes

Accept either:
- a `mp.weixin.qq.com` article URL, or
- a local file path containing HTML, MD, or text.

If the input is a WeChat URL, download the article first with the bundled downloader logic. Do not ask the user to run another skill.

## Flow

1. Detect whether the input is a URL or a local file path.
2. If URL, download HTML and MD via the remote MCP downloader.
3. Read the source content and extract the article title, summary, and body from the full `js_content` DOM.
4. Ask for template family if not already specified. Default to `template1`.
5. Ask for color style if not already specified. Default to `morandi_purple`.
6. If the user wants raw original article element retention, use template style 3; otherwise use the preset template elements.
6. Ask for rewrite requirements if not already specified, including the desired tone or extra emphasis.
7. Rewrite the article for公众号 readability while preserving factual data.
8. Render the article into the chosen xyb template.
9. Save the HTML under `~/Downloads/公众号转写结果/` by default and return the absolute file path for review.

## Priority rules

- Treat template assets as stable skeletons and style references.
- Do not edit template assets during ordinary transcribe/render runs.
- Rebuild a new HTML from content plus the selected skeleton/elements; do not keep patching templates for each article.
- Only repair a template asset when a real structural defect is confirmed and reproducible.
- If the skeleton is valid, keep it unchanged and regenerate the output HTML from content.
- Final output filenames must not contain `模版` or `模板`.

## Template selection

Default to `template1` + `xyb_template_morandi_purple.html`.

Available template families:
- `template1`: the standard xyb card-style layout used by `xyb-wechat-article-generator`
- `template2`: the special xyb feature-story layout used by `xyb-wechat-article-generator`
- `template3`: the raw-article element retention layout, preserving original WeChat section structure while still applying xyb color and output rules

Available styles:
- `morandi_purple` (default)
- `morandi_green`
- `raw_original`

Interaction rule:
- If the user has not explicitly chosen a family or style, prompt for both in one step and continue with the defaults if they accept.
- If the user has not specified rewrite requirements, prompt for a short rewrite brief and continue after collecting it.

If the user does not specify the template family or style, ask them to choose from the two families and the two styles, then continue.

## Rewrite requirements

Always preserve:
- factual data
- names
- dates
- percentages
- trial numbers
- paper conclusions

Allowed rewrite actions:
- make the language easier for公众号 readers
- reorganize long paragraphs into sections
- add brief explanation around technical terms
- keep key medical terms bold
- split long text into short paragraphs or numbered blocks

Formatting requirements:
- prefer section titles, short paragraphs, and numbered lists for dense technical content
- keep each rendered paragraph within about 2-3 lines on mobile when possible, and generally no more than 5 lines
- avoid dumping one idea into a single long block when it can be split without changing meaning
- use blank lines, decorative dividers, or small icon separators between paragraph groups when helpful
- preserve and elevate markdown markers from the source text, especially `1.`/`2.` section numbers and `-` bullet lists, instead of flattening them into plain paragraphs

Do not invent new data or claims.

USP cover subtitle rule:
- generate a content-derived 8-character hook
- format must be exactly `4字·4字`
- the separator must be the middle dot `·`
- never use a period `.`, template name, or workflow label in that position
- prefer tense, contrasting, title-derived phrases over safe generic wording
- if the title contains a clear conflict or pain point, extract that conflict into the hook

Template selection rule:
- `template1` and `template2` should use preset template elements, not the original article's section structure
- `template3` is the only mode that preserves the original article element structure and only applies xyb color/output conventions

Body boundary rule:
- Use subtractive cleanup when the original WeChat `js_content` is available.
- Preserve the article body from the title/content start, including non-ad inline images and tables.
- Stop the body at the first tail-operation marker and drop that node plus everything after it.
- Tail markers include recommendation blocks, online-visit guide blocks, account promotion blocks, author/editor bylines, and tiny decorative boundary images that introduce footer content.
- For the Fudan Cancer Hospital template family, the tiny image URL containing `O4S31l7wCFJqWpeLPjziaibleMm4WF2WPjUSIN3yXNyMsdrTQFuxEy7mDpNJVLtAcXRnJicc1wJlXHd21XLrr0E1RUnPsCfV8KNwtuPYqmiaBnA` is a hard footer boundary; remove it and all following content.
- Do not keep tail text such as `在线就诊指南`, `近期热文`, `有爱不惧癌`, `撰文：`, or `编辑：`.

## Output

Write one HTML file and report:
- the absolute output path
- the selected template family
- the selected style
- the source input path or URL
- the extracted title and summary

## Implementation note

Use the bundled script in `scripts/render.py` for downloading, reading, rewriting, and rendering.
