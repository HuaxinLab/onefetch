from onefetch import cli


def test_ingest_present_mode_outputs_block(capsys) -> None:
    exit_code = cli.main(["ingest", "https://example.com", "--present"])
    out = capsys.readouterr().out

    assert exit_code == 0
    assert "## Present" in out
    assert "### Item 1" in out
