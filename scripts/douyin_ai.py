#!/usr/bin/env python3
"""Douyin AI video assistant — get video transcript/summary via AI chat.

Usage:
    # Summary (fast, default)
    python scripts/douyin_ai.py <aweme_id_or_url>
    python scripts/douyin_ai.py 7621006894580141348 "总结视频内容"

    # Full transcript (uses deep think mode)
    python scripts/douyin_ai.py --deep <aweme_id_or_url> "给我完整的视频文字版"

    # Both: summary first, then full transcript
    python scripts/douyin_ai.py --full <aweme_id_or_url>

    # Short link
    python scripts/douyin_ai.py "https://v.douyin.com/xxx/"

Default question: "总结视频内容"

Cookie: .secrets/douyin_cookie.txt (header string format)
Output: AI reply on stdout, timing on stderr
"""

import argparse
import json
import re
import sys
import time
from pathlib import Path

import httpx
from onefetch.credentials import get_cookie_for_domains

BASE_URL = "https://so-landing.douyin.com"
AID = "6383"
DEVICE_ID = "7621538686223533610"


def load_cookie(cookie_path: str | None = None) -> str:
    if cookie_path:
        raw = Path(cookie_path).read_text(encoding="utf-8").strip()
        if raw:
            try:
                data = json.loads(raw)
                if isinstance(data, dict):
                    s = data.get("full_cookie_string", "")
                    if not s and data.get("cookies"):
                        s = "; ".join(f"{k}={v}" for k, v in data["cookies"].items())
                    if s:
                        return s
            except (json.JSONDecodeError, TypeError):
                pass
            return raw

    resolved = get_cookie_for_domains(
        ["douyin.com", "www.douyin.com"],
        parse_json_cookie=True,
    )
    if resolved:
        return resolved

    print("Error: No douyin cookie found.", file=sys.stderr)
    print("Run: bash scripts/setup_cookie.sh douyin.com", file=sys.stderr)
    sys.exit(1)


def resolve_aweme_id(input_str: str) -> str:
    """Extract aweme_id from URL or return as-is if already an ID."""
    # Pure numeric ID
    if re.match(r"^\d+$", input_str):
        return input_str

    # Full URL: https://www.douyin.com/video/7621006894580141348
    m = re.search(r"/video/(\d+)", input_str)
    if m:
        return m.group(1)

    # Short link: https://v.douyin.com/xxx/ — follow redirect
    if "v.douyin.com" in input_str or "douyin.com" in input_str:
        try:
            with httpx.Client(timeout=10, follow_redirects=True, verify=False) as client:
                resp = client.get(input_str)
                m = re.search(r"/video/(\d+)", str(resp.url))
                if m:
                    return m.group(1)
        except Exception as e:
            print(f"Error resolving short link: {e}", file=sys.stderr)

    print(f"Error: Cannot extract aweme_id from: {input_str}", file=sys.stderr)
    sys.exit(1)


def ai_stream(aweme_id: str, keyword: str, cookie: str, *, deep_think: bool = False) -> str:
    """Call Douyin AI stream API and return the text response."""
    params = {
        "keyword": keyword,
        "ai_search_enter_from_group_id": aweme_id,
        "aid": AID,
        "device_id": DEVICE_ID,
        "search_channel": "aweme_ai_chat",
        "search_type": "ai_chat_search",
        "ai_page_type": "ai_chat",
        "token": "search",
        "count": "5",
        "cursor": "0",
        "version_code": "32.1.0",
        "enter_from": "search_result",
        "enter_method": "ai_input",
        "search_source": "ai_input",
        "enable_ai_tab_new_framework": "1",
        "need_integration_card": "1",
        "enable_ai_search_deep_think": "1" if deep_think else "0",
        "ai_chat_message_use_lynx": "1",
        "pc_ai_search_enable_ruyi": "1",
        "pc_ai_search_enable_rich_media": "0",
    }

    headers = {
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": f"{BASE_URL}/",
    }

    t0 = time.time()
    full_text = ""

    with httpx.Client(timeout=120, verify=False) as client:
        with client.stream("GET", f"{BASE_URL}/douyin/select/v1/ai/stream/",
                           params=params, headers=headers) as resp:
            if resp.status_code != 200:
                print(f"Error: HTTP {resp.status_code}", file=sys.stderr)
                return ""

            for line in resp.iter_lines():
                if not line.startswith("data:"):
                    continue
                try:
                    d = json.loads(line[5:])
                except json.JSONDecodeError:
                    continue

                # Extract text from generation_spans (type=2)
                spans = _find_key_deep(d, "generation_spans")
                for span_list in spans:
                    if not isinstance(span_list, list):
                        continue
                    for span in span_list:
                        if not isinstance(span, dict):
                            continue
                        if span.get("type") != 2:
                            continue
                        text_obj = span.get("text")
                        if isinstance(text_obj, dict):
                            content = text_obj.get("content", "")
                            if content:
                                full_text += content
                        elif isinstance(text_obj, str) and text_obj:
                            full_text += text_obj

    elapsed = time.time() - t0
    print(f"[{elapsed:.1f}s]", file=sys.stderr)
    return full_text


def _find_key_deep(obj, target_key, depth=0):
    """Recursively find all values for a given key."""
    results = []
    if depth > 15:
        return results
    if isinstance(obj, dict):
        for k, v in obj.items():
            if k == target_key:
                results.append(v)
            results.extend(_find_key_deep(v, target_key, depth + 1))
    elif isinstance(obj, list):
        for item in obj:
            results.extend(_find_key_deep(item, target_key, depth + 1))
    return results


def main():
    parser = argparse.ArgumentParser(description="Douyin AI video assistant")
    parser.add_argument("input", help="Video aweme_id or URL")
    parser.add_argument("question", nargs="?", default=None,
                        help="Question to ask (default: 总结视频内容)")
    parser.add_argument("--cookie", "-c", help="Path to cookie file")
    parser.add_argument("--deep", action="store_true",
                        help="Enable deep think mode (better for full transcript)")
    parser.add_argument("--full", action="store_true",
                        help="Two-step: summary first, then full transcript with deep think")
    args = parser.parse_args()

    aweme_id = resolve_aweme_id(args.input)
    print(f"aweme_id: {aweme_id}", file=sys.stderr)
    cookie = load_cookie(args.cookie)

    if args.full:
        # Step 1: Summary
        print("## 视频总结\n", file=sys.stderr)
        summary = ai_stream(aweme_id, "总结视频内容", cookie, deep_think=False)
        if summary:
            print("## 视频总结\n")
            print(summary)
            print()

        # Step 2: Full transcript with deep think
        print("\n## 完整文字版\n", file=sys.stderr)
        transcript = ai_stream(aweme_id, "给我完整的视频文字版/字幕，不要省略任何内容", cookie, deep_think=True)
        if transcript:
            print("## 完整文字版\n")
            print(transcript)
    else:
        question = args.question or "总结视频内容"
        result = ai_stream(aweme_id, question, cookie, deep_think=args.deep)
        if result:
            print(result)
        else:
            print("Error: No response", file=sys.stderr)
            sys.exit(1)


if __name__ == "__main__":
    main()
