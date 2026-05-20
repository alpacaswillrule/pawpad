# Quartz static-site for the wiki

Quartz publishes the Obsidian vault as a static website. Served on the VM at
`http://pawpad-vm:8080` over Tailscale (no public exposure in the v1 preset).

## Installer setup

The `deploy` step clones https://github.com/jackyzha0/quartz into `quartz/`,
points its content directory at `~/obsidian-vault/wiki/` (so only the curated
wiki is published, not raw sources or per-project scratch), and starts the
`quartz.service` systemd unit which runs `npx quartz serve`.

## Content scope

Published:
- `obsidian-vault/wiki/` (all subdirectories)

NOT published:
- `obsidian-vault/.raw/` (dot-prefixed)
- `obsidian-vault/projects/` (per-channel scratch; sensitive)

The agent's CLAUDE.md instructs it to file cross-project knowledge in `wiki/`,
so what shows up on Quartz is the curated knowledge base, not active work.

## Mobile

Tailscale on the phone + `http://pawpad-vm:8080` in any browser. Add to home
screen for app-like access.
