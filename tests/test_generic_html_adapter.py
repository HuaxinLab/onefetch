import pytest

from onefetch.adapters.generic_html import GenericHtmlAdapter
from lxml import html


def test_browser_fallback_heuristics_short_content() -> None:
    assert GenericHtmlAdapter._needs_browser_fallback("short", "<html><body>x</body></html>") is True


def test_browser_fallback_heuristics_js_hint() -> None:
    html_text = "<html><body>Please enable JavaScript to continue.</body></html>"
    assert GenericHtmlAdapter._needs_browser_fallback("", html_text) is True


def test_browser_fallback_heuristics_normal_page() -> None:
    content = "A" * 500
    html_text = "<html><body>" + ("x" * 3000) + "</body></html>"
    assert GenericHtmlAdapter._needs_browser_fallback(content, html_text) is False


def test_extract_main_text_keeps_heading_and_code_fences() -> None:
    tree = html.fromstring(
        """
        <html><body><article>
          <h2>Section Title</h2>
          <p>before</p>
          <pre><code class="language-python">print("ok")</code></pre>
        </article></body></html>
        """
    )
    text, _images = GenericHtmlAdapter._extract_main_text(tree)
    assert "### Section Title" in text
    assert "```python" in text
    assert 'print("ok")' in text
    assert "```" in text


def test_extract_main_text_keeps_list_and_link_markdown() -> None:
    tree = html.fromstring(
        """
        <html><body><article>
          <ul><li>alpha</li><li>beta</li></ul>
          <ol><li>step one</li><li>step two</li></ol>
          <p>go to <a href="https://example.com/docs">docs</a></p>
        </article></body></html>
        """
    )
    text, _images = GenericHtmlAdapter._extract_main_text(tree)
    assert "- alpha" in text
    assert "- beta" in text
    assert "1. step one" in text
    assert "2. step two" in text
    assert "[docs](https://example.com/docs)" in text


def test_extract_main_text_keeps_table_and_image_placeholder() -> None:
    tree = html.fromstring(
        """
        <html><body><article>
          <table>
            <tr><th>Name</th><th>Value</th></tr>
            <tr><td>A</td><td>1</td></tr>
          </table>
          <p><img src="https://img.example.com/a.png" alt="a" /></p>
        </article></body></html>
        """
    )
    text, images = GenericHtmlAdapter._extract_main_text(tree)
    assert "| Name | Value |" in text
    assert "| --- | --- |" in text
    assert "| A | 1 |" in text
    assert "[IMG:1]" in text
    assert images == ["https://img.example.com/a.png"]


async def test_cookie_required_path_retries_browser_before_raising(monkeypatch) -> None:
    http_html = """
    <html><body>
      <main>
        <p>{text}</p>
      </main>
      <div>log in to continue</div>
    </body></html>
    """.format(text=("A" * 220))
    browser_html = """
    <html><body>
      <article>
        <h1>Public Post</h1>
        <p>This is readable content from browser rendering.</p>
      </article>
    </body></html>
    """

    class _Resp:
        def __init__(self, text: str) -> None:
            self.text = text
            self.url = "https://example.com/post"
            self.status_code = 200
            self.headers = {"content-type": "text/html"}

        def raise_for_status(self) -> None:
            return None

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, _url: str):
            return _Resp(http_html)

    async def _fake_render(_url: str, *, cookie: str = ""):
        return browser_html, "https://example.com/post", {"status": "ok", "load_mode": "networkidle"}

    monkeypatch.setattr("onefetch.adapters.generic_html.create_async_client", lambda **_: _Client())
    monkeypatch.setattr(GenericHtmlAdapter, "_render_with_browser", staticmethod(_fake_render))

    feed = await GenericHtmlAdapter().crawl("https://example.com/post")

    assert "Public Post" in feed.body
    assert "readable content from browser rendering" in feed.body
    assert feed.metadata["render_mode"] == "browser"


def test_x_shell_detection_markers() -> None:
    assert GenericHtmlAdapter._looks_like_x_shell(
        content="Something went wrong, but don’t fret — let’s give it another shot.",
        body_text="",
        title="X",
    )
    assert GenericHtmlAdapter._looks_like_x_shell(
        content="Don’t miss what’s happening\nPeople on X are the first to know.\nLog in Sign up",
        body_text="",
        title="X",
    )


def test_reader_markdown_extraction_filters_login_wall() -> None:
    text = """Title: X
Markdown Content:
Don’t miss what’s happening

People on X are the first to know.
"""
    assert GenericHtmlAdapter._extract_reader_markdown(text) == ""


async def test_fetch_x_fallback_from_oembed_tco_and_reader(monkeypatch) -> None:
    oembed_json = {
        "html": (
            '<blockquote class="twitter-tweet"><p><a href="https://t.co/abc123">'
            "https://t.co/abc123</a></p></blockquote>"
        )
    }
    reader_text = """Title: X
Markdown Content:
Recovered longform body from reader fallback.
"""

    class _Resp:
        def __init__(self, *, text: str = "", json_data=None, url: str = "") -> None:
            self._text = text
            self._json_data = json_data
            self.url = url

        @property
        def text(self) -> str:
            return self._text

        def json(self):
            return self._json_data

        def raise_for_status(self) -> None:
            return None

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def get(self, url: str):
            if "publish.twitter.com/oembed" in url:
                return _Resp(json_data=oembed_json)
            if url == "https://t.co/abc123":
                return _Resp(url="https://x.com/i/article/999")
            if "r.jina.ai/http://x.com/i/article/999" in url:
                return _Resp(text=reader_text)
            return _Resp(text="")

    monkeypatch.setattr("onefetch.adapters.generic_html.create_async_client", lambda **_: _Client())
    got = await GenericHtmlAdapter()._fetch_x_fallback("https://x.com/user/status/1")
    assert "Recovered longform body" in got
