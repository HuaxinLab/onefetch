from onefetch.llm_outputs import parse_and_validate_llm_outputs


def test_parse_llm_outputs_strict_json() -> None:
    raw = """
{
  "summary": "An article about model evaluation.",
  "key_points": ["metric design", "error analysis", "online monitoring"],
  "tags": ["ai", "evaluation"],
  "extras": {"language": "en"}
}
""".strip()
    outputs = parse_and_validate_llm_outputs(raw)
    assert outputs.summary == "An article about model evaluation."
    assert outputs.key_points == ["metric design", "error analysis", "online monitoring"]
    assert outputs.tags == ["ai", "evaluation"]
    assert outputs.extras == {"language": "en"}


def test_parse_llm_outputs_repairs_fenced_json_and_string_lists() -> None:
    raw = """
Here is the result:
```json
{
  "summary": "Main points only",
  "key_points": "- first\\n- second\\n- second",
  "tags": "foo;bar;foo"
}
```
""".strip()
    outputs = parse_and_validate_llm_outputs(raw)
    assert outputs.summary == "Main points only"
    assert outputs.key_points == ["first", "second"]
    assert outputs.tags == ["foo", "bar"]
    assert outputs.extras.get("repaired_from_non_strict_json") is True


def test_parse_llm_outputs_fallback_on_invalid_json() -> None:
    raw = "summary: hello\\nkey_points: [a,b,c]"
    outputs = parse_and_validate_llm_outputs(raw)
    assert outputs.summary == ""
    assert outputs.key_points == []
    assert outputs.tags == []
    assert "validation_error" in outputs.extras
    assert outputs.extras.get("raw_output") == raw

