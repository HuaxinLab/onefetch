from onefetch.adapters.zhihu import ZhihuAdapter


def test_supports_zhihu_question_url() -> None:
    adapter = ZhihuAdapter()
    assert adapter.supports("https://www.zhihu.com/question/2016626718161465398")
    assert adapter.supports("https://zhuanlan.zhihu.com/p/123456")


async def test_build_from_state_extracts_question_and_top_answers() -> None:
    adapter = ZhihuAdapter()
    state = {
        "initialState": {
            "entities": {
                "questions": {
                    "123": {
                        "id": 123,
                        "title": "测试问题",
                        "detail": "<p>问题详情</p>",
                        "answerCount": 2,
                        "followerCount": 99,
                    }
                },
                "answers": {
                    "a1": {
                        "id": "a1",
                        "question": {"id": 123},
                        "author": {"name": "作者甲"},
                        "voteupCount": 20,
                        "content": "<p>回答甲正文</p>",
                    },
                    "a2": {
                        "id": "a2",
                        "question": {"id": 123},
                        "author": {"name": "作者乙"},
                        "voteupCount": 10,
                        "excerpt": "回答乙摘要",
                    },
                },
            }
        }
    }
    body, title, author, published_at, metadata = await adapter._build_from_state(state, "123", None, None)
    assert "测试问题" in (title or "")
    assert author is None
    assert published_at is None
    assert "问题详情" in body
    assert "回答甲正文" in body
    assert "回答乙摘要" in body
    assert metadata["content_type"] == "question"
    assert metadata["top_answers_count"] == 2


async def test_build_from_state_extracts_zhuanlan_article() -> None:
    adapter = ZhihuAdapter()
    state = {
        "initialState": {
            "entities": {
                "articles": {
                    "456": {
                        "id": 456,
                        "title": "专栏标题",
                        "content": "<p>这是专栏正文第一段</p><p>这是第二段</p>",
                        "excerpt": "摘要",
                        "author": {"name": "专栏作者"},
                        "voteupCount": 1024,
                        "commentCount": 88,
                    }
                }
            }
        }
    }
    body, title, author, published_at, metadata = await adapter._build_from_state(state, None, None, "456")
    assert "这是专栏正文第一段" in body
    assert "这是第二段" in body
    assert title == "专栏标题"
    assert author == "专栏作者"
    assert published_at is None
    assert metadata["content_type"] == "zhuanlan_article"
    assert metadata["article_id"] == "456"


def test_needs_answer_completion_when_read_more_or_short() -> None:
    assert ZhihuAdapter._needs_answer_completion("这是一段短摘要") is True
    assert ZhihuAdapter._needs_answer_completion("......阅读全文") is True
    assert ZhihuAdapter._needs_answer_completion("这是一个" + ("比较完整的回答内容" * 30)) is False


def test_detect_challenge_or_login_page() -> None:
    assert ZhihuAdapter._is_challenge_or_login_page(
        "https://www.zhihu.com/account/unhuman?need_login=true",
        "<html><title>安全验证 - 知乎</title></html>",
    )
    assert not ZhihuAdapter._is_challenge_or_login_page(
        "https://zhuanlan.zhihu.com/p/123456",
        "<html><head><title>普通文章</title></head><body><article>正文</article></body></html>",
    )


def test_request_headers_include_cookie_when_configured(monkeypatch) -> None:
    monkeypatch.setenv("ONEFETCH_ZHIHU_COOKIE", "z_c0=abc; d_c0=def")
    headers = ZhihuAdapter._request_headers("https://zhuanlan.zhihu.com/p/123")
    assert headers.get("cookie") == "z_c0=abc; d_c0=def"


def test_looks_like_challenge_payload() -> None:
    assert ZhihuAdapter._looks_like_challenge_payload("安全验证", "请您登录后查看更多专业优质内容")
    assert not ZhihuAdapter._looks_like_challenge_payload("普通文章", "这是文章正文")
