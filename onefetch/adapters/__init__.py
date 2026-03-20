from onefetch.adapters.bilibili import BilibiliAdapter
from onefetch.adapters.generic_html import GenericHtmlAdapter
from onefetch.adapters.zhihu import ZhihuAdapter
from onefetch.adapters.wechat import WechatAdapter
from onefetch.adapters.xiaohongshu import XiaohongshuAdapter
from onefetch.adapters.base import BaseAdapter


def create_default_adapters(project_root: str | None = None) -> list[BaseAdapter]:
    if project_root:
        try:
            from onefetch.extensions import import_installed_adapters

            import_installed_adapters(project_root)
        except Exception:
            # Extension loading is best-effort; core adapters must still work.
            pass
    return BaseAdapter.build_registered_instances()


__all__ = [
    "BaseAdapter",
    "BilibiliAdapter",
    "GenericHtmlAdapter",
    "ZhihuAdapter",
    "WechatAdapter",
    "XiaohongshuAdapter",
    "create_default_adapters",
]
