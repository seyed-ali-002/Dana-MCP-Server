"""SSL / CA bundle helpers for frozen AppImage and packaged builds."""
from __future__ import annotations

import os
import ssl
import urllib.request
from functools import lru_cache


@lru_cache(maxsize=1)
def ca_bundle_path() -> str | None:
    """Return a usable CA bundle path for urllib/OpenSSL."""
    for key in ("SSL_CERT_FILE", "REQUESTS_CA_BUNDLE", "CURL_CA_BUNDLE"):
        value = os.environ.get(key, "").strip()
        if value and os.path.isfile(value):
            return value
    for candidate in (
        "/etc/ssl/certs/ca-certificates.crt",
        "/etc/pki/tls/certs/ca-bundle.crt",
        "/etc/ssl/cert.pem",
        "/usr/lib/ssl/cert.pem",
    ):
        if os.path.isfile(candidate):
            return candidate
    try:
        import certifi
        path = certifi.where()
        if path and os.path.isfile(path):
            return path
    except Exception:
        pass
    return None


def configure_ssl_environment() -> str | None:
    """Ensure process-wide SSL env vars point at a valid CA bundle."""
    path = ca_bundle_path()
    if not path:
        return None
    os.environ["SSL_CERT_FILE"] = path
    os.environ["REQUESTS_CA_BUNDLE"] = path
    os.environ["CURL_CA_BUNDLE"] = path
    return path


def ssl_context() -> ssl.SSLContext:
    """Build an SSL context that works inside AppImage / frozen runtimes."""
    path = configure_ssl_environment()
    if path:
        try:
            return ssl.create_default_context(cafile=path)
        except Exception:
            pass
    try:
        return ssl.create_default_context()
    except Exception:
        return ssl._create_unverified_context()


def urlopen(request, timeout: float = 30):
    """urllib.urlopen with a CA bundle that works in AppImage builds."""
    configure_ssl_environment()
    ctx = ssl_context()
    return urllib.request.urlopen(request, timeout=timeout, context=ctx)
