from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any
from urllib.request import Request, urlopen

from mcp.server.fastmcp import FastMCP

CACHE = Path.home() / ".dana" / "docs_cache"
CACHE.mkdir(parents=True, exist_ok=True)


def register_docs_context_tools(mcp: FastMCP) -> None:
    @mcp.tool()
    def resolve_library(library: str) -> dict[str, Any]:
        return {
            "library": library,
            "normalized": library.strip().lower(),
            "query": library + " official documentation",
            "provider": "pluggable docs cache",
        }

    @mcp.tool()
    def get_library_docs(
        library: str, url: str, max_chars: int = 12000, refresh: bool = False
    ) -> dict[str, Any]:
        f = CACHE / (hashlib.sha256(url.encode()).hexdigest() + ".json")
        cached = f.exists() and not refresh
        if cached:
            d = json.loads(f.read_text())
        else:
            r = Request(url, headers={"User-Agent": "Dana-MCP/1.0"})
            content = urlopen(r, timeout=20).read().decode(errors="ignore")
            d = {
                "library": library,
                "url": url,
                "content": content,
                "fetched_at": time.time(),
            }
            f.write_text(json.dumps(d))
        return {
            "library": library,
            "url": url,
            "content": d["content"][: max(1000, min(max_chars, 50000))],
            "cached": cached,
        }

    @mcp.tool()
    def search_library_docs(
        query: str, library: str = "", limit: int = 5
    ) -> dict[str, Any]:
        out = []
        for f in CACHE.glob("*.json"):
            try:
                d = json.loads(f.read_text())
                t = d["content"]
                i = t.lower().find(query.lower())
            except:
                continue
            if i >= 0 and (
                not library or library.lower() in d.get("library", "").lower()
            ):
                out.append(
                    {
                        "library": d.get("library"),
                        "url": d.get("url"),
                        "snippet": t[max(0, i - 500) : i + 1500],
                    }
                )
        return {"query": query, "results": out[:limit]}

    @mcp.tool()
    def context_compress(items: list[str], max_chars: int = 12000) -> dict[str, Any]:
        seen = set()
        out = []
        used = 0
        for x in items:
            x = " ".join(x.split())
            if not x or x in seen:
                continue
            seen.add(x)
            part = x[: max_chars - used]
            if not part:
                break
            out.append(part)
            used += len(part)
        return {
            "context": "\n\n".join(out),
            "used": used,
            "budget": max_chars,
            "items": len(out),
        }
