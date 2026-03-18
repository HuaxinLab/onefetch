from onefetch.adapters import create_default_adapters


def test_create_default_adapters_returns_expected_order() -> None:
    adapters = create_default_adapters()
    ids = [adapter.id for adapter in adapters]
    assert ids == ["xiaohongshu", "bilibili", "wechat", "zhihu", "generic_html"]
