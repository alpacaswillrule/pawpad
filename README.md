# pawpad

Turn a Discord guild into a multi-project Claude Code workstation.

One GCP VM hosts a Discord bot (Jojo) that spawns isolated Claude Agent SDK sessions per channel. Each channel = one project = one workspace + one private GitHub repo + one Obsidian notes folder. Notes follow the llm-wiki methodology and sync to your phone via Obsidian LiveSync.

Close your laptop. Work continues.

## Quick start

```bash
git clone git@github.com:alpacaswillrule/pawpad.git
cd pawpad
./install.sh
```

The TUI installer walks through every credential. See [`docs/creds.md`](docs/creds.md) for what you'll need to gather first.

## Status

**v0 — scaffolding.** Spec is locked, code is stubs. See [`SPEC.md`](SPEC.md) for the design and [`docs/creds.md`](docs/creds.md) for prerequisites.

## Docs

- [`SPEC.md`](SPEC.md) — full design (read this first)
- [`docs/creds.md`](docs/creds.md) — credentials to gather before running the installer
- [`docs/architecture.md`](docs/architecture.md) — diagrams + sequence flows
- [`docs/runbook.md`](docs/runbook.md) — common ops
