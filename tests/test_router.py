from onefetch.adapters.generic_html import GenericHtmlAdapter
from onefetch.adapters.wechat import WechatAdapter
from onefetch.adapters.xiaohongshu import XiaohongshuAdapter
from onefetch.router import Router


def test_route_xiaohongshu_url_to_xhs_adapter() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://www.xiaohongshu.com/explore/123")
    assert adapter.id == "xiaohongshu"


def test_route_wechat_url_to_wechat_adapter() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://mp.weixin.qq.com/s/abc")
    assert adapter.id == "wechat"


def test_route_fallback_to_generic_html() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://example.com/article")
    assert adapter.id == "generic_html"


def test_route_forced_adapter() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://example.com", forced_adapter="xiaohongshu")
    assert adapter.id == "xiaohongshu"
