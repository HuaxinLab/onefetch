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

    title, author, body, published_at, metadata, comments = adapter._extract_from_html(html_text, url)

    assert title == "Parsed Title"
    assert author == "小七麦"
    assert body == "Parsed Description"
    assert published_at == datetime.fromtimestamp(1745312541000 / 1000, tz=timezone.utc)
    assert metadata["canonical_url"] == "https://www.xiaohongshu.com/explore/68075b1d000000001b03c4f0"
    assert metadata["note_id"] == "68075b1d000000001b03c4f0"
    assert metadata["interact_info"]["liked_count"] == "102"
    assert comments == []
