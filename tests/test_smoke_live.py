import json
import os

import pytest

from onefetch import cli


@pytest.mark.skipif(os.getenv("ONEFETCH_RUN_LIVE_SMOKE") != "1", reason="set ONEFETCH_RUN_LIVE_SMOKE=1 to run live smoke")
def test_live_smoke_three_platforms(capsys) -> None:
    urls = [
        "https://www.xiaohongshu.com/explore/690b20100000000007034688",
        "https://mp.weixin.qq.com/s/aqAxZD5m4bvGYMPVQkFQhg",
        "https://www.bestblogs.dev/article/55c83261",
    ]
    exit_code = cli.main(["ingest", *urls, "--json"])
    out = capsys.readouterr().out

    assert exit_code == 0
    payload = json.loads(out)
    assert payload["failed_count"] == 0

    by_url = {item["source_url"]: item for item in payload["results"]}
    assert by_url[urls[0]]["crawler_id"] == "xiaohongshu"
    assert by_url[urls[1]]["crawler_id"] == "wechat"
    assert by_url[urls[2]]["crawler_id"] == "generic_html"
