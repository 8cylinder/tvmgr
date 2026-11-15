"""Output helpers for tvmgr."""

from __future__ import annotations

from dataclasses import dataclass

from rich.console import Console
from rich.markup import escape


@dataclass(frozen=True)
class Ui:
    """The stdout and stderr consoles used by the application."""

    out: Console
    err: Console


def make_ui(color: str) -> Ui:
    """Create consoles for the requested color mode."""
    if color == "always":
        return Ui(
            out=Console(force_terminal=True),
            err=Console(stderr=True, force_terminal=True),
        )
    if color == "never":
        return Ui(
            out=Console(force_terminal=False, no_color=True),
            err=Console(stderr=True, force_terminal=False, no_color=True),
        )
    return Ui(out=Console(), err=Console(stderr=True))


def ok(ui: Ui, message: str) -> None:
    """Print a success message."""
    ui.out.print(f"[green]ok[/green] {escape(message)}")


def warning(ui: Ui, message: str) -> None:
    """Print a warning to stderr."""
    ui.err.print(f"[yellow]warning:[/yellow] {escape(message)}")


def error(ui: Ui, message: str) -> None:
    """Print an error to stderr."""
    ui.err.print(f"[red]error:[/red] {escape(message)}")
