from onefetch.cookie_formats import CookieFormatError, parse_cookie_input


def test_parse_header_string() -> None:
    parsed = parse_cookie_input("a=1; b=2")
    assert parsed.header == "a=1; b=2"


def test_parse_netscape_with_domain_hint() -> None:
    raw = """# Netscape HTTP Cookie File
.b.geekbang.org\tTRUE\t/\tFALSE\t2147483647\tSESSDATA\tabc
.b.geekbang.org\tTRUE\t/\tFALSE\t2147483647\tbid\txyz
"""
    parsed = parse_cookie_input(raw, domain_hint="b.geekbang.org")
    assert parsed.inferred_domain == "b.geekbang.org"
    assert "SESSDATA=abc" in parsed.header
    assert "bid=xyz" in parsed.header


def test_parse_netscape_infer_single_domain() -> None:
    raw = """.zhihu.com\tTRUE\t/\tFALSE\t2147483647\tz_c0\tabc
"""
    parsed = parse_cookie_input(raw)
    assert parsed.inferred_domain == "zhihu.com"
    assert parsed.header == "z_c0=abc"


def test_parse_netscape_multiple_domains_requires_hint() -> None:
    raw = """.zhihu.com\tTRUE\t/\tFALSE\t2147483647\tz_c0\tabc
.bilibili.com\tTRUE\t/\tFALSE\t2147483647\tSESSDATA\txyz
"""
    try:
        parse_cookie_input(raw)
    except CookieFormatError as exc:
        assert "multiple domains" in str(exc)
    else:
        raise AssertionError("expected CookieFormatError")
