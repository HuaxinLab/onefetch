from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, Field


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _uuid() -> str:
    return str(uuid.uuid4())


class FeedComment(BaseModel):
    author: str | None = None
    text: str


class ImageAsset(BaseModel):
    src: str
    alt: str = ""
    href: str = ""


def normalize_images(images: list[Any] | None) -> list[dict[str, str]]:
    rows: list[dict[str, str]] = []
    for raw in images or []:
        if isinstance(raw, ImageAsset):
            src = str(raw.src or "").strip()
            alt = str(raw.alt or "").strip()
            href = str(raw.href or "").strip()
        elif isinstance(raw, dict):
            src = str(raw.get("src") or "").strip()
            alt = str(raw.get("alt") or "").strip()
            href = str(raw.get("href") or "").strip()
        else:
            src = str(raw or "").strip()
            alt = ""
            href = ""
        if not src:
            continue
        rows.append({"src": src, "alt": alt, "href": href})
    return rows


def image_src(raw: Any) -> str:
    if isinstance(raw, ImageAsset):
        return str(raw.src or "").strip()
    if isinstance(raw, dict):
        return str(raw.get("src") or "").strip()
    return str(raw or "").strip()


class FeedEntry(BaseModel):
    id: str = Field(default_factory=_uuid)
    source_url: str
    canonical_url: str
    crawler_id: str
    title: str = ""
    author: str | None = None
    published_at: datetime | None = None
    body: str = ""
    raw_body: str = ""
    images: list[Any] = Field(default_factory=list)
    comments: list[FeedComment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    fetched_at: datetime = Field(default_factory=_now)

    def compute_content_hash(self) -> str:
        comment_blob = "\n".join(item.text for item in self.comments)
        payload = "\n".join([self.title.strip(), self.body.strip(), comment_blob.strip()])
        self.content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self.content_hash


class LLMOutputs(BaseModel):
    summary: str = ""
    key_points: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    extras: dict[str, Any] = Field(default_factory=dict)


class IngestResult(BaseModel):
    source_url: str
    canonical_url: str
    crawler_id: str
    status: Literal["fetched", "stored", "duplicate", "failed"]
    content_hash: str = ""
    title: str = ""
    author: str = ""
    published_at: str = ""
    error: str = ""
    error_code: str = ""
    error_type: str = ""
    retryable: bool = False
    action_hint: str = ""
    feed_path: str = ""
    comment_count: int = 0
    comment_source: str = "none"
    body_preview: str = ""
    body_full: str = ""
    images: list[ImageAsset] = Field(default_factory=list)
    cache_path: str = ""
    llm_outputs: LLMOutputs = Field(default_factory=LLMOutputs)
    llm_outputs_state: Literal["missing", "ok", "fallback"] = "missing"
    risk_controlled: bool = False


class BatchIngestReport(BaseModel):
    requested_urls: list[str]
    results: list[IngestResult] = Field(default_factory=list)
    fetched_count: int = 0
    stored_count: int = 0
    duplicate_count: int = 0
    failed_count: int = 0


class DiscoverResult(BaseModel):
    seed_url: str
    expander_id: str = ""
    discovered_urls: list[str] = Field(default_factory=list)
    stats: dict[str, Any] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)
    next_cursor: str = ""
    status: Literal["ok", "failed"] = "ok"
    error: str = ""


class BatchDiscoverReport(BaseModel):
    run_id: str = ""
    generated_at: str = ""
    requested_urls: list[str]
    results: list[DiscoverResult] = Field(default_factory=list)
    discovered_count: int = 0
    failed_count: int = 0
