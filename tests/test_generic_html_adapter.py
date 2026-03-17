from onefetch.adapters.generic_html import GenericHtmlAdapter


def test_browser_fallback_heuristics_short_content() -> None:
    assert GenericHtmlAdapter._needs_browser_fallback("short", "<html><body>x</body></html>") is True


def test_browser_fallback_heuristics_js_hint() -> None:
    html_text = "<html><body>Please enable JavaScript to continue.</body></html>"
    assert GenericHtmlAdapter._needs_browser_fallback("", html_text) is True


def test_browser_fallback_heuristics_normal_page() -> None:
    content = "A" * 500
    html_text = "<html><body>" + ("x" * 3000) + "</body></html>"
    assert GenericHtmlAdapter._needs_browser_fallback(content, html_text) is False
