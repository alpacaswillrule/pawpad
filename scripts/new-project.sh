#!/usr/bin/env bash
# Create a new project workspace for a Discord channel.
#
# Called by the bot on `on_guild_channel_create`. Idempotent — re-running on
# an existing slug is safe (skips already-done steps).
#
# Args:
#   $1  channel slug (lowercase, hyphens, no spaces)
#   $2  channel topic (optional, used for initial agent prompt + README)
#
# Env:
#   GH_OWNER             default: alpacaswillrule
#   WORKSPACES_ROOT      default: $HOME/projects
#   VAULT_ROOT           default: $HOME/obsidian-vault

set -euo pipefail

SLUG="${1:?missing slug}"
TOPIC="${2:-}"

GH_OWNER="${GH_OWNER:-alpacaswillrule}"
WORKSPACES_ROOT="${WORKSPACES_ROOT:-$HOME/projects}"
VAULT_ROOT="${VAULT_ROOT:-$HOME/obsidian-vault}"

WS="${WORKSPACES_ROOT}/${SLUG}"
VAULT_PROJ="${VAULT_ROOT}/projects/${SLUG}"

mkdir -p "${WS}" "${VAULT_PROJ}"

# --- workspace git init + remote create (private) ----------------------------

if [[ ! -d "${WS}/.git" ]]; then
  git -C "${WS}" init -q -b main
  cat > "${WS}/README.md" <<EOF
# ${SLUG}

${TOPIC:-Project workspace for Discord channel #${SLUG}.}

Notes live in \`~/obsidian-vault/projects/${SLUG}/\`.
EOF
  git -C "${WS}" add README.md
  git -C "${WS}" -c user.email="jojo@pawpad.local" -c user.name="Jojo" \
      commit -q -m "chore: init ${SLUG}"
fi

if ! gh repo view "${GH_OWNER}/${SLUG}" >/dev/null 2>&1; then
  gh repo create "${GH_OWNER}/${SLUG}" --private --source="${WS}" --remote=origin --push
fi

# --- per-channel CLAUDE.md (empty, ready for /claude-instructions appends) ---

if [[ ! -f "${WS}/CLAUDE.md" ]]; then
  cat > "${WS}/CLAUDE.md" <<'EOF'
# Project-specific instructions

This file is appended to by `/claude-instructions` from the bound Discord channel.
The VM-wide CLAUDE.md at /opt/pawpad/claude/CLAUDE.md applies first; everything
here layers on top.
EOF
fi

# --- vault project folder ----------------------------------------------------

if [[ ! -f "${VAULT_PROJ}/plan.md" ]]; then
  cat > "${VAULT_PROJ}/plan.md" <<EOF
---
type: project-plan
title: "${SLUG}"
created: $(date -u +%Y-%m-%d)
updated: $(date -u +%Y-%m-%dT%H:%M:%S)
status: planning
---

# ${SLUG} — Plan

${TOPIC:-_(no channel topic set yet)_}

## Status
- Created: $(date -u +%Y-%m-%d)
- Repo: \`${GH_OWNER}/${SLUG}\` (private)

## Plan
_(filled in by the agent on first turn)_

## Decisions
_(see decisions.md)_
EOF
  touch "${VAULT_PROJ}/decisions.md" "${VAULT_PROJ}/notes.md"
fi

echo "ok: workspace=${WS} vault=${VAULT_PROJ} repo=${GH_OWNER}/${SLUG}"
