from onefetch.plugins.presets import list_presets, load_preset


def test_load_builtin_preset_for_chain_plugin() -> None:
    options = load_preset("template_html_js_jsonp", plugin_id="extract_html_js_jsonp")
    assert options["callback"] == "callback"
    assert options["field"] == "value"


def test_load_preset_rejects_wrong_plugin_id() -> None:
    try:
        load_preset("template_html_js_jsonp", plugin_id="extract_css_attr")
    except ValueError as exc:
        assert "is for plugin" in str(exc)
    else:
        raise AssertionError("expected ValueError for mismatched plugin")


def test_local_preset_overrides_builtin(monkeypatch, tmp_path) -> None:
    secrets_dir = tmp_path / ".secrets" / "plugin_presets"
    secrets_dir.mkdir(parents=True, exist_ok=True)
    (secrets_dir / "template_html_js_jsonp.json").write_text(
        '{"plugin_id":"extract_html_js_jsonp","options":{"callback":"local_cb","field":"local_field"}}',
        encoding="utf-8",
    )
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    options = load_preset("template_html_js_jsonp", plugin_id="extract_html_js_jsonp")
    assert options["callback"] == "local_cb"
    assert options["field"] == "local_field"


def test_list_presets_contains_builtin_chain() -> None:
    rows = list_presets(plugin_id="extract_html_js_jsonp")
    names = {row["name"] for row in rows}
    assert "chain_cdn_js_jsonp_img" in names
