#!/usr/bin/env python3
from __future__ import annotations

import re
import shutil
import subprocess
import time
from dataclasses import dataclass
from pathlib import Path


class ProxyConfigurationError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProxyTarget:
    kind: str
    config: Path
    domain: str
    created: bool = False


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def _run(command: list[str], check: bool = True) -> subprocess.CompletedProcess[str]:
    return subprocess.run(command, check=check, text=True, capture_output=True)


def detect_proxy(domain: str) -> ProxyTarget | None:
    if command_exists("nginx"):
        result = _run(["sudo", "nginx", "-T"], check=False)
        output = result.stdout + "\n" + result.stderr
        marker = "# configuration file "
        current: Path | None = None
        for line in output.splitlines():
            if line.startswith(marker) and line.endswith(":"):
                current = Path(line[len(marker) : -1])
            elif current and re.search(r"\bserver_name\b", line) and domain in line:
                return ProxyTarget("nginx", current, domain)
        return ProxyTarget(
            "nginx", Path(f"/etc/nginx/sites-available/{domain}"), domain, created=True
        )
    if command_exists("caddy"):
        config = Path("/etc/caddy/Caddyfile")
        return ProxyTarget("caddy", config, domain, created=not config.exists())
    if command_exists("apache2ctl") or command_exists("apachectl"):
        cmd = "apache2ctl" if command_exists("apache2ctl") else "apachectl"
        result = _run(["sudo", cmd, "-S"], check=False)
        match = re.search(
            rf"port \d+ namevhost {re.escape(domain)} \(([^)]+)\)",
            result.stdout + result.stderr,
        )
        if match:
            return ProxyTarget("apache", Path(match.group(1)), domain)
    return None


def backup(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(f"{path.name}.dana-backup-{stamp}")
    _run(["sudo", "cp", "-a", str(path), str(destination)])
    return destination


def _sudo_write(path: Path, content: str) -> None:
    tmp = Path(f"/tmp/dana-{path.name}.tmp")
    tmp.write_text(content, encoding="utf-8")
    _run(["sudo", "mkdir", "-p", str(path.parent)])
    _run(["sudo", "cp", str(tmp), str(path)])


def _nginx_route(port: int) -> str:
    return f"""\n    # Dana MCP Server\n    location = /mcp {{\n        proxy_pass http://127.0.0.1:{port};\n        proxy_http_version 1.1;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n        proxy_buffering off;\n        proxy_read_timeout 3600s;\n    }}\n"""


def _inject_before_closing_block(text: str, needle: str, route: str) -> str:
    start = text.find(needle)
    if start < 0:
        raise ProxyConfigurationError(
            "Could not locate the selected virtual host block."
        )
    depth = 0
    opened = False
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
            opened = True
        elif text[index] == "}" and opened:
            depth -= 1
            if depth == 0:
                return text[:index] + route + text[index:]
    raise ProxyConfigurationError("Selected virtual host block is incomplete.")


def _nginx_server(
    domain: str,
    port: int,
    origin_protocol: str,
    cert: str | None = None,
    key: str | None = None,
) -> str:
    if origin_protocol == "https":
        if not cert or not key:
            raise ProxyConfigurationError(
                "A new Nginx HTTPS virtual host requires certificate and private-key paths."
            )
        return f"server {{\n    listen 443 ssl;\n    server_name {domain};\n    ssl_certificate {cert};\n    ssl_certificate_key {key};{_nginx_route(port)}\n}}\n"
    return f"server {{\n    listen 80;\n    server_name {domain};{_nginx_route(port)}\n}}\n"


def _apache_route(port: int) -> str:
    return f"""\n    # Dana MCP Server\n    ProxyPreserveHost On\n    ProxyPass /mcp http://127.0.0.1:{port}/mcp\n    ProxyPassReverse /mcp http://127.0.0.1:{port}/mcp\n    RequestHeader set X-Forwarded-Proto \"https\"\n"""


def _caddy_server(domain: str, port: int, origin_protocol: str) -> str:
    if origin_protocol == "http":
        return f"http://{domain} {{\n    reverse_proxy /mcp 127.0.0.1:{port}\n}}\n"
    return f"{domain} {{\n    reverse_proxy /mcp 127.0.0.1:{port}\n}}\n"


def install_caddy() -> None:
    if command_exists("caddy"):
        return
    if not command_exists("apt-get"):
        raise ProxyConfigurationError(
            "Automatic Caddy installation currently requires an apt-based Linux distribution."
        )
    _run(["sudo", "apt-get", "update"])
    _run(["sudo", "apt-get", "install", "-y", "caddy"])


def apply_proxy(
    target: ProxyTarget,
    backend_port: int,
    origin_protocol: str = "https",
    cert: str | None = None,
    key: str | None = None,
) -> Path | None:
    original = (
        target.config.read_text(encoding="utf-8") if target.config.exists() else ""
    )
    if "Dana MCP Server" in original:
        return None
    backup_path = backup(target.config) if target.config.exists() else None
    created_site = target.created and target.kind == "nginx"
    try:
        if target.kind == "nginx":
            updated = (
                _nginx_server(target.domain, backend_port, origin_protocol, cert, key)
                if target.created
                else _inject_before_closing_block(
                    original, "server", _nginx_route(backend_port)
                )
            )
            _sudo_write(target.config, updated)
            if created_site:
                link = Path(f"/etc/nginx/sites-enabled/{target.domain}")
                _run(["sudo", "ln", "-sfn", str(target.config), str(link)])
            _run(["sudo", "nginx", "-t"])
            _run(["sudo", "systemctl", "reload", "nginx"])
        elif target.kind == "caddy":
            updated = (
                original
                + "\n"
                + _caddy_server(target.domain, backend_port, origin_protocol)
            )
            _sudo_write(target.config, updated)
            _run(["sudo", "caddy", "validate", "--config", str(target.config)])
            _run(["sudo", "systemctl", "reload", "caddy"])
        elif target.kind == "apache":
            updated = _inject_before_closing_block(
                original, "VirtualHost", _apache_route(backend_port)
            )
            _sudo_write(target.config, updated)
            _run(["sudo", "a2enmod", "proxy", "proxy_http", "headers"], check=False)
            cmd = "apache2ctl" if command_exists("apache2ctl") else "apachectl"
            _run(["sudo", cmd, "-t"])
            _run(["sudo", "systemctl", "reload", "apache2"])
        else:
            raise ProxyConfigurationError(f"Unsupported reverse proxy: {target.kind}")
    except Exception as exc:
        if backup_path:
            _run(
                ["sudo", "cp", "-a", str(backup_path), str(target.config)], check=False
            )
        elif target.config.exists():
            _run(["sudo", "rm", "-f", str(target.config)], check=False)
        if created_site:
            _run(
                ["sudo", "rm", "-f", f"/etc/nginx/sites-enabled/{target.domain}"],
                check=False,
            )
        service = target.kind
        _run(["sudo", "systemctl", "reload", service], check=False)
        raise ProxyConfigurationError(
            f"Proxy configuration failed and was rolled back: {exc}"
        ) from exc
    return backup_path
