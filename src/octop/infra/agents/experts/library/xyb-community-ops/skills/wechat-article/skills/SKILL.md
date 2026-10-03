---
name: xyb-wechat-transcribe
description: Download or read a WeChat public account article, rewrite it into an xyb-style WeChat HTML article, and save the final HTML to an absolute path. Use when the user provides an mp.weixin.qq.com link or a local article file and wants a complete transcribe->rewrite->HTML output chain with template selection, defaulting to template1 morandi purple unless the user chooses otherwise.
---

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
