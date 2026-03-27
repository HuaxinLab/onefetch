from onefetch import cli
from onefetch.secret_store import set_secret


def test_secret_list_and_get_masked(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")
    set_secret("cookie.zhihu.com", "z_c0=abcdef")

    code = cli.main(["secret", "list", "--type", "cookie"])
    assert code == 0
    out = capsys.readouterr().out
    assert "cookie.zhihu.com" in out

    code = cli.main(["secret", "get", "cookie.zhihu.com"])
    assert code == 0
    out = capsys.readouterr().out
    assert "z_c" in out
    assert "len=" in out
    assert "abcdef" not in out


def test_secret_get_plain_and_delete(monkeypatch, tmp_path, capsys) -> None:
    monkeypatch.setenv("ONEFETCH_PROJECT_ROOT", str(tmp_path))
    monkeypatch.setenv("ONEFETCH_MASTER_KEY", "test-master-key")
    set_secret("cookie.douyin.com", "sessionid=xyz")

    code = cli.main(["secret", "get", "cookie.douyin.com", "--no-masked"])
    assert code == 0
    assert "sessionid=xyz" in capsys.readouterr().out

    code = cli.main(["secret", "delete", "cookie.douyin.com"])
    assert code == 0
    assert "deleted" in capsys.readouterr().out

    code = cli.main(["secret", "get", "cookie.douyin.com"])
    assert code == 1
    assert "not found" in capsys.readouterr().out
