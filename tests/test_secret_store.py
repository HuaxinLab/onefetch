from onefetch.secret_store import get_secret, set_secret


def test_set_and_get_secret_roundtrip(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")

    set_secret("cookie.zhihu.com", "z_c0=abc")
    assert get_secret("cookie.zhihu.com") == "z_c0=abc"


def test_auto_create_master_key_file_when_env_missing(monkeypatch, tmp_path) -> None:
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.delenv("ONEFETCH_MASTER_KEY", raising=False)
    key_file = tmp_path / "master.key"
    monkeypatch.setenv("ONEFETCH_MASTER_KEY_FILE", str(key_file))

    set_secret("cookie.zhihu.com", "x=1")
    assert get_secret("cookie.zhihu.com") == "x=1"
    assert key_file.is_file()
    assert key_file.read_text(encoding="utf-8").strip()
