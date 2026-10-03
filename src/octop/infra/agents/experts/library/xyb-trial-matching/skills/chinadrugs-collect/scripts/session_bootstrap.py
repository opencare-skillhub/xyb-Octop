#!/usr/bin/env python3
"""建立专用浏览器会话并保存 chinadrugtrials.org.cn Cookie。

此脚本只导出它自行创建的专用浏览器 Profile 中、目标站点的 Cookie。
不会读取用户日常 Chrome Profile，也不会尝试绕过验证码或其他访问控制。
"""

import argparse
import json
import shlex
import sys
import time
from datetime import datetime
from pathlib import Path

import requests
from playwright.sync_api import sync_playwright

from cookie_tools import (
    BROWSER_UA,
    cookie_dict_to_string,
    mask_cookie,
    parse_cookie_string,
    save_cookie_to_config,
)

BASE_URL = "https://www.chinadrugtrials.org.cn"
SEARCH_URL = f"{BASE_URL}/clinicaltrials.searchlist.dhtml"
LANDING_URL = f"{BASE_URL}/clinicaltrials.prosearch.dhtml"


def build_search_form(keywords="胰腺癌", state=""):
    """构建与平台搜索页一致的最小 POST 表单。"""
    return {
        "keywords": keywords,
        "sort": "desc",
        "sort2": "",
        "rule": "CTR",
        "secondLevel": "0" if state else "1",
        "currentpage": "1",
        "id": "",
        "ckm_index": "",
        "reg_no": "",
        "indication": "",
        "case_no": "",
        "drugs_name": "",
        "drugs_type": "",
        "appliers": "",
        "communities": "",
        "researchers": "",
        "agencies": "",
        "state": state,
    }


def is_challenge_response(html):
    """识别已知的空 body FSSBBI 挑战页，避免将其错判为零结果。"""
    lower = (html or "").lower()
    stripped = "".join((html or "").split())
    return (
        ("<body></body>" in stripped or "<body/>" in stripped)
        and (lower.count("<meta") >= 2 or "_$tw" in lower or "fssbbi" in lower)
    )


def validate_cookie(cookie_text, keywords, state, timeout=30):
    """使用 requests 对一次真实搜索作只读验证，返回结构化结果。"""
    session = requests.Session()
    for name, value in parse_cookie_string(cookie_text).items():
        session.cookies.set(name, value)
    response = session.post(
        SEARCH_URL,
        data=build_search_form(keywords, state),
        headers={
            "User-Agent": BROWSER_UA,
            "Accept-Language": "zh-CN,zh;q=0.9",
            "Origin": BASE_URL,
            "Referer": LANDING_URL,
        },
        timeout=timeout,
    )
    response.encoding = "utf-8"
    valid = response.ok and "searchTable" in response.text and not is_challenge_response(response.text)
    return {
        "valid": valid,
        "status_code": response.status_code,
        "challenge": is_challenge_response(response.text),
        "has_result_table": "searchTable" in response.text,
        "final_url": response.url,
    }


def build_curl(cookie_text, keywords, state):
    """从已验证的 Cookie 和公开搜索表单生成可复现的 cURL。"""
    form = build_search_form(keywords, state)
    parts = [
        "curl", "--compressed", "-X", "POST", shlex.quote(SEARCH_URL),
        "-H", shlex.quote(f"User-Agent: {BROWSER_UA}"),
        "-H", shlex.quote("Accept-Language: zh-CN,zh;q=0.9"),
        "-H", shlex.quote(f"Origin: {BASE_URL}"),
        "-H", shlex.quote(f"Referer: {LANDING_URL}"),
        "-H", shlex.quote(f"Cookie: {cookie_text}"),
    ]
    for key, value in form.items():
        parts.extend(["--data-urlencode", shlex.quote(f"{key}={value}")])
    return " \\\n  ".join(parts) + "\n"


