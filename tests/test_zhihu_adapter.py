from onefetch.adapters.zhihu import ZhihuAdapter


def test_supports_zhihu_question_url() -> None:
    adapter = ZhihuAdapter()
    assert adapter.supports("https://www.zhihu.com/question/2016626718161465398")
    assert not adapter.supports("https://zhuanlan.zhihu.com/p/123456")


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
    body, title, author, published_at, metadata = await adapter._build_from_state(state, "123", None)
    assert "测试问题" in (title or "")
    assert author is None
    assert published_at is None
    assert "问题详情" in body
    assert "回答甲正文" in body
    assert "回答乙摘要" in body
    assert metadata["content_type"] == "question"
    assert metadata["top_answers_count"] == 2


def test_needs_answer_completion_when_read_more_or_short() -> None:
    assert ZhihuAdapter._needs_answer_completion("这是一段短摘要") is True
    assert ZhihuAdapter._needs_answer_completion("......阅读全文") is True
    assert ZhihuAdapter._needs_answer_completion("这是一个" + ("比较完整的回答内容" * 30)) is False
