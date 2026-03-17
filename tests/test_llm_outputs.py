from onefetch.models import IngestResult


def test_ingest_result_has_standardized_llm_outputs_defaults() -> None:
    result = IngestResult(
        source_url="https://example.com/a",
        canonical_url="https://example.com/a",
        crawler_id="generic_html",
        status="fetched",
    )
    assert result.llm_outputs.summary == ""
    assert result.llm_outputs.key_points == []
    assert result.llm_outputs.tags == []
    assert result.llm_outputs.extras == {}

