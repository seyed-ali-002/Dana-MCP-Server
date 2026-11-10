

# --- post-2.0.1 connection mode overrides (loaded last) -----------------
def get_connection_mode() -> str:
    global _CONNECTION_MODE
    try:
        env_vals = _read_env()
    except Exception:
        env_vals = {}
    saved = str(
        env_vals.get("DANA_CONNECTION_MODE")
        or os.environ.get("DANA_CONNECTION_MODE")
        or _CONNECTION_MODE
        or "all"
    ).strip().lower()
    if saved in {"all", "local", "public", "supermcp"}:
        _CONNECTION_MODE = saved
        return saved
    return "all"


def set_connection_mode(mode: str = "all") -> dict[str, object]:
    global _CONNECTION_MODE
    m = (mode or "all").strip().lower()
    if m not in {"all", "local", "public", "supermcp"}:
        m = "all"
    _CONNECTION_MODE = m
    os.environ["DANA_CONNECTION_MODE"] = m
    try:
        env = _read_env()
        env["DANA_CONNECTION_MODE"] = m
        _write_env(env)
    except Exception as exc:
        _setup_log(f"Could not persist connection mode: {exc}", "warning")
    try:
        from . import supermcp
        if m == "local":
            set_local_only(True)
            try:
                supermcp.stop()
            except Exception:
                pass
            _setup_log("Connection mode set to Local Only (MCP :8765).", "info")
        elif m == "public":
            set_local_only(False)
            try:
                supermcp.stop()
            except Exception:
                pass
            _setup_log("Connection mode set to Public Funnel Only (MCP + HTTPS Funnel).", "info")
        elif m == "supermcp":
            set_local_only(True)
            try:
                supermcp.start()
            except Exception as sm_exc:
                _setup_log(f"SuperMCP start warning: {sm_exc}", "warning")
            _setup_log("Connection mode set to SuperMCP Assistant Only (MCP + SSE :3006).", "info")
        else:
            set_local_only(False)
            try:
                supermcp.start()
            except Exception as sm_exc:
                _setup_log(f"SuperMCP start warning: {sm_exc}", "warning")
            _setup_log("Connection mode set to All Services (Local + Public Funnel + SuperMCP).", "success")
    except Exception as exc:
        _setup_log(f"Connection mode switch warning: {exc}", "warning")
    st = status().to_dict()
    st["connection_mode"] = m
    return {
        "ok": True,
        "connection_mode": m,
        "message": f"Connection mode switched to {m.upper()}.",
        "status": st,
    }
