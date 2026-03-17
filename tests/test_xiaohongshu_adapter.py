from datetime import datetime, timezone

from onefetch.adapters.xiaohongshu import XiaohongshuAdapter


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
