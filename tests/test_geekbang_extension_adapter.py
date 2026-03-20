import importlib.util
import asyncio
from pathlib import Path

from lxml import html
from onefetch.adapters.base import BaseAdapter
from onefetch.models import FeedEntry


def _load_adapter_module():
    adapter_file = Path(__file__).resolve().parents[1] / ".onefetch" / "extensions" / "geekbang" / "adapter.py"
    BaseAdapter._registry.pop("geekbang", None)
    spec = importlib.util.spec_from_file_location("test_geekbang_adapter_ext", adapter_file)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    BaseAdapter._registry.pop("geekbang", None)
    return module


def test_geekbang_filters_decorative_images_and_keeps_body_markers() -> None:
    module = _load_adapter_module()
    body = "\n".join(
        [
            "段落A",
            "[IMG:1]",
            "[IMG_CAPTION:1] 头图",
            "[IMG:2]",
            "[IMG_CAPTION:2] 核心示意图",
            "[IMG:3]",
            "[IMG_CAPTION:3] 评论区占位图",
        ]
    )
    images = [
        "https://static001.geekbang.org/static/service/member.b/img/logo-normal.6001dff2.png",
        "https://static001.geekbang.org/resource/image/71/ba/714f8a37662a4856650118a26e5857ba.jpg",
        "https://static001.geekbang.org/static/service/member.b/img/empty-comment.1b74cb30.png",
    ]
    out_body, out_images = module.GeekbangAdapter._filter_images_and_markers(body, images)
    assert out_images == [images[1]]
    assert "[IMG:1]" in out_body
    assert "[IMG_CAPTION:1] 核心示意图" in out_body
    assert "[IMG:2]" not in out_body
    assert "[IMG:3]" not in out_body


def test_geekbang_extract_rich_body_wraps_code_block_with_fences() -> None:
    module = _load_adapter_module()
    tree = html.fromstring(
        """
        <div class="ProseMirror">
          <p>代码示例：</p>
          <pre data-language="python"><code>def add(a, b):
    return a + b
</code></pre>
          <p>结束。</p>
        </div>
        """
    )
    body, images = module.GeekbangAdapter._extract_rich_body(tree)
    assert images == []
    assert "```python" in body
    assert "def add(a, b):" in body
    assert "return a + b" in body
    assert "```" in body


def test_geekbang_extract_rich_body_preserves_list_markdown_lines() -> None:
    module = _load_adapter_module()
    tree = html.fromstring(
        """
        <div class="ProseMirror">
          <ul>
            <li>第一项</li>
            <li>第二项</li>
          </ul>
          <ol>
            <li>步骤一</li>
            <li>步骤二</li>
          </ol>
        </div>
        """
    )
    body, _ = module.GeekbangAdapter._extract_rich_body(tree)
    assert "- 第一项" in body
    assert "- 第二项" in body
    assert "1. 步骤一" in body
    assert "2. 步骤二" in body


def test_geekbang_extract_rich_body_does_not_insert_double_blank_between_every_block() -> None:
    module = _load_adapter_module()
    tree = html.fromstring(
        """
        <div class="ProseMirror">
          <p>段落A</p>
          <p>段落B</p>
          <p>段落C</p>
        </div>
        """
    )
    body, _ = module.GeekbangAdapter._extract_rich_body(tree)
    assert "\n\n" not in body
    assert body.splitlines() == ["段落A", "段落B", "段落C"]


def test_geekbang_extract_rich_body_reflows_compact_code_like_plain_text_block() -> None:
    module = _load_adapter_module()
    tree = html.fromstring(
        """
        <div class="ProseMirror">
          <p>def a(): pass def b(): pass def c(): pass if __name__ == "__main__": print("x"); print("y"); print("z"); print("u"); print("v"); print("w"); print("i"); print("j"); print("k"); print("l"); print("m"); print("n")</p>
        </div>
        """
    )
    body, _ = module.GeekbangAdapter._extract_rich_body(tree)
    assert body.startswith("```")
    assert "\ndef a():" in body
    assert "\ndef b():" in body
    assert body.endswith("```")


def test_geekbang_cleanup_body_keeps_code_indentation() -> None:
    module = _load_adapter_module()
    raw = "\n".join(
        [
            "前文",
            "```python",
            "def f():",
            "    return 1",
            "```",
            "问好",
            "后文",
        ]
    )
    out = module.GeekbangAdapter._cleanup_body(raw)
    assert "问好" not in out
    assert "```python" in out
    assert "    return 1" in out


def test_geekbang_extract_code_block_reflows_compact_js_line() -> None:
    module = _load_adapter_module()
    tree = html.fromstring(
        """
        <pre data-language="javascript"><code>function run(){const x=1;const y=2;if(x&lt;y){console.log("ok");}else{console.log("bad");}return x+y;} function end(){return 0;}</code></pre>
        """
    )
    out = module.GeekbangAdapter._extract_code_block(tree)
    assert out.startswith("```javascript\n")
    assert "\n    const x=1;" in out
    assert "\n    if(x<y){" in out
    assert "\n        console.log(\"ok\");" in out
    assert "\n    }" in out
    assert out.endswith("\n```")


def test_geekbang_extract_code_block_keeps_short_plain_text_line() -> None:
    module = _load_adapter_module()
    tree = html.fromstring("<pre><code>just a short line without code symbols</code></pre>")
    out = module.GeekbangAdapter._extract_code_block(tree)
    assert "just a short line without code symbols" in out
    assert out.count("\n") <= 3


def test_geekbang_extract_code_block_reflows_compact_python_style_line() -> None:
    module = _load_adapter_module()
    tree = html.fromstring(
        """
        <pre><code>def a(): pass def b(): pass def c(): pass if __name__ == "__main__": print("x"); print("y"); print("z"); print("u"); print("v"); print("w")</code></pre>
        """
    )
    out = module.GeekbangAdapter._extract_code_block(tree)
    assert "```" in out
    assert "\ndef a():" in out
    assert "\ndef b():" in out
    assert "\ndef c():" in out


def test_geekbang_crawl_overrides_fallback_images_when_specialized_parse_succeeds() -> None:
    module = _load_adapter_module()

    class FakeGenericHtmlAdapter:
        async def crawl(self, url: str) -> FeedEntry:
            html_text = """
            <html>
              <body>
                <div class="ArticleContent_audio-course-wrapper">
                  <h1 class="ArticleContent_title">标题</h1>
                  <div class="ArticleContent_desc">作者</div>
                  <div class="ProseMirror">
                    <p>正文段落</p>
                  </div>
                </div>
              </body>
            </html>
            """
            return FeedEntry(
                source_url=url,
                canonical_url=url,
                crawler_id="generic_html",
                title="fallback-title",
                body="fallback-body",
                raw_body=html_text,
                images=["https://static001.geekbang.org/static/service/member.b/img/logo-normal.6001dff2.png"],
            )

    old = module.GenericHtmlAdapter
    module.GenericHtmlAdapter = FakeGenericHtmlAdapter
    try:
        result = asyncio.run(module.GeekbangAdapter().crawl("https://b.geekbang.org/member/course/detail/123"))
    finally:
        module.GenericHtmlAdapter = old

    assert result.crawler_id == "geekbang"
    assert result.title == "标题"
    assert result.images == []
