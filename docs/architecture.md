# pawpad architecture

## Components

```
   ┌─────────────────────┐
   │  Discord (web/app)  │
   │  + Obsidian app     │
   │  (your laptop/phone)│
   └──────────┬──────────┘
              │ Tailscale
              ▼
┌────────────────────────────────────────────────────┐
│  GCP VM (Ubuntu 24.04, 4 vCPU, 16 GB, 1 TB disk)   │
│                                                     │
│  ┌────────────────────────────────────────────┐    │
│  │ systemd: jojo-bot.service                  │    │
│  │   └ Python: discord.py + claude-agent-sdk  │    │
│  │      ├ SessionManager (per-channel)        │    │
│  │      ├ Budget (sqlite ledger)              │    │
│  │      └ Audit (#jojo-audit poster)          │    │
│  └────────────────────────────────────────────┘    │
│                                                     │
│  ┌────────────────────────────────────────────┐    │
│  │ systemd: livesync.service                  │    │
│  │   └ docker: CouchDB on :5984               │    │
│  └────────────────────────────────────────────┘    │
│                                                     │
│  ┌────────────────────────────────────────────┐    │
│  │ systemd: quartz.service                    │    │
│  │   └ npx quartz serve --port 8080           │    │
│  └────────────────────────────────────────────┘    │
│                                                     │
│  ~/projects/{slug}/        # one per channel        │
│  ~/obsidian-vault/         # shared, llm-wiki style │
└────────────────────────────────────────────────────┘
              │
              │ outbound only
              ▼
   Discord gateway, Anthropic API, GitHub API
```

## Per-channel session flow

```
1. Channel created under `projects` category
        │
        ▼
2. on_guild_channel_create handler
        │
        ▼
3. scripts/new-project.sh {slug} {topic}
   - mkdir ~/projects/{slug}, git init
   - gh repo create alpacaswillrule/{slug} --private
   - mkdir ~/obsidian-vault/projects/{slug}, scaffold plan.md
        │
        ▼
4. SessionManager.create_for_channel
   - Build ChannelSession(channel_id, workspace, vault_dir)
   - If channel.topic: enqueue as initial prompt
   - Post welcome message
        │
        ▼
5. User sends message in channel
        │
        ▼
6. SessionManager.handle_message
   - Append to session.pending_messages
   - If state==idle: open ClaudeSDKClient and run_turn
   - If state==active: queued for next turn boundary (no interrupt)
   - If state==suspended: resume by session_id
        │
        ▼
7. run_turn (streaming async iterator):
   - tool_use events     → update last_tool_event_at, footer count
   - text_delta events   → update last_token_event_at, buffer for final
   - turn_end            → post final to Discord with footer, persist session_id
        │
        ▼
8. Idle watcher (background):
   - Every 60s, scan sessions
   - If now - latest_activity() > 30min: suspend, free slot
```

## Idle detection contract

A session is idle iff **none** of these happened in the last 30 minutes:

- `tool_use` event streamed from SDK
- `tool_result` event streamed
- text token streamed from agent
- new user message arrived in the channel

A two-hour `npm test && deploy && gh pr checks --watch` stays **active** the
entire time because tool events stream throughout. Only true silence triggers
suspend.

## Budget enforcement

Every turn returns a usage object (input/output/cache tokens, model). Budget
converts to USD using a pricing table, inserts into a sqlite ledger, computes
`spent_today()`. When `spent_today() >= daily_cap`, all active sessions are
paused and `#jojo-audit` gets a notice. The ledger resets at VM-local midnight.

Warnings at 80% / 95% / 100% of cap.

## Network boundary

Tailscale-only. The VM has:
- No firewall rules permitting public ingress
- An ephemeral external IP **only during install** (terraform creates it, the
  installer SSHes in once to bootstrap, then we use tailnet SSH thereafter).
  Optional: release the external IP after install.
- `tailscale up` runs from the VM's startup script using the operator-provided
  authkey, joining the tailnet with hostname `pawpad-vm` and tag `tag:pawpad`.

Outbound is unrestricted (default GCP VPC behavior), so:
- `gateway.discord.gg` ws → Discord events
- `api.anthropic.com` → model calls
- `github.com` → clone/push
- `api.tailscale.com` (if we use it for whois) → fine
