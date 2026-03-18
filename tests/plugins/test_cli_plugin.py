from onefetch import cli


def test_plugin_list_command_outputs_builtin_plugins(capsys) -> None:
    exit_code = cli.main(["plugin", "list"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "extract_css_attr" in out
    assert "extract_html_js_jsonp" in out
    assert "extract_jsonp_field" in out


def test_plugin_list_with_presets_includes_names(capsys) -> None:
    exit_code = cli.main(["plugin", "list", "--with-presets"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "presets:" in out
    assert "chain_cdn_js_jsonp_img" in out


def test_plugin_presets_list_json(capsys) -> None:
    exit_code = cli.main(["plugin", "presets", "--plugin-id", "extract_html_js_jsonp", "--json"])
    out = capsys.readouterr().out
    assert exit_code == 0
    assert "chain_cdn_js_jsonp_img" in out


def test_plugin_run_css_with_inline_html(capsys) -> None:
    exit_code = cli.main(
        [
            "plugin",
            "run",
            "extract_css_attr",
            "--opt",
            "selector=.wk-hero-invite-col",
            "--opt",
            "attr=text",
            "--opt",
            "html=<div class='wk-hero-invite-col'>ok</div>",
        ]
    )
    out = capsys.readouterr().out.strip()

    assert exit_code == 0
    assert out == "ok"


def test_plugin_run_rejects_bad_opt_format(capsys) -> None:
    exit_code = cli.main(["plugin", "run", "extract_css_attr", "--opt", "selector"])
    out = capsys.readouterr().out

    assert exit_code == 2
    assert "expected key=value" in out


def test_plugin_run_with_preset_merges_options(monkeypatch, capsys) -> None:
    monkeypatch.setattr(
        cli,
        "load_preset",
        lambda name, plugin_id: {"selector": ".wk-hero-invite-col", "attr": "text", "index": "0"},
    )
    exit_code = cli.main(
        [
            "plugin",
            "run",
            "extract_css_attr",
            "--opt",
            "preset=any_name",
            "--opt",
            "html=<div class='wk-hero-invite-col'>from-preset</div>",
        ]
    )
    out = capsys.readouterr().out.strip()
    assert exit_code == 0
    assert out == "from-preset"
