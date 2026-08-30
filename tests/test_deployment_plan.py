#!/usr/bin/env python3
from dana import deployment


def test_detect_proxy_returns_none_without_supported_proxy(monkeypatch):
    monkeypatch.setattr(deployment, "command_exists", lambda name: False)
    assert deployment.detect_proxy("mcp.example.com") is None


def test_new_nginx_https_requires_certificate_paths():
    target = deployment.ProxyTarget(
        "nginx",
        deployment.Path("/tmp/dana-nginx-test"),
        "mcp.example.com",
        created=True,
    )
    try:
        deployment._nginx_server(target.domain, 18080, "https")
    except deployment.ProxyConfigurationError:
        pass
    else:
        raise AssertionError(
            "HTTPS Nginx site should require explicit certificate paths"
        )


def test_http_origin_nginx_route_is_plain_http():
    config = deployment._nginx_server("mcp.example.com", 18080, "http")
    assert "listen 80;" in config
    assert "proxy_pass http://127.0.0.1:18080;" in config
