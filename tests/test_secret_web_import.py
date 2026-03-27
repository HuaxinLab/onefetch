from onefetch.secret_web_import import canonical_cookie_domain, generate_code


def test_canonical_cookie_domain() -> None:
    assert canonical_cookie_domain("www.zhihu.com") == "zhihu.com"
    assert canonical_cookie_domain("douyin") == "douyin.com"
    assert canonical_cookie_domain("https://b.geekbang.org/member/course/intro/101123001") == "b.geekbang.org"


def test_generate_code() -> None:
    code = generate_code()
    assert isinstance(code, str)
    assert len(code) >= 8
