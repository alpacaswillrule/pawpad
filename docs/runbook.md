# Runbook

Common ops once pawpad is up.

## SSH in

```bash
tailscale ssh pawpad-vm
# or, if you set up regular SSH too:
ssh pawpad@pawpad-vm.tailnet-name.ts.net
```

## View bot logs

```bash
journalctl -u jojo-bot.service -f
```

## Restart the bot

```bash
sudo systemctl restart jojo-bot.service
```

In-flight sessions resume via Agent SDK `session_id` — no work lost. The bot
re-attaches to all channels in the `projects` category on startup.

## Rotate the Anthropic API key

```bash
sudo -e /opt/pawpad/.env       # edit ANTHROPIC_API_KEY=
sudo systemctl restart jojo-bot.service
```

## Drive an agent manually from SSH (no Discord)

```bash
tailscale ssh pawpad-vm
cd ~/projects/{slug}
claude
```

You're now in a regular interactive Claude Code session in that workspace.
Heads-up: the Discord bot is **still running** and will react to messages
arriving in that channel. If you want to avoid bot ↔ you collisions, run
`/pause` from Discord first (then `/resume` when you're done).

## Take a disk snapshot

```bash
~/pawpad/scripts/snapshot.sh
```

## Tear down (with snapshot)

```bash
~/pawpad/scripts/teardown.sh
```

Pass `--no-snapshot` if you really don't want one.

## View today's spend without using Discord

```bash
sudo -u pawpad sqlite3 /home/pawpad/.pawpad/budget.sqlite \
  "SELECT channel_id, ROUND(SUM(usd), 2) FROM turns WHERE ts >= date('now', 'start of day') GROUP BY channel_id;"
```

## Update pawpad itself

The bot lives at `/opt/pawpad` cloned from `alpacaswillrule/pawpad`. To pull
updates:

```bash
sudo -u pawpad git -C /opt/pawpad pull
sudo systemctl restart jojo-bot.service
```

If the update touches `requirements.txt` or `pyproject.toml`:

```bash
sudo -u pawpad bash -c 'cd /opt/pawpad && .venv/bin/pip install -e .[dev]'
sudo systemctl restart jojo-bot.service
```

## Inspect Obsidian LiveSync

```bash
docker compose -f /opt/pawpad/obsidian/livesync/docker-compose.yml logs -f
```

## Add a skill or plugin to the agent

VM-wide skills live in `/opt/pawpad/claude/skills/`. Drop a `SKILL.md` in a
new subdir and restart the bot; the SDK picks it up on the next session.

For plugins (like `Chachamaru127/claude-code-harness`), install via the
Claude Code plugin marketplace from an interactive `claude` session on the
VM:

```bash
tailscale ssh pawpad-vm
cd /opt/pawpad
claude
> /plugin install Chachamaru127/claude-code-harness
```

The plugin is then available to bot-spawned sessions on next session-create.
