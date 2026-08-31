from dana.tools.context_engine import (
    build_context,
    compact_session,
    optimize_result,
    read_page,
)


def test_result_compaction_and_pagination():
    value = list(range(250))
    result = optimize_result(value)
    assert result["truncated"] is True
    assert result["next_cursor"]
    page = read_page(result["next_cursor"], 50)
    assert page["count"] == 50


def test_context_budget():
    result = build_context(
        {"stable": "x"},
        {"data": "a" * 50000},
        "history " * 10000,
        {"current": "ok"},
        4000,
    )
    assert result["tokens_est"] <= 4000 or not result["within_budget"]
    assert "static" in result["context"]


def test_session_compaction():
    result = compact_session("test-context-engine", ["one", "one", "two"], 100)
    assert result["source_messages"] == 3
    assert "one" in result["summary"]
