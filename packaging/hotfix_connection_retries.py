#!/usr/bin/env python3
"""Harden flaky public MCP probes and connection tests (1.7.2)."""
from pathlib import Path

p = Path("dana/setup.py")
t = p.read_text(encoding="utf-8")
changed = False

old_status = """        try:
            public_verified = verify_public_endpoint(funnel_host, timeout=3.0) if funnel_host else False
        except Exception:
            public_verified = False"""
new_status = """        try:
            public_verified = False
            if funnel_host:
                for _attempt in range(3):
                    public_verified = verify_public_endpoint(funnel_host, timeout=4.0)
                    if public_verified:
                        break
                    time.sleep(0.6 * (_attempt + 1))
        except Exception:
            public_verified = False"""
if old_status in t:
    t = t.replace(old_status, new_status)
    changed = True
    print("status public retry")
elif "verify_public_endpoint(funnel_host, timeout=4.0)" in t:
    print("status public retry already present")

old_try = """    for path in ordered_paths:
        url = f\"https://{host}{path}\"
        if _try(url):
            return True
    return False"""
new_try = """    attempts = max(1, int(os.environ.get(\"DANA_PUBLIC_PROBE_RETRIES\", \"3\") or \"3\"))
    for attempt in range(attempts):
        for path in ordered_paths:
            url = f\"https://{host}{path}\"
            if _try(url):
                return True
        if attempt + 1 < attempts:
            time.sleep(0.5 * (attempt + 1))
    return False"""
if old_try in t:
    t = t.replace(old_try, new_try)
    changed = True
    print("verify_public retry")
elif "DANA_PUBLIC_PROBE_RETRIES" in t:
    print("verify_public retry already present")

if "transient_keys" not in t:
    old_loop = """    for name, url, host in candidates:
        try:
            request = urllib.request.Request(
                url,
                data=initialize,
                method=\"POST\",
                headers={
                    \"Accept\": \"application/json, text/event-stream\",
                    \"Content-Type\": \"application/json\",
                    \"Authorization\": f\"Bearer {token}\",
                    \"Host\": host,
                },
            )
            with ssl_urlopen(request, timeout=12) as response:
                raw = response.read(65536).decode(\"utf-8\", \"replace\")
                content_type = response.headers.get(\"content-type\", \"\")
                handshake_ok = response.status == 200 and (
                    \"application/json\" in content_type or \"text/event-stream\" in content_type
                )
                checks.append({
                    \"name\": name,
                    \"url\": url,
                    \"ok\": handshake_ok,
                    \"status\": response.status,
                    \"content_type\": content_type,
                    \"handshake\": \"initialize\" if handshake_ok else \"failed\",
                    \"response_preview\": raw[:240],
                })
        except Exception as exc:
            status_code = getattr(exc, \"code\", None)
            checks.append({
                \"name\": name,
                \"url\": url,
                \"ok\": False,
                \"status\": status_code,
                \"handshake\": \"failed\",
                \"error\": str(exc)[:180],
            })
"""
    new_loop = """    transient_keys = (
        \"timed out\", \"timeout\", \"temporarily\", \"connection reset\", \"connection aborted\",
        \"10053\", \"10054\", \"broken pipe\", \"network is unreachable\", \"name resolution\",
        \"eof occurred\", \"remote end closed\",
    )
    for name, url, host in candidates:
        last_fail: dict[str, object] | None = None
        for attempt in range(3):
            try:
                request = urllib.request.Request(
                    url,
                    data=initialize,
                    method=\"POST\",
                    headers={
                        \"Accept\": \"application/json, text/event-stream\",
                        \"Content-Type\": \"application/json\",
                        \"Authorization\": f\"Bearer {token}\",
                        \"Host\": host,
                    },
                )
                with ssl_urlopen(request, timeout=12) as response:
                    raw = response.read(65536).decode(\"utf-8\", \"replace\")
                    content_type = response.headers.get(\"content-type\", \"\")
                    handshake_ok = response.status == 200 and (
                        \"application/json\" in content_type or \"text/event-stream\" in content_type
                    )
                    checks.append({
                        \"name\": name,
                        \"url\": url,
                        \"ok\": handshake_ok,
                        \"status\": response.status,
                        \"content_type\": content_type,
                        \"handshake\": \"initialize\" if handshake_ok else \"failed\",
                        \"response_preview\": raw[:240],
                        \"attempts\": attempt + 1,
                    })
                    break
            except Exception as exc:
                status_code = getattr(exc, \"code\", None)
                last_fail = {
                    \"name\": name,
                    \"url\": url,
                    \"ok\": False,
                    \"status\": status_code,
                    \"handshake\": \"failed\",
                    \"error\": str(exc)[:180],
                    \"attempts\": attempt + 1,
                }
                msg = str(exc).lower()
                if not any(k in msg for k in transient_keys) or attempt >= 2:
                    checks.append(last_fail)
                    break
                time.sleep(0.7 * (attempt + 1))
        else:
            if last_fail is not None and not any(c.get(\"name\") == name for c in checks):
                checks.append(last_fail)
"""
    if old_loop in t:
        t = t.replace(old_loop, new_loop)
        changed = True
        print("test_connections retry")
    else:
        print("WARN test_connections block not exact")
else:
    print("test_connections retry already present")

if changed:
    p.write_text(t, encoding="utf-8")
    print("wrote dana/setup.py")
else:
    print("no changes")
