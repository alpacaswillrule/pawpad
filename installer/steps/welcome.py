"""Welcome screen + load .env.dev defaults if present."""

from __future__ import annotations

from pathlib import Path

from installer._helpers import confirm, load_env_dev_defaults, section


def run(state: dict) -> None:
    section(
        "pawpad installer",
        "About to provision a GCP VM hosting a Discord bot that orchestrates\n"
        "Claude Agent SDK sessions per channel.\n\n"
        "Expected duration: [bold]~15 minutes[/bold].\n\n"
        "You'll need (we walk through each):\n"
        "  • GCP project + auth (gcloud login or service-account JSON)\n"
        "  • Tailscale auth key\n"
        "  • GitHub auth (gh CLI on this machine)\n"
        "  • Discord bot token + guild ID\n"
        "  • Anthropic API key\n",
    )

    repo_root = Path(__file__).resolve().parents[2]
    load_env_dev_defaults(state, repo_root)

    if any(state.get(k) for k in ("discord_token", "anthropic_api_key", "tailscale_authkey")):
        section(
            ".env.dev detected",
            "Loaded existing values for: "
            + ", ".join(
                k
                for k in (
                    "discord_token",
                    "discord_guild_id",
                    "anthropic_api_key",
                    "tailscale_authkey",
                    "gcp_project_id",
                )
                if state.get(k)
            ),
        )

    if not confirm("Ready to start?", default=True):
        raise KeyboardInterrupt()
