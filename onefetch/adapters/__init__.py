from onefetch.adapters.generic_html import GenericHtmlAdapter
from onefetch.adapters.zhihu import ZhihuAdapter
from onefetch.adapters.wechat import WechatAdapter
from onefetch.adapters.xiaohongshu import XiaohongshuAdapter
from onefetch.adapters.base import BaseAdapter


def create_default_adapters() -> list[BaseAdapter]:
    return BaseAdapter.build_registered_instances()


__all__ = [
    "BaseAdapter",
    "GenericHtmlAdapter",
    "ZhihuAdapter",
    "WechatAdapter",
    "XiaohongshuAdapter",
    "create_default_adapters",
]
