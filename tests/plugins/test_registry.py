from onefetch.plugins import PluginTask, create_default_registry


def test_default_registry_contains_expected_plugins() -> None:
    registry = create_default_registry()
    plugin_ids = [plugin.id for plugin in registry.list_plugins()]
    assert "extract_css_attr" in plugin_ids
    assert "extract_jsonp_field" in plugin_ids


def test_extract_css_attr_plugin_with_inline_html() -> None:
    registry = create_default_registry()
    task = PluginTask(
        plugin_id="extract_css_attr",
        options={
            "selector": ".wk-hero-invite-col",
            "attr": "text",
            "html": "<div class='wk-hero-invite-col'>hello</div>",
        },
    )
    result = registry.run(task)
    assert result.ok is True
    assert result.value == "hello"


def test_extract_jsonp_field_plugin_with_inline_body() -> None:
    registry = create_default_registry()
    task = PluginTask(
        plugin_id="extract_jsonp_field",
        options={
            "callback": "img_url",
            "field": "img_url",
            "jsonp_body": 'img_url({"img_url":"https://example.com/a.png"})',
        },
    )
    result = registry.run(task)
    assert result.ok is True
    assert result.value == "https://example.com/a.png"
