#!/usr/bin/env python3

from dana.tools.performance_engine import (
    build_dag,
    classify_complexity,
    delta,
    fast_path,
    fingerprint,
    plan,
    semantic_get,
    semantic_put,
    tool_cost,
)


def test_fast_path_and_adaptive_budget():
    assert fast_path("git status")["tool"] == "git"
    assert classify_complexity("show status")["budget_tokens"] == 4000
    assert (
        classify_complexity("refactor the authentication architecture and debug it")[
            "budget_tokens"
        ]
        >= 12000
    )


def test_dependency_dag_levels_and_cycle_detection():
    dag = build_dag(
        [
            {"name": "system_info"},
            {"name": "system_metrics"},
            {"name": "run_tests", "depends_on": [0, 1]},
        ]
    )
    assert dag["levels"] == [[0, 1], [2]]


def test_result_delta():
    assert delta({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 4})["delta"] == {
        "b": 3,
        "c": 4,
    }
    assert delta("same", "same")["changed"] is False


def test_fingerprint_is_stable():
    assert fingerprint({"b": 2, "a": 1}) == fingerprint({"a": 1, "b": 2})


def test_semantic_cache_normalizes_query():
    semantic_put("Please show the system status", {"ok": True}, ttl=30)
    assert semantic_get("show system status", ttl=30) == {"ok": True}


def test_plan_uses_fast_path_and_parallel_levels():
    result = plan("git status", ["git", "system_info"])
    assert result["steps"] == [
        {"id": 0, "tool": "git", "depends_on": [], "cost": tool_cost("git")}
    ]
    assert result["execution_levels"] == [[0]]


def test_incremental_python_symbol_index(tmp_path):
    p = tmp_path / "sample.py"
    p.write_text(
        "class User:\n    def create(self):\n        return 1\n", encoding="utf-8"
    )
    from dana.tools.performance_engine import extract_symbols

    symbols = extract_symbols(p)
    assert {s["name"] for s in symbols} == {"User", "create"}
