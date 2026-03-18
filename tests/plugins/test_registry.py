from onefetch.plugins import PluginTask, create_default_registry


def test_default_registry_contains_expected_plugins() -> None:
    registry = create_default_registry()
    plugin_ids = [plugin.id for plugin in registry.list_plugins()]
    assert "extract_css_attr" in plugin_ids
    assert "extract_html_js_jsonp" in plugin_ids
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


def test_extract_html_js_jsonp_chain_with_inline_inputs() -> None:
    registry = create_default_registry()
    html = '<script src="//cdn.dingtalkapps.com/dingding/wukong_office_network/0.2.10/wukong/abc.js"></script>'
    js = (
        'var x="https://hudong.alicdn.com/api/data/v2/438eae9715f945468d599660d2d92aeb.js?t=";'
        'var b={imageUrl:"https://fallback.example.com/default.png",version:"8"};'
    )
    jsonp = 'img_url({"img_url":"https://example.com/live.png"})'
    task = PluginTask(
        plugin_id="extract_html_js_jsonp",
        options={
            "html": html,
            "js_body": js,
            "jsonp_body": jsonp,
            "callback": "img_url",
            "field": "img_url",
            "append_version": "true",
            "ts": "123",
        },
    )
    result = registry.run(task)
    assert result.ok is True
    assert result.value == "https://example.com/live.png?v=8"
    assert isinstance(result.meta.get("steps"), list)
    assert result.meta.get("selected", {}).get("fallback_used") is False


def test_extract_html_js_jsonp_supports_multiple_patterns() -> None:
    registry = create_default_registry()
    html = '<script src="//cdn.dingtalkapps.com/dingding/wukong_office_network/0.2.10/wukong/abc.js"></script>'
    js = (
        'var x="https://hudong.alicdn.com/api/data/v2/438eae9715f945468d599660d2d92aeb.js?t=";'
        'var b={imageUrl:"https://fallback.example.com/default.png",version:"8"};'
    )
    task = PluginTask(
        plugin_id="extract_html_js_jsonp",
        options={
            "html": html,
            "js_body": js,
            "js_url_regexes": ["(https?://none.invalid/abc.js)", "(https?:)?//cdn\\.dingtalkapps\\.com/dingding/wukong_office_network/[^\"\\\\]+/wukong/[^\"\\\\]+\\.js"],
            "jsonp_base_regexes": ["(https://none.invalid/api.js?t=)", "(https://hudong\\.alicdn\\.com/api/data/v2/[^\"\\\\]+\\.js\\?t=)"],
            "jsonp_body": 'img_url({"img_url":"https://example.com/live.png"})',
            "callback": "img_url",
            "field": "img_url",
            "append_version": "true",
        },
    )
    result = registry.run(task)
    assert result.ok is True
    assert result.value == "https://example.com/live.png?v=8"
    steps = result.meta.get("steps", [])
    js_match_steps = [step for step in steps if step.get("step") == "match_js_url"]
    assert len(js_match_steps) >= 2


def test_extract_html_js_jsonp_auto_detect_callback_and_field() -> None:
    registry = create_default_registry()
    task = PluginTask(
        plugin_id="extract_html_js_jsonp",
        options={
            "html": "<html></html>",
            "js_body": 'var a="https://api.example.com/data/payload.js?t=";',
            "jsonp_body": 'mycb({"download_url":"https://example.com/app.pkg"})',
            "auto_detect": "true",
        },
    )
    result = registry.run(task)
    assert result.ok is True
    assert result.value == "https://example.com/app.pkg"
    assert result.meta.get("selected", {}).get("selected_callback") == "mycb"
    assert result.meta.get("selected", {}).get("selected_field") == "download_url"


def test_extract_html_js_jsonp_returns_error_code_and_suggestion() -> None:
    registry = create_default_registry()
    task = PluginTask(plugin_id="extract_html_js_jsonp", options={})
    result = registry.run(task)
    assert result.ok is False
    assert result.meta.get("error_code") == "E_INPUT_MISSING"
    assert "Provide --url" in result.meta.get("suggestion", "")
