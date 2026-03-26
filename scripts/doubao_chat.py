#!/usr/bin/env python3
"""Doubao (豆包) chat API client for onefetch.

Usage:
    python scripts/doubao_chat.py "你好"
    python scripts/doubao_chat.py "提取图片中的所有文字：http://example.com/image.jpg"
    python scripts/doubao_chat.py --cookie /path/to/cookie "message"
    echo "翻译成英文" | python scripts/doubao_chat.py

Cookie: .secrets/doubao_cookie.txt (header string format: key=val; key=val)
    Or specify --cookie <path>
"""

import argparse
import json
import os
import sys
import time
import uuid
from pathlib import Path

import httpx

BASE_URL = "https://www.doubao.com"
BOT_ID = "7338286299411103781"

PROJECT_ROOT = Path(os.environ.get("ONEFETCH_PROJECT_ROOT", Path(__file__).resolve().parent.parent))


def load_cookie(cookie_path: str | None = None) -> str:
    """Load cookie string, auto-detecting format."""
    candidates = []
    if cookie_path:
        candidates.append(Path(cookie_path))
    else:
        candidates.append(PROJECT_ROOT / ".secrets" / "doubao_cookie.txt")

    for path in candidates:
        if not path.exists():
            continue
        raw = path.read_text(encoding="utf-8").strip()
        if not raw:
            continue

        # Try api-scout JSON format
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

        # Plain cookie string
        if "=" in raw and not raw.startswith("{"):
            return raw

    print("Error: No doubao cookie found.", file=sys.stderr)
    print("Run: bash scripts/setup_cookie.sh doubao.com", file=sys.stderr)
    sys.exit(1)


def chat(message: str, cookie: str) -> str:
    """Send a message to Doubao and return the reply."""
    params = {
        "aid": "497858",
        "device_id": "7619249794900690447",
        "device_platform": "web",
        "language": "zh",
        "pc_version": "3.10.4",
        "pkg_type": "release_version",
        "real_aid": "497858",
        "samantha_web": "1",
        "use-olympus-account": "1",
        "version_code": "20800",
        "web_id": "7619249808787850803",
        "web_tab_id": str(uuid.uuid4()),
    }

    headers = {
        "Content-Type": "application/json",
        "Cookie": cookie,
        "User-Agent": (
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/131.0.0.0 Safari/537.36"
        ),
        "Referer": f"{BASE_URL}/",
        "Accept": "application/json, text/plain, */*",
        "agw-js-conv": "str, str",
    }

    body = {
        "client_meta": {
            "local_conversation_id": f"local_{int(time.time() * 1000)}",
            "conversation_id": "",
            "bot_id": BOT_ID,
            "last_section_id": "",
            "last_message_index": None,
        },
        "messages": [{
            "local_message_id": str(uuid.uuid4()),
            "content_block": [{
                "block_type": 10000,
                "content": {
                    "text_block": {"text": message},
                    "pc_event_block": "",
                },
                "block_id": str(uuid.uuid4()),
                "parent_id": "",
                "meta_info": [],
                "append_fields": [],
            }],
            "message_status": 0,
        }],
        "option": {
            "send_message_scene": "",
            "create_time_ms": int(time.time() * 1000),
            "need_deep_think": 0,
            "need_create_conversation": True,
            "tts_switch": False,
            "is_regen": False,
            "is_replace": False,
            "unique_key": str(uuid.uuid4()),
            "start_seq": 0,
        },
        "ext": {"use_deep_think": "0"},
    }

    t0 = time.time()
    full_text = ""
    conversation_id = ""

    with httpx.Client(timeout=120, verify=False) as client:
        with client.stream("POST", f"{BASE_URL}/chat/completion",
                           params=params, headers=headers, json=body) as resp:
            if resp.status_code != 200:
                print(f"Error: HTTP {resp.status_code}", file=sys.stderr)
                try:
                    print(resp.read().decode()[:300], file=sys.stderr)
                except Exception:
                    pass
                return ""

            current_event = ""
            for line in resp.iter_lines():
                if line.startswith("event:"):
                    current_event = line[6:].strip()
                    continue
                if not line.startswith("data:"):
                    continue

                data_str = line[5:].strip()
                if not data_str or data_str == "{}":
                    continue

                try:
                    data = json.loads(data_str)
                except json.JSONDecodeError:
                    continue

                if current_event == "SSE_ACK":
                    cid = data.get("ack_client_meta", {}).get("conversation_id", "")
                    if cid:
                        conversation_id = cid

                elif current_event == "STREAM_MSG_NOTIFY":
                    for block in data.get("content", {}).get("content_block", []):
                        text = block.get("content", {}).get("text_block", {}).get("text", "")
                        if text:
                            full_text += text

                elif current_event == "STREAM_CHUNK":
                    for patch in data.get("patch_op", []):
                        if patch.get("patch_object") != 1:
                            continue
                        for block in patch.get("patch_value", {}).get("content_block", []):
                            text = block.get("content", {}).get("text_block", {}).get("text", "")
                            if text:
                                full_text += text

                elif current_event == "STREAM_ERROR":
                    code = data.get("error_code", "?")
                    msg = data.get("error_msg", "unknown")
                    print(f"Error: {code} — {msg}", file=sys.stderr)
                    return ""

        # Clean up: delete the conversation to avoid polluting user's chat list
        if conversation_id:
            try:
                # IM endpoints require different headers than chat
                im_headers = {**headers, "Content-Type": "application/json; encoding=utf-8", "agw-js-conv": "str"}
                client.post(
                    f"{BASE_URL}/im/conversation/batch_del_user_conv",
                    params=params,
                    headers=im_headers,
                    json={
                        "cmd": 4171,
                        "uplink_body": {
                            "batch_delete_user_conversation_uplink_body": {
                                "conversation_id": [conversation_id],
                                "delete_all": False,
                                "conversation_type": 3,
                            }
                        },
                        "sequence_id": str(uuid.uuid4()),
                        "channel": 2,
                        "version": "1",
                    },
                )
            except Exception:
                pass

    elapsed = time.time() - t0
    print(f"[{elapsed:.1f}s]", file=sys.stderr)
    return full_text


def main():
    parser = argparse.ArgumentParser(description="Doubao chat API (supports image/video URL understanding)")
    parser.add_argument("message", nargs="*", help="Message to send (can include URLs)")
    parser.add_argument("--cookie", "-c", help="Path to cookie file")
    args = parser.parse_args()

    if args.message:
        message = " ".join(args.message)
    elif not sys.stdin.isatty():
        message = sys.stdin.read().strip()
    else:
        print("Usage: python scripts/doubao_chat.py <message>", file=sys.stderr)
        sys.exit(1)

    if not message:
        sys.exit(1)

    cookie = load_cookie(args.cookie)
    result = chat(message, cookie)
    if result:
        print(result)


if __name__ == "__main__":
    main()
