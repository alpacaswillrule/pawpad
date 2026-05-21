# pawpad — spec

> Source of truth. The agent itself reads this when extending pawpad. Keep it accurate.

## What it is

A self-hostable system that turns a Discord guild into a multi-project Claude Code workstation. One GCP VM hosts a Discord bot ("Jojo") that spawns isolated Claude Agent SDK sessions per channel, each with full filesystem + shell + git access. Notes and plans live in a shared Obsidian vault following the llm-wiki methodology, synced to mobile via LiveSync and published as a read-only website via Quartz.

User-facing communication happens entirely through Discord. The user can close their laptop; agents keep running on the VM until their tasks finish.

## Stack

| Layer | Choice |
|---|---|
| Host | GCP Compute Engine, Ubuntu 24.04 LTS, user picks region/disks at install |
| Storage | Two-tier: **hot** pd-balanced SSD (default 200GB) for live workspaces; **cold** pd-standard HDD (default 1TB) for `_archived/`. Cold disk is optional — set `cold_disk_size_gb=0` for single-tier. |
| Network | Tailscale-only (no public ports); SSH + Obsidian web served over tailnet |
| Orchestrator | Python: `discord.py` + `claude-agent-sdk`, systemd-managed |
| Agent | Claude Agent SDK with `permission_mode=bypassPermissions` |
| Auth (Claude) | `ANTHROPIC_API_KEY` in `.env` |
| Notes | Shared Obsidian vault + Self-Hosted LiveSync (CouchDB) + Quartz |
| Notes methodology | `claude-obsidian` plugin family (llm-wiki) |
| Installer | Local TUI (`rich` + `textual`) |

## Concurrency + budget

- **Soft cap: 8 simultaneously active agent sessions.** Overflow queued FIFO.
- **Idle = 30min with zero agent activity** (no tool calls, no streamed tokens, no incoming messages). Long-running work (hours of `npm test`, `gh pr checks --watch`, etc.) does NOT count as idle as long as tools/tokens stream. On idle, suspend; resume by `session_id` on next message.
- **Budget**: `/budget <amount>` Discord command. Default $500/day. Hard pause on hit; resumes at VM midnight. Warnings at 80% / 95% / 100% posted to `#jojo-audit`.

## Network

Tailscale-only by default. Inbound public traffic: none. Outbound is unrestricted, so:
- Discord gateway (outbound websocket) works fine
- Anthropic API works fine
- GitHub clone/push works fine

The Obsidian Quartz site is reachable only over tailnet. Mobile access requires the Tailscale app. Switch to public-web preset (open 443 + Caddy) only if a public notes URL is wanted.

## Channels

Bot only watches channels under a Discord category named **`projects`**. Channels elsewhere (`#general`, voice, etc.) are ignored.

### Channel lifecycle

1. **Create channel under `projects`** → bot:
   - Creates `~/projects/{slug}/`
   - `gh repo create alpacaswillrule/{slug} --private`
   - Creates `obsidian-vault/projects/{slug}/plan.md` from template
   - Opens Claude Agent SDK session for that workspace
   - If the channel topic is set, it becomes the agent's initial prompt; otherwise the agent waits for the first user message
   - Posts welcome message with workspace path + GitHub URL

2. **User messages** → routed to the channel's SDK session and **queued for the agent's next turn boundary**. Mid-turn messages are NOT injected immediately; they appear in the next turn's input. No interrupt. (This mirrors how additional messages work in interactive Claude Code.)

3. **Agent output** → assistant text is **streamed to Discord live** as the SDK emits `TextBlock`s. The first `TextBlock` of a turn posts a new Discord message; subsequent blocks edit it in place (rate-limited to ~1 edit/sec). When the message hits ~1900 chars it spills to a new message on a clean boundary. The turn ends with a `ResultMessage` (or a 60-second inactivity timeout) and the footer is appended: `• 14 tools · 47s · $0.23`. Code blocks larger than 1800 chars are attached as files instead of inlined.

4. **Idle 30min** (per above definition) → suspend session. Concurrency slot freed for queued channels.

5. **Channel deleted** → workspace + Obsidian project folder moved to `~/projects/_archived/{slug}-{timestamp}/`. The GitHub repo is untouched. Audit-log entry posted.

### Threads → parallel agents

Each new Discord thread under a watched channel spawns its own Claude Agent
SDK session in a **git worktree** off the parent channel's repo, on a new
branch `thread/<slug>` — so multiple agents can work on the same project in
parallel without stepping on each other.

```
~/projects/tachi-extension/                    ← channel session (main branch)
~/projects/tachi-extension-threads/
    ├── debug-empty-page/                      ← thread 1 worktree (branch thread/debug-empty-page)
    └── pr-37-rebase/                          ← thread 2 worktree (branch thread/pr-37-rebase)
```

