"""Welcome screen — explain what's about to happen.

Shows expected duration, list of credentials we're about to gather, and the
final outcome (VM running on tailnet, bot in your Discord guild).
"""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Confirm

console = Console()


def run(state: dict) -> None:
    console.print(
        Panel.fit(
            "[bold]pawpad installer[/bold]\n\n"
            "About to gather credentials and provision a GCP VM that hosts a Discord\n"
            "bot orchestrating Claude Agent SDK sessions per channel.\n\n"
            "Expected duration: [bold]~15 minutes[/bold].\n\n"
            "You'll need (we'll walk through each):\n"
            "  • GCP service-account JSON (or gcloud auth login)\n"
            "  • A GCP project with billing enabled\n"
            "  • Tailscale auth key\n"
            "  • GitHub auth (gh CLI on this machine)\n"
            "  • A Discord bot token + guild ID\n"
            "  • An Anthropic API key\n",
            border_style="cyan",
        )
    )
    if not Confirm.ask("Ready to start?", default=True):
        raise KeyboardInterrupt()
