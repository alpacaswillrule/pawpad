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

# Fail-fast if gh isn't authed — otherwise gh would hang on a stdin prompt.
if ! gh auth status >/dev/null 2>&1; then
  echo "new-project.sh: gh CLI is not authenticated. SSH in and run 'gh auth login'." >&2
  exit 2
fi

mkdir -p "${WS}" "${VAULT_PROJ}"

# --- workspace git init + remote create (private) ----------------------------

if [[ ! -d "${WS}/.git" ]]; then
  git -C "${WS}" init -q -b main
  # Write README without heredoc expansion of $TOPIC so a topic like `$(rm -rf /)`
  # or backticks can't execute anything.
  {
    printf '# %s\n\n' "$SLUG"
    if [[ -n "$TOPIC" ]]; then
      printf '%s\n\n' "$TOPIC"
    else
      printf 'Project workspace for Discord channel #%s.\n\n' "$SLUG"
    fi
    printf 'Notes live in `~/obsidian-vault/projects/%s/`.\n' "$SLUG"
  } > "${WS}/README.md"
  git -C "${WS}" add README.md
  git -C "${WS}" -c user.email="jojo@pawpad.local" -c user.name="Jojo" \
      commit -q -m "chore: init ${SLUG}"
fi

if ! gh repo view "${GH_OWNER}/${SLUG}" >/dev/null 2>&1; then
  gh repo create "${GH_OWNER}/${SLUG}" --private --source="${WS}" --remote=origin --push </dev/null
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
# All heredocs use 'EOF' (quoted) and we printf in any user-supplied values
# so a hostile channel topic can't execute as the bot user.

if [[ ! -f "${VAULT_PROJ}/plan.md" ]]; then
  TODAY=$(date -u +%Y-%m-%d)
  NOW=$(date -u +%Y-%m-%dT%H:%M:%S)
  TOPIC_BLOCK="${TOPIC:-_(no channel topic set yet)_}"
  {
    printf -- '---\n'
    printf 'type: project-plan\n'
    printf 'title: "%s"\n' "$SLUG"
    printf 'created: %s\n' "$TODAY"
    printf 'updated: %s\n' "$NOW"
    printf 'status: planning\n'
    printf -- '---\n\n'
    printf '# %s — Plan\n\n' "$SLUG"
    printf '%s\n\n' "$TOPIC_BLOCK"
    printf '## Status\n- Created: %s\n- Repo: `%s/%s` (private)\n\n' "$TODAY" "$GH_OWNER" "$SLUG"
    printf '## Plan\n_(filled in by the agent on first turn)_\n\n'
    printf '## Decisions\n_(see decisions.md)_\n'
  } > "${VAULT_PROJ}/plan.md"
  touch "${VAULT_PROJ}/decisions.md" "${VAULT_PROJ}/notes.md"
fi

echo "ok: workspace=${WS} vault=${VAULT_PROJ} repo=${GH_OWNER}/${SLUG}"
