from __future__ import annotations

import json
import re
from typing import Any

from onefetch.models import LLMOutputs

_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{[\s\S]*?\})\s*```", re.IGNORECASE)
_IMG_MARKERS_RE = re.compile(r"\[(?:IMG|IMG_CAPTION):\d+\]\s*")

_MAX_SUMMARY_CHARS = 4000
_MAX_KEY_POINTS = 12
_MAX_TAGS = 20
_MAX_RAW_OUTPUT = 4000


def parse_and_validate_llm_outputs(raw_text: str) -> LLMOutputs:
    payload: Any = None
    parse_error = ""
    repaired = False

    parse_attempts = [_parse_direct_json, _parse_fenced_json, _parse_braced_json]
    for index, parser in enumerate(parse_attempts):
        try:
            payload = parser(raw_text)
            repaired = index > 0
            break
        except ValueError as exc:
            parse_error = str(exc)

    if payload is None:
        return LLMOutputs(
            extras={
                "validation_error": parse_error or "invalid_json",
                "raw_output": (raw_text or "")[:_MAX_RAW_OUTPUT],
            }
        )

    return _normalize_payload(payload, raw_text=raw_text, repaired=repaired)


def _parse_direct_json(raw_text: str) -> Any:
    return json.loads(raw_text)


def _parse_fenced_json(raw_text: str) -> Any:
    match = _JSON_FENCE_RE.search(raw_text or "")
    if not match:
        raise ValueError("json_code_block_not_found")
    return json.loads(match.group(1))


def _parse_braced_json(raw_text: str) -> Any:
    text = raw_text or ""
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError("json_object_not_found")
    return json.loads(text[start : end + 1])


def _normalize_payload(payload: Any, *, raw_text: str, repaired: bool) -> LLMOutputs:
    if not isinstance(payload, dict):
        return LLMOutputs(
            extras={
                "validation_error": "payload_is_not_object",
                "raw_output": (raw_text or "")[:_MAX_RAW_OUTPUT],
            }
        )

    summary = _normalize_summary(payload.get("summary"))
    key_points = _normalize_list(payload.get("key_points"), max_items=_MAX_KEY_POINTS)
    tags = _normalize_list(payload.get("tags"), max_items=_MAX_TAGS)
    extras = _normalize_extras(payload.get("extras"))

    for key, value in payload.items():
        if key in {"summary", "key_points", "tags", "extras"}:
            continue
        extras[key] = value

    if repaired:
        extras["repaired_from_non_strict_json"] = True

    return LLMOutputs(summary=summary, key_points=key_points, tags=tags, extras=extras)


def _normalize_summary(value: Any) -> str:
    if value is None:
        return ""
    summary = _strip_image_markers(str(value))
    return summary[:_MAX_SUMMARY_CHARS]


def _normalize_list(value: Any, *, max_items: int) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        candidates = [item.strip("- ").strip() for item in re.split(r"[\n;]+", value) if item.strip()]
    elif isinstance(value, list):
        candidates = [str(item).strip() for item in value if str(item).strip()]
    else:
        candidates = [str(value).strip()] if str(value).strip() else []

    seen: set[str] = set()
    normalized: list[str] = []
    for item in candidates:
        item = _strip_image_markers(item)
        if not item:
            continue
        if item in seen:
            continue
        seen.add(item)
        normalized.append(item)
        if len(normalized) >= max_items:
            break
    return normalized


def _normalize_extras(value: Any) -> dict[str, Any]:
    if value is None:
        return {}
    if isinstance(value, dict):
        return dict(value)
    return {"raw_extras": value}


def _strip_image_markers(text: str) -> str:
    cleaned = _IMG_MARKERS_RE.sub("", text or "")
    cleaned = re.sub(r"\s{2,}", " ", cleaned).strip()
    return cleaned
