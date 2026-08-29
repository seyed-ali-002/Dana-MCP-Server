import uvicorn
from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from .config import settings


def _mode() -> str:
    return settings.normalized_mode()


def _banner() -> None:
    console = Console()
    table = Table.grid(padding=(0, 2))
    table.add_row("STATUS", "[bold green]ONLINE[/bold green]")
    table.add_row("MODE", f"[bold cyan]{_mode().upper()}[/bold cyan]")
    table.add_row("TRANSPORT", "HTTP Streamable MCP")
    table.add_row("AUTH", "HTTPS MCP endpoint" if _mode() == "server" else "Tokenized Connection Path")
    table.add_row("ENDPOINT", f"http://{settings.host}:{settings.port}{settings.mcp_path}")
    if settings.public_host:
        if _mode() == "server":
            public_url = f"https://{settings.public_host}{settings.mcp_path}"
        else:
            authority = settings.public_host
            if settings.public_port:
                authority = f"{authority}:{settings.public_port}"
            token_path = "/" + settings.require_auth_token()
            public_url = f"https://{authority}{token_path}{settings.mcp_path}"
        table.add_row("PUBLIC", public_url)
    console.print(Panel(table, title="[bold cyan]DANA MCP SERVER[/bold cyan]", subtitle="[dim]ready for connections[/dim]", border_style="cyan"))


def run() -> None:
    _mode()
    _banner()
    uvicorn.run(
        "dana.http:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level,
        reload=False,
    )


if __name__ == "__main__":
    run()
