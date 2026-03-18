from onefetch.adapters.generic_html import GenericHtmlAdapter
from onefetch.adapters.zhihu import ZhihuAdapter
from onefetch.adapters.wechat import WechatAdapter
from onefetch.adapters.xiaohongshu import XiaohongshuAdapter
from onefetch.router import Router


def test_route_xiaohongshu_url_to_xhs_adapter() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), ZhihuAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://www.xiaohongshu.com/explore/123")
    assert adapter.id == "xiaohongshu"


def test_route_wechat_url_to_wechat_adapter() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), ZhihuAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://mp.weixin.qq.com/s/abc")
    assert adapter.id == "wechat"


def test_route_zhihu_url_to_zhihu_adapter() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), ZhihuAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://www.zhihu.com/question/610072126")
    assert adapter.id == "zhihu"


def test_route_zhihu_zhuanlan_url_to_zhihu_adapter() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), ZhihuAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://zhuanlan.zhihu.com/p/2016268919397196245")
    assert adapter.id == "zhihu"


def test_route_fallback_to_generic_html() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), ZhihuAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://example.com/article")
    assert adapter.id == "generic_html"


def test_route_forced_adapter() -> None:
    router = Router([XiaohongshuAdapter(), WechatAdapter(), ZhihuAdapter(), GenericHtmlAdapter()])
    adapter = router.route("https://example.com", forced_adapter="xiaohongshu")
    assert adapter.id == "xiaohongshu"
