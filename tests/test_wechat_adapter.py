from lxml import html

from onefetch.adapters.wechat import WechatAdapter


SAMPLE = """
<html>
  <head><title>示例标题 - 微信公众平台</title></head>
  <body>
    <h1 id='activity-name'>这是公众号标题</h1>
    <span id='js_name'>OneFetch Lab</span>
    <em id='publish_time'>2026-03-17</em>
    <div id='js_content'>
      <p>第一段内容</p>
      <script>var noisy = 'should be removed';</script>
      <p>第二段内容</p>
      <p>阅读 1200</p>
      <p>写留言</p>
    </div>
  </body>
</html>
"""


def test_extract_article_cleans_script_noise() -> None:
    tree = html.fromstring(SAMPLE)
    title, author, published, content, cleanup = WechatAdapter._extract_article(tree, SAMPLE)

    assert title == "这是公众号标题"
    assert author == "OneFetch Lab"
    assert published is not None
    assert "第一段内容" in content
    assert "第二段内容" in content
    assert "should be removed" not in content
    assert "写留言" not in content
    assert cleanup["removed_lines"] >= 1


def test_supports_mp_weixin_domain() -> None:
    adapter = WechatAdapter()
    assert adapter.supports("https://mp.weixin.qq.com/s/abc") is True
    assert adapter.supports("https://weixin.qq.com/") is False
