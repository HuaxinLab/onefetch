from datetime import datetime, timezone

import pytest

from onefetch.adapters.xiaohongshu import XiaohongshuAdapter
from onefetch.secret_store import cookie_key, set_secret


def test_extract_note_data_from_initial_state() -> None:
    adapter = XiaohongshuAdapter()
    url = "https://www.xiaohongshu.com/explore/68075b1d000000001b03c4f0?foo=bar"
    html_text = """
    <html>
      <head>
        <meta property="og:url" content="https://www.xiaohongshu.com/explore/68075b1d000000001b03c4f0" />
        <meta property="og:title" content="OG Title - 小红书" />
      </head>
      <body>
        <script>
          window.__INITIAL_STATE__={"note":{"noteDetailMap":{"68075b1d000000001b03c4f0":{"comments":{"list":[]},"note":{"noteId":"68075b1d000000001b03c4f0","title":"Parsed Title","desc":"Parsed Description","time":1745312541000,"user":{"nickname":"小七麦"},"interactInfo":{"likedCount":"102","commentCount":"3","collectedCount":"83","shareCount":"134"}}}}}};
        </script>
      </body>
    </html>
    """

    state = adapter._extract_initial_state(html_text)
    title, author, body, published_at, metadata, comments = adapter._extract_from_html_and_state(html_text, url, state)

    assert title == "Parsed Title"
    assert author == "小七麦"
    assert "Parsed Description" in body
    assert published_at == datetime.fromtimestamp(1745312541000 / 1000, tz=timezone.utc)
    assert metadata["canonical_url"] == "https://www.xiaohongshu.com/explore/68075b1d000000001b03c4f0"
    assert metadata["note_id"] == "68075b1d000000001b03c4f0"
    assert metadata["interact_info"]["liked_count"] == "102"
    assert comments == []


def test_extract_note_id_for_discovery_item() -> None:
    adapter = XiaohongshuAdapter()
    note_id = adapter._extract_note_id("https://www.xiaohongshu.com/discovery/item/69b81c12000000002103afee?x=1")
    assert note_id == "69b81c12000000002103afee"


def test_risk_signal_detection() -> None:
    assert XiaohongshuAdapter._is_risk_signal(http_status=461, api_code=None) is True
    assert XiaohongshuAdapter._is_risk_signal(http_status=200, api_code=300011) is True
    assert XiaohongshuAdapter._is_risk_signal(http_status=200, api_code=0) is False


class _FakeResponse:
    def __init__(self, payload: dict, status_code: int = 200) -> None:
        self._payload = payload
        self.status_code = status_code

    def json(self) -> dict:
        return self._payload


class _FakeClient:
    def __init__(self, responses: list[_FakeResponse]) -> None:
        self._responses = responses
        self.calls = 0

    async def get(self, url: str):  # noqa: ANN001
        response = self._responses[min(self.calls, len(self._responses) - 1)]
        self.calls += 1
        return response


class _FakeClientContext:
    def __init__(self, client: _FakeClient) -> None:
        self.client = client

    async def __aenter__(self) -> _FakeClient:
        return self.client

    async def __aexit__(self, exc_type, exc, tb) -> None:  # noqa: ANN001
        return None


async def test_fetch_comments_pagination_and_dedup(monkeypatch: pytest.MonkeyPatch, tmp_path) -> None:
    adapter = XiaohongshuAdapter()
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")
    set_secret(cookie_key("xiaohongshu.com"), "session=ok")
    monkeypatch.setenv("ONEFETCH_XHS_COMMENT_MAX_PAGES", "5")
    monkeypatch.setenv("ONEFETCH_XHS_COMMENT_MAX_ITEMS", "50")

    page1 = _FakeResponse(
        {
            "success": True,
            "data": {
                "comments": [
                    {
                        "content": "A",
                        "user_info": {"nickname": "u1"},
                        "sub_comments": [
                            {"content": "A-1", "user_info": {"nickname": "u1r"}},
                        ],
                    },
                    {"content": "B", "user_info": {"nickname": "u2"}},
                ],
                "has_more": True,
                "cursor": "c1",
            },
        }
    )
    page2 = _FakeResponse(
        {
            "success": True,
            "data": {
                "comments": [
                    {"content": "B", "user_info": {"nickname": "u2"}},  # duplicate
                    {"content": "C", "user_info": {"nickname": "u3"}},
                ],
                "has_more": False,
                "cursor": "c2",
            },
        }
    )
    fake_client = _FakeClient([page1, page2])

    def fake_create_async_client(**kwargs):  # noqa: ANN003
        return _FakeClientContext(fake_client)

    monkeypatch.setattr("onefetch.adapters.xiaohongshu.create_async_client", fake_create_async_client)
    comments, status = await adapter._fetch_comments(
        "68075b1d000000001b03c4f0",
        canonical_url="https://www.xiaohongshu.com/explore/68075b1d000000001b03c4f0",
    )

    assert [item.text for item in comments] == ["A", "↳ A-1", "B", "C"]
    assert status["status"] == "ok"
    assert status["count"] == 4
    assert status["pages_fetched"] == 2
    assert status["has_more"] is False
