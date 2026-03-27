from onefetch.adapters.generic_html import GenericHtmlAdapter
from onefetch.adapters.x import XAdapter
from onefetch.models import FeedEntry


async def test_x_adapter_uses_fallback_when_generic_raises(monkeypatch) -> None:
    async def _raise(_self, _url: str):
        raise RuntimeError("页面内容为空或需要登录才能查看。")

    async def _fallback(_self, _url: str):
        return "Recovered body"

    monkeypatch.setattr(GenericHtmlAdapter, "crawl", _raise)
    monkeypatch.setattr(XAdapter, "_fetch_x_fallback", _fallback)

    feed = await XAdapter().crawl("https://x.com/a/status/1")
    assert feed.crawler_id == "x"
    assert feed.title == "X post (fallback)"
    assert feed.body == "Recovered body"


async def test_x_adapter_prefers_generic_when_content_is_normal(monkeypatch) -> None:
    async def _ok(_self, url: str):
        return FeedEntry(
            source_url=url,
            canonical_url=url,
            crawler_id="generic_html",
            title="Normal",
            author=None,
            published_at=None,
            body="Readable post body",
            raw_body="Readable post body",
            images=[],
            metadata={},
        )

    monkeypatch.setattr(GenericHtmlAdapter, "crawl", _ok)
    feed = await XAdapter().crawl("https://x.com/a/status/1")
    assert feed.crawler_id == "generic_html"
    assert feed.body == "Readable post body"
