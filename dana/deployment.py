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


def command_exists(name: str) -> bool:
    return shutil.which(name) is not None


def detect_proxy(domain: str) -> ProxyTarget:
    if command_exists("nginx"):
        result = subprocess.run(["sudo", "nginx", "-T"], text=True, capture_output=True)
        output = result.stdout + "\n" + result.stderr
        marker = f"# configuration file "
        current: Path | None = None
        for line in output.splitlines():
            if line.startswith(marker) and line.endswith(":"):
                current = Path(line[len(marker):-1])
            elif current and re.search(r"\bserver_name\b", line) and domain in line:
                return ProxyTarget("nginx", current, domain)
        raise ProxyConfigurationError(f"Nginx is installed, but no active server block for {domain} was found.")
    if command_exists("caddy"):
        config = Path("/etc/caddy/Caddyfile")
        if config.exists() and domain in config.read_text(encoding="utf-8", errors="ignore"):
            return ProxyTarget("caddy", config, domain)
        raise ProxyConfigurationError(f"Caddy is installed, but no site block for {domain} was found.")
    if command_exists("apache2ctl") or command_exists("apachectl"):
        cmd = "apache2ctl" if command_exists("apache2ctl") else "apachectl"
        result = subprocess.run(["sudo", cmd, "-S"], text=True, capture_output=True)
        match = re.search(rf"port \d+ namevhost {re.escape(domain)} \(([^)]+)\)", result.stdout + result.stderr)
        if match:
            return ProxyTarget("apache", Path(match.group(1)), domain)
        raise ProxyConfigurationError(f"Apache is installed, but no active virtual host for {domain} was found.")
    raise ProxyConfigurationError("No supported reverse proxy detected (Nginx, Caddy, or Apache).")


def backup(path: Path) -> Path:
    stamp = time.strftime("%Y%m%d-%H%M%S")
    destination = path.with_name(f"{path.name}.dana-backup-{stamp}")
    subprocess.run(["sudo", "cp", "-a", str(path), str(destination)], check=True)
    return destination


def _sudo_write(path: Path, content: str) -> None:
    tmp = Path("/tmp/dana-proxy-config.tmp")
    tmp.write_text(content, encoding="utf-8")
    subprocess.run(["sudo", "cp", str(tmp), str(path)], check=True)


def _nginx_route(port: int) -> str:
    return f'''\n    # Dana MCP Server\n    location = /mcp {{\n        proxy_pass http://127.0.0.1:{port};\n        proxy_http_version 1.1;\n        proxy_set_header Host $host;\n        proxy_set_header X-Real-IP $remote_addr;\n        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;\n        proxy_set_header X-Forwarded-Proto $scheme;\n        proxy_buffering off;\n        proxy_read_timeout 3600s;\n    }}\n'''


def _inject_before_closing_block(text: str, needle: str, route: str) -> str:
    start = text.find(needle)
    if start < 0:
        raise ProxyConfigurationError("Could not locate the selected virtual host block.")
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


def _apache_route(port: int) -> str:
    return f'''\n    # Dana MCP Server\n    ProxyPreserveHost On\n    ProxyPass /mcp http://127.0.0.1:{port}/mcp\n    ProxyPassReverse /mcp http://127.0.0.1:{port}/mcp\n'''


def apply_proxy(target: ProxyTarget, backend_port: int) -> Path:
    original = target.config.read_text(encoding="utf-8")
    if "Dana MCP Server" in original:
        return target.config
    backup_path = backup(target.config)
    try:
        if target.kind == "nginx":
            updated = _inject_before_closing_block(original, "server", _nginx_route(backend_port))
            _sudo_write(target.config, updated)
            subprocess.run(["sudo", "nginx", "-t"], check=True)
            subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=True)
        elif target.kind == "caddy":
            route = f"\n    # Dana MCP Server\n    handle /mcp {{\n        reverse_proxy 127.0.0.1:{backend_port}\n    }}\n"
            updated = _inject_before_closing_block(original, target.domain, route)
            _sudo_write(target.config, updated)
            subprocess.run(["sudo", "caddy", "validate", "--config", str(target.config)], check=True)
            subprocess.run(["sudo", "systemctl", "reload", "caddy"], check=True)
        elif target.kind == "apache":
            updated = _inject_before_closing_block(original, "<VirtualHost", _apache_route(backend_port))
            _sudo_write(target.config, updated)
            command = "apache2ctl" if command_exists("apache2ctl") else "apachectl"
            subprocess.run(["sudo", command, "configtest"], check=True)
            service = "apache2" if command_exists("apache2ctl") else "httpd"
            subprocess.run(["sudo", "systemctl", "reload", service], check=True)
        else:
            raise ProxyConfigurationError(f"Unsupported reverse proxy: {target.kind}")
    except Exception as exc:
        subprocess.run(["sudo", "cp", "-a", str(backup_path), str(target.config)], check=False)
        if target.kind == "nginx":
            subprocess.run(["sudo", "systemctl", "reload", "nginx"], check=False)
        elif target.kind == "caddy":
            subprocess.run(["sudo", "systemctl", "reload", "caddy"], check=False)
        elif target.kind == "apache":
            service = "apache2" if command_exists("apache2ctl") else "httpd"
            subprocess.run(["sudo", "systemctl", "reload", service], check=False)
        raise ProxyConfigurationError(f"Proxy configuration failed and was rolled back: {exc}") from exc
    return backup_path
