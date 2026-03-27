from onefetch.secret_store import cookie_key, set_secret
from onefetch.secrets import load_cookie


def test_load_cookie_prefers_store_over_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")
    set_secret(cookie_key("zhihu.com"), "from_store=1;")

    monkeypatch.setenv("ONEFETCH_COOKIE_ZHIHU_COM", "from_env=1;")
    cookie = load_cookie(domains=["zhihu.com"])
    assert cookie == "from_store=1;"


def test_load_cookie_from_store(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")
    set_secret(cookie_key("zhuanlan.zhihu.com"), "z_c0=abc")

    cookie = load_cookie(domains=["zhuanlan.zhihu.com"])
    assert cookie == "z_c0=abc"


def test_load_cookie_supports_short_site_env_name(monkeypatch) -> None:
    monkeypatch.setenv("ONEFETCH_ZHIHU_COOKIE", "z_c0=abc")
    cookie = load_cookie(domains=["zhuanlan.zhihu.com"])
    assert cookie == "z_c0=abc"
