from dana.setup import SetupStatus

def test_setup_status_connectivity_fields():
    s = SetupStatus(
        True, "Running", "host", True, "host.ts.net", True,
        "https://x", "http://127.0.0.1:8765/t/mcp", "https://host.ts.net/t/mcp",
        connectivity="connected", public_verified=True, hint="ok", local_only=False,
    )
    d = s.to_dict()
    assert d["connectivity"] == "connected"
    assert d["public_verified"] is True
    assert d["local_only"] is False
