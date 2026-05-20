"""Discord bot setup walkthrough.

Walks the operator through creating a Discord application + bot user, then
collects the bot token and guild ID. Verifies the bot can connect to Discord
and reports its current guild memberships.

Writes:
  state["discord_token"]     (sensitive)
  state["discord_guild_id"]
"""

from __future__ import annotations

# TODO:
#   Step-by-step walkthrough:
#     1. https://discord.com/developers/applications → "New Application" → name it "Jojo"
#     2. Bot tab → Add Bot → copy token
#     3. Privileged Gateway Intents: enable
#          - SERVER MEMBERS INTENT
#          - MESSAGE CONTENT INTENT
#     4. OAuth2 → URL Generator:
#          scopes:       bot, applications.commands
#          permissions:  View Channels, Send Messages, Manage Channels, Read Message History,
#                        Attach Files, Use Slash Commands, Embed Links, Add Reactions
#     5. Open generated URL → invite bot to your guild
#     6. In Discord, enable Developer Mode (User Settings → Advanced)
#     7. Right-click your guild → Copy Server ID → paste here
#
#   Then verify via discord.py:
#       import discord
#       client = discord.Client(intents=discord.Intents.default())
#       @client.event
#       async def on_ready():
#           ... check guild membership ...
#       client.run(token)


def run(state: dict) -> None:
    raise NotImplementedError("TODO: Discord bot setup")