- **`on_thread_create`** → `scripts/new-thread.sh {channel-slug} {thread-id} {thread-slug}` creates the worktree + a `thread/<slug>` branch, scaffolds `obsidian-vault/projects/{channel}/threads/{thread}/plan.md`, and (if the thread's starter message has content) enqueues it as the agent's initial prompt.
- **Sessions are keyed by Discord ID** — channel IDs and thread IDs are globally unique, so the `SessionManager.sessions` dict holds both types.
- **The 8-slot concurrency cap counts all sessions** — channel and thread sessions compete for the same budget. Idle sessions suspend after 30 min.
- **`on_thread_archive`** (Discord-side archive) → pauses the session, releases the slot. **`on_thread_unarchive`** → resumes.
- **`on_thread_delete`** → `scripts/archive-thread.sh` removes the worktree (`git worktree remove --force`), moves any leftover files to `~/projects/_archived/threads/`. The thread's branch is **not** deleted — committed work is preserved for later inspection / PR.
- **Agents in threads are instructed to push to their branch and open a PR rather than touching `main`** (via per-thread `CLAUDE.md` written by `new-thread.sh`).

### Authorization

Any user in the guild who can post in a watched channel can interact with the bot. No per-user gating in v1. Slash commands (`/budget` etc.) are guild-wide, not per-user.

## Slash commands (v1)

| Command | Effect |
|---|---|
| `/budget <amount>` | Set daily $ cap. Default $500. |
| `/status` | This channel's agent state (active/idle/suspended/queued) + today's spend + queue position. |
| `/spend` | Per-channel + global spend breakdown for today & this week. |
| `/pause` | Park this channel's agent. Frees the concurrency slot. Won't act on messages until resumed. |
| `/resume` | Unpark. |
| `/archive` | Archive workspace + Obsidian folder + stop agent, but leave Discord channel intact. |
| `/claude-instructions "..."` | Append instructions to this channel's CLAUDE.md (in `~/projects/{slug}/CLAUDE.md`). Agent picks them up on next turn. |
| `/claude-instructions global "..."` | Append to VM-wide CLAUDE.md (affects every channel's agent). |
| `/clone <repo-url>` | Replace this channel's workspace with a `git clone` of an existing repo. Refuses if the workspace has uncommitted changes or any commits beyond the initial scaffold. Drops the SDK session_id so the next message starts a fresh agent in the clone. The empty `alpacaswillrule/{slug}` repo created at channel-init is **not** auto-deleted — operator deletes manually via `gh repo delete` if wanted. Only valid in channel sessions, not threads. |

Deferred to v1.1+: `/handoff` (manual SSH takeover), `/verbose <level>`, multi-user authorization scoping.

## Audit channel

Bot auto-creates `#jojo-audit` on first run. Posts:
- Daily spend summary (rolls at VM midnight)
- Budget warnings (80% / 95% / 100%)
- Agent crashes + stack traces
- Channel archives
- New channel + repo creation events
- Suspends/resumes (debug; toggleable)

## CLAUDE.md hierarchy

Three layers, merged at session start:

1. **VM-wide**: `~/pawpad/claude/CLAUDE.md` — Obsidian/wiki conventions, git defaults, Discord etiquette.
2. **Per-channel**: `~/projects/{slug}/CLAUDE.md` — appended to by `/claude-instructions` in that channel.
3. **Auto-injected (per session)**: identity + context — channel name, workspace path, Obsidian project folder, agent's role. Not a file; injected programmatically by the bot when opening the SDK session.

### VM-wide CLAUDE.md content

- **Obsidian + wiki (mandatory)**: plan in `obsidian-vault/projects/{slug}/plan.md`, file entities/concepts/domains in shared `obsidian-vault/wiki/`, update `wiki/hot.md` after significant work, use `claude-obsidian:*` sub-skills (`wiki-ingest`, `wiki-query`, `wiki-lint`, `wiki-fold`).
- **Git**: default to private repos (`gh repo create --private`), conventional commit messages, feature branches with draft PRs (do not push directly to `main`), only make a repo public if the user explicitly asks.
- **Discord etiquette**: keep replies concise (Discord 2000-char limit), chunk long outputs, attach code blocks > 1800 chars as files rather than inlining, all user-facing text goes via the `discord_send` MCP tool (the bot also auto-forwards final turn text).

## Repo layout

```
pawpad/
├── SPEC.md                      this file
├── README.md                    quickstart
├── install.sh                   entry point — bootstraps Python env + runs TUI
├── requirements.txt             installer deps
├── pyproject.toml               package metadata for the on-VM bot
├── .gitignore
├── installer/
│   ├── __init__.py
│   ├── tui.py                   rich/textual entry
│   └── steps/                   one module per install step
│       ├── __init__.py
│       ├── welcome.py
│       ├── gcp_auth.py
│       ├── gcp_project.py
│       ├── vm_specs.py
│       ├── tailscale.py
│       ├── github.py
│       ├── discord.py
│       ├── anthropic.py
│       ├── obsidian.py
│       ├── deploy.py
│       └── finalize.py
├── bot/
│   ├── __init__.py
│   ├── main.py                  discord.py entry
│   ├── sessions.py              per-channel SDK sessions, idle tracker, queue
│   ├── slash.py                 /budget /status /spend /pause /resume /archive /claude-instructions
│   ├── budget.py                spend ledger, hard-pause
│   ├── audit.py                 #jojo-audit poster
│   ├── output.py                Discord output formatting (chunking, attachments, footers)
│   └── mcp/
│       ├── __init__.py
│       └── discord_send.py      in-process MCP server exposing discord_send(text)
├── claude/
│   ├── CLAUDE.md                VM-wide system prompt
│   ├── settings.json            hooks + bypassPermissions
│   ├── skills/                  copied from ~/.claude/skills/ during install
│   └── agents/
├── obsidian/
│   ├── vault-template/          starter vault scaffold
│   │   ├── CLAUDE.md            schema + ingest/query rules (from llm-wiki)
│   │   ├── wiki/
│   │   │   ├── index.md
│   │   │   ├── log.md
│   │   │   ├── hot.md
│   │   │   ├── overview.md
│   │   │   ├── sources/
│   │   │   ├── entities/_index.md
│   │   │   ├── concepts/_index.md
│   │   │   ├── domains/_index.md
│   │   │   ├── comparisons/
│   │   │   ├── questions/
│   │   │   └── meta/
│   │   ├── projects/            per-channel subfolders live here
│   │   └── .raw/                source documents
│   └── livesync/
│       ├── docker-compose.yml   CouchDB
│       └── README.md
├── quartz/
│   └── README.md                quartz config + build instructions
├── infra/
│   └── terraform/
│       ├── main.tf              VM + disk + firewall + tailscale auth
│       ├── variables.tf
│       └── outputs.tf
├── systemd/
│   ├── jojo-bot.service
│   ├── livesync.service
│   └── quartz.service
├── scripts/
│   ├── new-project.sh           per-channel setup (workspace + gh repo + obsidian folder)
│   ├── archive-project.sh
│   ├── snapshot.sh              disk snapshot to GCS
│   └── teardown.sh
└── docs/
    ├── creds.md                 credential gathering walkthrough
    ├── architecture.md          diagrams + sequence flows
    └── runbook.md               common ops (restart bot, rotate key, view logs)
```

## Installer flow (TUI, `rich` + `textual`)

1. **Welcome** — what's about to happen, ~15 min estimate
2. **GCP auth** — link to console, paste service-account JSON path or run `gcloud auth login`
3. **GCP project / region / zone** — picker with region latency hints
4. **VM specs** — machine type dropdown, disk size, disk type radio (pd-balanced default)
5. **Tailscale** — link to admin console, paste authkey
6. **GitHub** — `gh auth login` device flow; verifies push access to `alpacaswillrule`
7. **Discord bot** — step-by-step dev portal instructions, paste bot token + guild ID, verifies bot can join
8. **Anthropic key** — paste, hit endpoint to verify
9. **Obsidian LiveSync** — generate or paste passphrase
10. **Confirm + deploy** — summary, then live progress: Terraform → SSH → `install-vm.sh` → systemd start → smoke test (bot joins guild, creates `#jojo-audit`)
11. **Done** — print Tailscale IP, Quartz URL on tailnet, instructions to create first `projects/...` channel

## Out of scope for v1 (deferred)

- Local-test daemon (PR-based pattern is the workflow for now)
- Backups to GCS (snapshot script ships, schedule is manual)
- Cost dashboards beyond `/spend`
- Multi-user authorization scoping (per-user permissions)
- Public Quartz on a custom domain
- Claude-code-harness plugin auto-install (user can manually `/plugin install` from `Chachamaru127/claude-code-harness`)
- `/handoff` manual SSH takeover with bot pause
- `/verbose <level>` per-channel tool-call visibility toggle

## Design tradeoffs to remember

- **bypassPermissions**: agents can do anything the VM user can. User accepts full risk. Limit blast radius via the VM boundary itself, not via Claude permissions.
- **Tailscale-only**: secure by default. Cost: every user must run Tailscale on every device to access the VM web UI.
- **Single-guild**: keeps the auth model trivial. Multi-guild is achievable later but not free.
- **Queue, no interrupt**: prevents destructive mid-task interruptions. Cost: user must wait for current turn to end (usually seconds).
- **Shared vault, not per-channel**: knowledge compounds across projects. Cost: a misbehaving agent in one channel can pollute the shared wiki — mitigated by llm-wiki's lint sub-skill.
- **API key, not Claude Max**: scales to many parallel sessions, billable per token, capable of hard budget enforcement. Cost: pay per token.
