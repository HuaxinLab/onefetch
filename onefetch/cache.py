from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse, urlunparse

from onefetch.config import Paths
from onefetch.models import IngestResult, LLMOutputs


class TempCacheService:
    def __init__(self, paths: Paths, *, max_entries: int = 200) -> None:
        self._cache_dir = paths.temp_cache_dir
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._max_entries = max(1, int(max_entries))

    def save_result(self, result: IngestResult) -> str:
        cache_id = self._build_cache_id(result.canonical_url, result.content_hash)
        path = self._cache_dir / f"{cache_id}.json"
        payload = {
            "cache_id": cache_id,
            "cached_at": datetime.now(timezone.utc).isoformat(),
            "source_url": result.source_url,
            "canonical_url": result.canonical_url,
            "crawler_id": result.crawler_id,
            "status": result.status,
            "title": result.title,
            "content_hash": result.content_hash,
            "comment_count": result.comment_count,
            "comment_source": result.comment_source,
            "body_preview": result.body_preview,
            "body_full": result.body_full,
            "images": result.images,
            "llm_outputs": result.llm_outputs.model_dump(),
            "llm_outputs_state": result.llm_outputs_state,
            "error": result.error,
            "error_code": result.error_code,
            "error_type": result.error_type,
            "retryable": result.retryable,
            "action_hint": result.action_hint,
        }
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        self._prune_if_needed()
        return str(path)

    def load_latest_result(self, url: str) -> IngestResult | None:
        target = _normalize_url(url)
        latest_payload: dict | None = None
        latest_time = ""

        for path in self._cache_dir.glob("*.json"):
            try:
                payload = json.loads(path.read_text(encoding="utf-8"))
            except Exception:
                continue

            source_url = str(payload.get("source_url") or "")
            canonical_url = str(payload.get("canonical_url") or "")
            source_norm = _normalize_url(source_url) if source_url else ""
            canonical_norm = _normalize_url(canonical_url) if canonical_url else ""
            if target not in {source_norm, canonical_norm}:
                continue

            cached_at = str(payload.get("cached_at") or "")
            if cached_at >= latest_time:
                latest_time = cached_at
                latest_payload = payload

        if latest_payload is None:
            return None
        return self._to_result(latest_payload)

    @staticmethod
    def _to_result(payload: dict) -> IngestResult:
        raw_status = str(payload.get("status") or "fetched")
        status = raw_status if raw_status in {"fetched", "stored", "duplicate", "failed"} else "fetched"
        llm_outputs = LLMOutputs.model_validate(payload.get("llm_outputs") or {})
        llm_outputs.extras = {**llm_outputs.extras, "cache_hit": True}
        llm_state = str(payload.get("llm_outputs_state") or "")
        if llm_state not in {"missing", "ok", "fallback"}:
            llm_state = _infer_llm_outputs_state(llm_outputs)
        return IngestResult(
            source_url=str(payload.get("source_url") or ""),
            canonical_url=str(payload.get("canonical_url") or ""),
            crawler_id=str(payload.get("crawler_id") or "unknown"),
            status=status,
            content_hash=str(payload.get("content_hash") or ""),
            title=str(payload.get("title") or ""),
            error=str(payload.get("error") or ""),
            error_code=str(payload.get("error_code") or ""),
            error_type=str(payload.get("error_type") or ""),
            retryable=bool(payload.get("retryable") or False),
            action_hint=str(payload.get("action_hint") or ""),
            comment_count=int(payload.get("comment_count") or 0),
            comment_source=str(payload.get("comment_source") or "none"),
            body_preview=str(payload.get("body_preview") or ""),
            body_full=str(payload.get("body_full") or ""),
            images=list(payload.get("images") or []),
            llm_outputs=llm_outputs,
            llm_outputs_state=llm_state,
        )

    def touch_result(self, canonical_url: str, content_hash: str) -> None:
        """Update mtime of an existing cache file without rewriting it."""
        cache_id = self._build_cache_id(canonical_url, content_hash)
        path = self._cache_dir / f"{cache_id}.json"
        if path.exists():
            path.touch()

    @staticmethod
    def _build_cache_id(canonical_url: str, content_hash: str) -> str:
        base = (canonical_url or "").strip() or "unknown_url"
        suffix = (content_hash or "").strip() or "no_hash"
        digest = hashlib.sha1(f"{base}|{suffix}".encode("utf-8")).hexdigest()[:16]
        return f"{digest}-{suffix[:12]}"

    def _prune_if_needed(self) -> None:
        files = sorted(self._cache_dir.glob("*.json"), key=lambda p: p.stat().st_mtime)
        overflow = len(files) - self._max_entries
        if overflow <= 0:
            return
        for path in files[:overflow]:
            path.unlink(missing_ok=True)


def _normalize_url(url: str) -> str:
    parsed = urlparse((url or "").strip())
    scheme = (parsed.scheme or "https").lower()
    netloc = parsed.netloc.lower().replace(":80", "").replace(":443", "")
    path = parsed.path.rstrip("/") or "/"
    cleaned = parsed._replace(scheme=scheme, netloc=netloc, path=path, fragment="")
    return urlunparse(cleaned)


def _infer_llm_outputs_state(llm_outputs: LLMOutputs) -> str:
    if llm_outputs.extras.get("validation_error"):
        return "fallback"
    if llm_outputs.summary or llm_outputs.key_points or llm_outputs.tags:
        return "ok"
    return "missing"
