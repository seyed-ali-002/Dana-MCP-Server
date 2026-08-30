from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

console = Console()

def _row(table: Table, key: str, value: str) -> None:
    table.add_row(f"[dim]{key}[/dim]", value)

def banner() -> None:
    title = Text("DANA", style="bold cyan")
    subtitle = Text("  MCP SERVER", style="bold white")
    title.append_text(subtitle)
    console.print(Panel.fit(title, subtitle="Fast • Secure • Ready for AI agents", border_style="cyan", padding=(1, 4)))

def server_dashboard(settings: Any, mode: str, public_url: str | None = None) -> None:
    console.clear()
    banner()
    grid = Table.grid(expand=False, padding=(0, 2))
    grid.add_column(style="dim", justify="right"); grid.add_column()
    _row(grid, "STATUS", "[bold green]● ONLINE[/bold green]")
    _row(grid, "MODE", f"[bold cyan]{mode.upper()}[/bold cyan]")
    _row(grid, "TRANSPORT", "HTTP Streamable MCP")
    _row(grid, "WORKERS", f"[bold]{settings.normalized_workers()}[/bold]")
    _row(grid, "LOCAL", f"http://{settings.host}:{settings.port}{settings.mcp_path}")
    if public_url: _row(grid, "CONNECT", f"[bold green]{public_url}[/bold green]")
    _row(grid, "STARTED", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    console.print(Panel(grid, title="[bold]SERVER STATUS[/bold]", border_style="blue", padding=(1,2)))
    console.print("[dim]Quiet mode is enabled. Routine request/access logs are hidden. Press Ctrl+C to stop.[/dim]")

def startup_error(message: str) -> None:
    console.print(Panel(f"[bold red]{message}[/bold red]", title="DANA ERROR", border_style="red"))
