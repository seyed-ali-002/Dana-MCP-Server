from __future__ import annotations

from datetime import datetime
from typing import Any

from rich.rule import Rule

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
    console.print(
        Panel.fit(
            title,
            subtitle="Fast • Secure • Ready for AI agents",
            border_style="cyan",
            padding=(1, 4),
        )
    )


def server_dashboard(settings: Any, mode: str, public_url: str | None = None) -> None:
    banner()
    grid = Table.grid(expand=True, padding=(0, 2))
    grid.add_column(style="dim", justify="right", width=11)
    grid.add_column(ratio=1)
    _row(grid, "STATUS", "[bold green]● ONLINE[/bold green]")
    _row(grid, "MODE", f"[bold cyan]{mode.upper()}[/bold cyan]")
    _row(grid, "TRANSPORT", "HTTP Streamable MCP")
    _row(grid, "WORKERS", f"[bold]{settings.normalized_workers()}[/bold]")
    _row(grid, "LOCAL", f"http://{settings.host}:{settings.port}{settings.mcp_path}")
    _row(grid, "STARTED", datetime.now().strftime("%Y-%m-%d %H:%M:%S"))
    console.print(
        Panel(
            grid,
            title="[bold]SERVER STATUS[/bold]",
            border_style="blue",
            padding=(1, 2),
        )
    )

    if public_url:
        connect_url = public_url.rstrip("/")
        if not connect_url.endswith(settings.mcp_path):
            connect_url = f"{connect_url}{settings.mcp_path}"

        # Keep the connection address outside the status table. Tables/panels can
        # truncate long tokenized URLs; a dedicated Text renderable preserves the
        # exact URL and makes terminal selection/copy straightforward.
        console.print()
        console.print("[bold green]MCP CONNECTION URL[/bold green]")
        console.print(
            Text(connect_url, style="bold green"), soft_wrap=True, overflow="ignore"
        )
        console.print(
            "[dim]Copy the complete URL above when connecting an MCP client.[/dim]"
        )

    console.print()
    console.print(Rule("[bold cyan]ACTIVITY[/bold cyan]", style="dim cyan"))
    console.print(
        "[dim]Only important worker events are shown. HTTP/session noise is hidden. Press Ctrl+C to stop.[/dim]"
    )


def worker_event(
    worker_name: str,
    worker_number: int,
    tool: str,
    input_tokens: int,
    output_tokens: int,
    duration_ms: float,
    success: bool = True,
) -> None:
    status = "[green]✓[/green]" if success else "[red]✗[/red]"
    now = datetime.now().strftime("%H:%M:%S")
    worker = f"{worker_name} [dim]#{worker_number}[/dim]"
    tokens = input_tokens + output_tokens
    token_text = f"[dim]{tokens:,} tok[/dim]"
    timing = f"[yellow]{duration_ms:.0f}ms[/yellow]"
    console.print(
        f"[dim]{now}[/dim]  {status} [bold cyan]{worker}[/bold cyan]  "
        f"[white]{tool}[/white]  {timing}  {token_text} "
        f"[dim]({input_tokens:,} in / {output_tokens:,} out)[/dim]"
    )


def worker_ready(worker_name: str, worker_number: int) -> None:
    now = datetime.now().strftime("%H:%M:%S")
    console.print(
        f"[dim]{now}[/dim]  [green]●[/green] [bold cyan]{worker_name}[/bold cyan] "
        f"[dim]#{worker_number}[/dim] [green]ONLINE[/green]"
    )


def startup_error(message: str) -> None:
    console.print(
        Panel(
            f"[bold red]Startup failed[/bold red]\n\n{message}",
            title="[bold red]DANA ERROR[/bold red]",
            border_style="red",
            padding=(1, 2),
        )
    )
