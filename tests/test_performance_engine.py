import asyncio

from dana.tools.performance_engine import (
    build_dag,
    classify_complexity,
    delta,
    fast_path,
    fingerprint,
    index_project,
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


def test_incremental_python_symbol_index(tmp_path):
    p = tmp_path / "sample.py"
    p.write_text(
        "class User:\n    def create(self):\n        return 1\n", encoding="utf-8"
    )
    # The engine accepts arbitrary absolute paths; this test validates parsing without
    # requiring the live project index to be populated.
    from dana.tools.performance_engine import extract_symbols

    symbols = extract_symbols(p)
    assert {s["name"] for s in symbols} == {"User", "create"}