def export_browser_cookies(config_path, profile_dir, keywords, state, wait_seconds, headed, interactive):
    """启动独立 Chromium Profile，导出目标域 Cookie 并保存到本地配置。"""
    config_path = Path(config_path).resolve()
    profile_dir = Path(profile_dir).resolve()
    profile_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as playwright:
        context = playwright.chromium.launch_persistent_context(
            user_data_dir=str(profile_dir),
            headless=not headed,
            viewport={"width": 1440, "height": 960},
            locale="zh-CN",
        )
        try:
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(LANDING_URL, wait_until="domcontentloaded", timeout=60000)
            page.wait_for_timeout(max(0, int(wait_seconds * 1000)))

            cookies = context.cookies([BASE_URL])
            cookie_text = cookie_dict_to_string({item["name"]: item["value"] for item in cookies})
            validation = validate_cookie(cookie_text, keywords, state)

            if not validation["valid"] and interactive and headed:
                print("\n浏览器已打开专用会话。若网页要求人工确认，请仅在该窗口完成正常验证。")
                input("完成后按回车继续导出 Cookie（直接回车也会继续）: ")
                page.reload(wait_until="domcontentloaded", timeout=60000)
                page.wait_for_timeout(1500)
                cookies = context.cookies([BASE_URL])
                cookie_text = cookie_dict_to_string({item["name"]: item["value"] for item in cookies})
                validation = validate_cookie(cookie_text, keywords, state)
        finally:
            context.close()

    if not cookie_text:
        raise RuntimeError("浏览器未导出任何目标站点 Cookie。")

    # 仅在真实搜索验证通过后覆盖本地会话，避免把挑战页产生的半成品 Cookie 写入配置。
    if not validation["valid"]:
        return {
            "updated_at": datetime.now().isoformat(),
            "profile_dir": str(profile_dir),
            "validation": validation,
            "curl_path": None,
            "cookie_fields": list(parse_cookie_string(cookie_text).keys()),
        }, None

    config = save_cookie_to_config(config_path, cookie_text, merge=True)
    session_dir = config_path.parent / ".session"
    session_dir.mkdir(parents=True, exist_ok=True)
    curl_path = session_dir / "latest-search.curl"
    curl_path.write_text(build_curl(config["cookies"], keywords, state), encoding="utf-8")
    try:
        curl_path.chmod(0o600)
    except OSError:
        pass

    metadata = {
        "updated_at": datetime.now().isoformat(),
        "profile_dir": str(profile_dir),
        "validation": validation,
        "curl_path": str(curl_path),
        "cookie_fields": list(parse_cookie_string(config["cookies"]).keys()),
    }
    (session_dir / "session.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
    return metadata, config


def main():
    parser = argparse.ArgumentParser(description="通过专用浏览器会话刷新中国药物临床试验平台 Cookie")
    parser.add_argument("--config", default="config.json", help="本地配置文件路径")
    parser.add_argument("--profile-dir", default=None, help="专用 Chromium Profile 目录")
    parser.add_argument("--keywords", default="胰腺癌", help="用于验证会话的关键词")
    parser.add_argument("--state", default="", help="用于验证会话的试验状态")
    parser.add_argument("--wait-seconds", type=float, default=3.0, help="首次页面加载后等待秒数")
    parser.add_argument("--headless", action="store_true", help="无界面运行；无法处理人工确认")
    parser.add_argument("--non-interactive", action="store_true", help="验证失败时不等待人工确认")
    args = parser.parse_args()

    config_path = Path(args.config).expanduser().resolve()
    profile_dir = Path(args.profile_dir).expanduser().resolve() if args.profile_dir else config_path.parent / ".browser-profile"
    try:
        metadata, config = export_browser_cookies(
            config_path=config_path,
            profile_dir=profile_dir,
            keywords=args.keywords,
            state=args.state,
            wait_seconds=args.wait_seconds,
            headed=not args.headless,
            interactive=not args.non_interactive,
        )
    except Exception as exc:
        print(f"会话刷新失败: {exc}", file=sys.stderr)
        return 1

    validation = metadata["validation"]
    print(f"浏览器导出 {len(metadata['cookie_fields'])} 个 Cookie 字段。")
    print(f"验证搜索: HTTP {validation['status_code']}；结果表={validation['has_result_table']}；挑战页={validation['challenge']}")
    if validation["valid"]:
        print(f"Cookie（脱敏）: {mask_cookie(config['cookies'])}")
        print('会话状态: 可用，已保存到本地配置。')
        print(f"本地 cURL（含敏感 Cookie，已限制文件权限）: {metadata['curl_path']}")
        return 0
    print('会话状态: 未通过验证；未修改已有 config.json，也未保存 cURL。')
    return 2


if __name__ == "__main__":
    sys.exit(main())
