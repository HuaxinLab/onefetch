from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from html import unescape
from urllib.parse import urlparse

from lxml import html

from onefetch.adapters.base import BaseAdapter
from onefetch.adapters.generic_html import GenericHtmlAdapter
from onefetch.http import create_async_client
from onefetch.models import Capture, CrawlOutput, FeedEntry
from onefetch.router import normalize_url

_INITIAL_DATA_RE = re.compile(
    r'<script id="js-initialData" type="text/json">([\s\S]*?)</script>',
    re.IGNORECASE,
)


class ZhihuAdapter(BaseAdapter):
    id = "zhihu"
    priority = 250

    def supports(self, url: str) -> bool:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        path = parsed.path or "/"
        return host.endswith("zhihu.com") and path.startswith("/question/")

    async def crawl(self, url: str) -> CrawlOutput:
        final_url, body_text, status_code, headers, render_mode, browser_status = await self._fetch_html(url)

        canonical = normalize_url(final_url)
        tree = html.fromstring(body_text)
        state = self._extract_initial_state(body_text)

        question_id, answer_id = self._extract_ids(final_url)
        title = self._first_text(
            tree,
            [
                "//meta[@property='og:title']/@content",
                "//meta[@name='og:title']/@content",
                "//title/text()",
            ],
        )
        author = self._first_text(tree, ["//meta[@name='author']/@content"])

        content, parsed_title, parsed_author, published_at, metadata = await self._build_from_state(
            state,
            question_id,
            answer_id,
        )
        if parsed_title:
            title = parsed_title
        if parsed_author:
            author = parsed_author
        if not content:
            content = self._extract_fallback_body(tree)

        if title and title.endswith(" - 知乎"):
            title = title[: -len(" - 知乎")].strip()

        capture = Capture(
            source_url=url,
            canonical_url=canonical,
            final_url=final_url,
            status_code=status_code,
            headers=headers,
            body=body_text,
        )
        feed = FeedEntry(
            source_url=url,
            canonical_url=canonical,
            crawler_id=self.id,
            title=title or "知乎内容",
            author=author,
            published_at=published_at,
            body=content[:60000],
            metadata={
                "platform": "zhihu",
                "render_mode": render_mode,
                "browser": browser_status,
                **metadata,
            },
        )
        return CrawlOutput(capture=capture, feed=feed)

    async def _fetch_html(self, url: str) -> tuple[str, str, int, dict[str, str], str, dict[str, str]]:
        final_url = url
        body_text = ""
        status_code = 0
        headers: dict[str, str] = {}
        render_mode = "http"
        browser_status: dict[str, str] = {"status": "skipped", "reason": "not_needed"}
        try:
            async with create_async_client(timeout=30, follow_redirects=True) as client:
                response = await client.get(url)
                response.raise_for_status()
            final_url = str(response.url)
            body_text = response.text
            status_code = response.status_code
            headers = {k.lower(): v for k, v in response.headers.items()}
        except Exception as exc:
            rendered_html, rendered_url, browser_status = await GenericHtmlAdapter._render_with_browser(url)
            if not rendered_html:
                raise RuntimeError(f"zhihu fetch failed: {exc}") from exc
            final_url = rendered_url or final_url
            body_text = rendered_html
            status_code = 200
            render_mode = "browser"
        return final_url, body_text, status_code, headers, render_mode, browser_status

    @staticmethod
    def _extract_initial_state(html_text: str) -> dict | None:
        match = _INITIAL_DATA_RE.search(html_text or "")
        if not match:
            return None
        raw = (match.group(1) or "").strip()
        if not raw:
            return None
        try:
            return json.loads(unescape(raw))
        except json.JSONDecodeError:
            return None

    @staticmethod
    def _extract_ids(url: str) -> tuple[str | None, str | None]:
        path = urlparse(url).path or ""
        match = re.search(r"^/question/(\d+)(?:/answer/(\d+))?", path)
        if not match:
            return None, None
        return match.group(1), match.group(2)

    async def _build_from_state(
        self,
        state: dict | None,
        question_id: str | None,
        answer_id: str | None,
    ) -> tuple[str, str | None, str | None, datetime | None, dict]:
        entities = (((state or {}).get("initialState") or {}).get("entities")) or {}
        questions = entities.get("questions") or {}
        answers = entities.get("answers") or {}

        if answer_id:
            answer = answers.get(answer_id) or answers.get(str(answer_id))
            if not isinstance(answer, dict):
                return "", None, None, None, {"content_type": "answer", "parse_state": "answer_not_found"}
            question = answer.get("question") or {}
            question_title = (question.get("title") or "").strip()
            answer_text = self._html_to_text(answer.get("content") or "") or (answer.get("excerpt") or "").strip()
            lines = []
            if question_title:
                lines.append(f"问题：{question_title}")
            lines.append("回答：")
            lines.append(answer_text)
            body = "\n\n".join(line for line in lines if line).strip()
            author = ((answer.get("author") or {}).get("name") or "").strip() or None
            published_at = self._parse_epoch(answer.get("updatedTime") or answer.get("createdTime"))
            metadata = {
                "content_type": "answer",
                "question_id": question.get("id") or question_id,
                "answer_id": answer.get("id") or answer_id,
                "voteup_count": answer.get("voteupCount"),
                "comment_count": answer.get("commentCount"),
            }
            return body, question_title or None, author, published_at, metadata

        question = questions.get(question_id or "") or questions.get(str(question_id or ""))
        if not isinstance(question, dict):
            return "", None, None, None, {"content_type": "question", "parse_state": "question_not_found"}

        qid = str(question.get("id") or question_id or "")
        top_answers = [
            item
            for item in answers.values()
            if isinstance(item, dict) and str(((item.get("question") or {}).get("id") or "")) == qid
        ]
        top_answers.sort(key=lambda item: int(item.get("voteupCount") or 0), reverse=True)
        top_answers = top_answers[:5]

        question_title = (question.get("title") or "").strip() or None
        question_desc = self._html_to_text(question.get("detail") or "") or self._html_to_text(question.get("excerpt") or "")
        sections: list[str] = []
        if question_title:
            sections.append(f"问题：{question_title}")
        if question_desc:
            sections.append(f"问题描述：\n{question_desc}")
        if top_answers:
            answer_blocks: list[str] = []
            completed_count = 0
            for idx, item in enumerate(top_answers, start=1):
                text = self._html_to_text(item.get("content") or "") or (item.get("excerpt") or "").strip()
                answer_id_value = str(item.get("id") or "").strip()
                if self._needs_answer_completion(text) and answer_id_value and qid:
                    completed = await self._fetch_answer_full_content(qid, answer_id_value)
                    if completed:
                        text = completed
                        completed_count += 1
                if not text:
                    continue
                author = ((item.get("author") or {}).get("name") or "匿名用户").strip()
                votes = int(item.get("voteupCount") or 0)
                answer_blocks.append(f"{idx}. {author}（赞同 {votes}）\n{text}")
            if answer_blocks:
                sections.append("高赞回答：\n" + "\n\n".join(answer_blocks))
        else:
            completed_count = 0
        body = "\n\n".join(part for part in sections if part).strip()
        published_at = self._parse_epoch(question.get("updatedTime") or question.get("created"))
        metadata = {
            "content_type": "question",
            "question_id": qid or question_id,
            "answer_count": question.get("answerCount"),
            "follower_count": question.get("followerCount"),
            "visit_count": question.get("visitCount"),
            "top_answers_count": len(top_answers),
            "completed_answers_count": completed_count,
        }
        return body, question_title, None, published_at, metadata

    async def _fetch_answer_full_content(self, question_id: str, answer_id: str) -> str:
        answer_url = f"https://www.zhihu.com/question/{question_id}/answer/{answer_id}"
        try:
            _, html_text, _, _, _, _ = await self._fetch_html(answer_url)
        except Exception:
            return ""
        state = self._extract_initial_state(html_text)
        entities = (((state or {}).get("initialState") or {}).get("entities")) or {}
        answers = entities.get("answers") or {}
        answer = answers.get(answer_id) or answers.get(str(answer_id))
        if not isinstance(answer, dict):
            return ""
        text = self._html_to_text(answer.get("content") or "")
        if not text:
            text = (answer.get("excerpt") or "").strip()
        return text

    @staticmethod
    def _needs_answer_completion(text: str) -> bool:
        normalized = (text or "").strip()
        if not normalized:
            return True
        if "阅读全文" in normalized:
            return True
        return len(normalized) < 220

    @staticmethod
    def _extract_fallback_body(tree: html.HtmlElement) -> str:
        candidates = tree.xpath("//main") or tree.xpath("//article") or tree.xpath("//body")
        if not candidates:
            return ""
        text = candidates[0].text_content()
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        return text.strip()[:60000]

    @staticmethod
    def _html_to_text(raw_html: str) -> str:
        if not raw_html:
            return ""
        try:
            node = html.fromstring(f"<div>{raw_html}</div>")
            text = node.text_content()
        except Exception:
            text = raw_html
        text = text.replace("\u00a0", " ")
        text = re.sub(r"\n\s*\n+", "\n\n", text)
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines if line).strip()

    @staticmethod
    def _first_text(tree: html.HtmlElement, xpaths: list[str]) -> str | None:
        for xpath in xpaths:
            values = tree.xpath(xpath)
            if not values:
                continue
            value = values[0]
            if isinstance(value, str):
                stripped = value.strip()
                if stripped:
                    return stripped
        return None

    @staticmethod
    def _parse_epoch(value: object) -> datetime | None:
        if not isinstance(value, (int, float)):
            return None
        ts = float(value)
        if ts > 1_000_000_000_000:
            ts = ts / 1000
        if ts <= 0:
            return None
        return datetime.fromtimestamp(ts, tz=timezone.utc)
