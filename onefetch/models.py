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


class Capture(BaseModel):
    id: str = Field(default_factory=_uuid)
    source_url: str
    canonical_url: str
    final_url: str
    status_code: int
    headers: dict[str, str] = Field(default_factory=dict)
    body: str
    fetched_at: datetime = Field(default_factory=_now)


class FeedEntry(BaseModel):
    id: str = Field(default_factory=_uuid)
    source_url: str
    canonical_url: str
    crawler_id: str
    title: str = ""
    author: str | None = None
    published_at: datetime | None = None
    body: str = ""
    comments: list[FeedComment] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    content_hash: str = ""
    fetched_at: datetime = Field(default_factory=_now)

    def compute_content_hash(self) -> str:
        comment_blob = "\n".join(item.text for item in self.comments)
        payload = "\n".join([self.title.strip(), self.body.strip(), comment_blob.strip()])
        self.content_hash = hashlib.sha256(payload.encode("utf-8")).hexdigest()
        return self.content_hash


class CrawlOutput(BaseModel):
    capture: Capture
    feed: FeedEntry


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
    error: str = ""
    error_code: str = ""
    error_type: str = ""
    retryable: bool = False
    raw_path: str = ""
    feed_path: str = ""
    note_path: str = ""
    comment_count: int = 0
    comment_source: str = "none"
    body_preview: str = ""
    body_excerpt: str = ""
    body_full: str = ""
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
