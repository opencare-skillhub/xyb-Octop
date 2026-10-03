# xyb-wechat-article-transcription

This repository packages the `xyb-wechat-transcribe` skill.

## Contents

- `skills/xyb-wechat-transcribe`: WeChat public-account download, transcribe, rewrite, and HTML rendering skill

## Usage

Install or copy the `skills/xyb-wechat-transcribe` directory into your Codex skill path.

## Extraction Policy

The renderer reads the full WeChat `js_content` DOM and cleans it by subtraction. It keeps body text, tables, and non-ad inline images, then truncates at footer-operation boundaries such as recommendation blocks, online-visit guide sections, account-promotion sections, author/editor bylines, or tiny decorative footer images.
