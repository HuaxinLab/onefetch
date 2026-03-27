from pathlib import Path

from onefetch.secret_cli import canonical_cookie_domain, import_cookie_files, import_cookie_from_env, normalize_cookie_keys
from onefetch.secret_store import get_secret, list_secret_keys, set_secret


def test_import_cookies_from_file_infer_domain(monkeypatch, tmp_path) -> None:
    path = tmp_path / "zhihu.com_cookie.txt"
    path.write_text("z_c0=abc; d_c0=def")
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")

    count = import_cookie_files([str(path)])
    assert count == 1
    assert get_secret("cookie.zhihu.com") == "z_c0=abc; d_c0=def"


def test_import_cookies_from_explicit_dir(monkeypatch, tmp_path) -> None:
    path = tmp_path / "random_name.txt"
    path.write_text("SESSDATA=1;")

    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")

    count = import_cookie_files([str(Path(path))], domain_override="www.bilibili.com")
    assert count == 1
    assert get_secret("cookie.bilibili.com") == "SESSDATA=1;"


def test_import_cookies_supports_netscape(monkeypatch, tmp_path) -> None:
    path = tmp_path / "cookies.txt"
    path.write_text(
        ".b.geekbang.org\tTRUE\t/\tFALSE\t2147483647\tSESSDATA\tabc\n"
        ".b.geekbang.org\tTRUE\t/\tFALSE\t2147483647\tbid\txyz\n"
    )
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    count = import_cookie_files([str(path)], domain_override="b.geekbang.org")
    assert count == 1
    value = get_secret("cookie.b.geekbang.org") or ""
    assert "SESSDATA=abc" in value
    assert "bid=xyz" in value


def test_normalize_cookie_keys_merges_aliases(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")
    set_secret("cookie.zhihu", "v1")
    set_secret("cookie.zhihu.com", "v2")

    changed = normalize_cookie_keys()
    assert changed == 1
    assert get_secret("cookie.zhihu.com") == "v2"
    assert "cookie.zhihu" not in list_secret_keys(secret_type="cookie")


def test_canonical_cookie_domain() -> None:
    assert canonical_cookie_domain("www.zhihu.com") == "zhihu.com"
    assert canonical_cookie_domain("zhihu") == "zhihu.com"
    assert canonical_cookie_domain("doubao") == "doubao.com"
    assert canonical_cookie_domain("https://b.geekbang.org/member/course/intro/101123001") == "b.geekbang.org"


def test_import_cookie_from_env(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")
    monkeypatch.setenv("TEST_COOKIE_ENV", "sid=1; uid=2;")
    import_cookie_from_env("TEST_COOKIE_ENV", "zhihu.com")
    assert get_secret("cookie.zhihu.com") == "sid=1; uid=2;"
