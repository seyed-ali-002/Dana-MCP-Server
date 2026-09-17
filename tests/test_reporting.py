from dana.reporting import _render


def test_report_active_time_is_union_of_overlapping_operations():
    data = {
        "start": 100.0,
        "last": 102.0,
        "input": 2,
        "output": 4,
        "operations": 2,
        "exact_tokens": 0,
        "estimated_tokens": 6,
        "active_seconds": 2.0,
        "events": [
            {"time": 101.0, "started": 100.0, "duration": 1000, "input": 1, "output": 2, "worker": "A", "number": 1, "tool": "x", "success": True},
            {"time": 101.5, "started": 100.5, "duration": 1000, "input": 1, "output": 2, "worker": "B", "number": 2, "tool": "y", "success": True},
        ],
    }
    html = _render(data)
    assert "Active usage time" in html
    assert "1s" in html
