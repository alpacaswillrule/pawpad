"""Discord bot token + guild ID collection."""

from __future__ import annotations

import httpx

from installer._helpers import prompt, section


def run(state: dict) -> None:
    have_token = bool(state.get("discord_token"))
    have_guild = bool(state.get("discord_guild_id"))

    if have_token and have_guild:
        section(
            "Discord",
            "Token + guild ID loaded from .env.dev. Verifying...",
        )
    else:
        section(
            "Discord bot",
            "1. https://discord.com/developers/applications → New Application → \"Jojo\"\n"
            "2. Bot tab → Reset Token → copy\n"
            "3. Enable [bold]MESSAGE CONTENT INTENT[/bold] (privileged gateway intents)\n"
            "4. OAuth2 → URL Generator:\n"
            "      scopes: bot, applications.commands\n"
            "      perms: View Channels, Send Messages, Manage Channels,\n"
            "             Read Message History, Attach Files, Use Slash Commands,\n"
            "             Embed Links, Add Reactions\n"
            "   Open the URL → invite the bot to your server\n"
            "5. Discord Developer Mode → right-click your server → Copy Server ID\n"
            "6. Create a category named [bold]`projects`[/bold] in your server\n",
        )

    token = state.get("discord_token") or prompt("Discord bot token", password=True)
    guild_id = state.get("discord_guild_id") or prompt("Discord guild (server) ID")

    headers = {"Authorization": f"Bot {token}"}
    try:
        with httpx.Client(timeout=10) as client:
            r = client.get("https://discord.com/api/v10/users/@me", headers=headers)
            r.raise_for_status()
            bot_user = r.json()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Discord auth failed: {exc}") from exc

    section(
        "Discord: OK",
        f"bot user: [bold]{bot_user.get('username')}#{bot_user.get('discriminator', '0')}[/bold] "
        f"(id {bot_user.get('id')})",
    )

    state["discord_token"] = token
    state["discord_guild_id"] = str(guild_id).strip()
    state["discord_bot_user"] = bot_user.get("username")
