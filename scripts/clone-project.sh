#!/usr/bin/env bash
# Replace a channel's workspace with a clone of an existing repo.
#
# Args:
#   $1  channel slug
#   $2  repository URL (HTTPS or SSH)
#
# Env:
#   WORKSPACES_ROOT  default $HOME/projects
#   VAULT_ROOT       default $HOME/obsidian-vault
#   GH_OWNER         default alpacaswillrule
#
# Safety: refuses to clobber a workspace that has uncommitted changes OR
# more than the single initial scaffold commit ("chore: init <slug>"). Run
# `/archive` first if you really want to start over.

set -euo pipefail

SLUG="${1:?missing slug}"
REPO_URL="${2:?missing repo URL}"

WORKSPACES_ROOT="${WORKSPACES_ROOT:-$HOME/projects}"
VAULT_ROOT="${VAULT_ROOT:-$HOME/obsidian-vault}"
GH_OWNER="${GH_OWNER:-alpacaswillrule}"

WS="${WORKSPACES_ROOT}/${SLUG}"
VAULT_PROJ="${VAULT_ROOT}/projects/${SLUG}"

# --- validate the URL looks plausible ---------------------------------------

if [[ ! "$REPO_URL" =~ ^(https?://|git@|ssh://) ]]; then
  echo "clone-project.sh: '$REPO_URL' doesn't look like a clonable URL" >&2
  exit 2
fi

# --- check the workspace is safe to clobber ---------------------------------

if [[ -d "${WS}/.git" ]]; then
  cd "$WS"

  if [[ -n "$(git status --porcelain)" ]]; then
    echo "clone-project.sh: workspace has uncommitted changes — refusing to clobber" >&2
    git status --short >&2
    exit 3
  fi

  commit_count=$(git rev-list --count HEAD 2>/dev/null || echo 0)
  if [[ "$commit_count" -gt 1 ]]; then
    echo "clone-project.sh: workspace has $commit_count commits beyond the initial scaffold — refusing" >&2
    echo "if you really want to wipe this workspace, run /archive first then create a new channel" >&2
    exit 4
  fi
fi

# --- wipe + clone -----------------------------------------------------------

# Remove the current workspace contents but keep the parent directory.
rm -rf "$WS"

# Shallow clone is fast and uses ~10x less disk for typical history.
# Drop --depth=1 if the user later needs full history (they can `git fetch --unshallow`).
git clone --depth 1 "$REPO_URL" "$WS"

# Configure identity for any commits the agent makes here.
git -C "$WS" config user.email "jojo@pawpad.local"
git -C "$WS" config user.name  "Jojo"

# --- per-channel CLAUDE.md (replace the scaffold one) -----------------------

cat > "${WS}/CLAUDE.md" <<EOF
# Project-specific instructions

This workspace is a clone of \`${REPO_URL}\`.

The agent should respect the existing project conventions (read the repo's
own README, CONTRIBUTING, etc. first). Branches and PR workflow follow the
parent project's norms unless overridden here.

Appended to by \`/claude-instructions\` from the bound Discord channel.
The VM-wide CLAUDE.md at /opt/pawpad/claude/CLAUDE.md applies first; this
layers on top.
EOF

# --- vault project folder (idempotent) --------------------------------------

mkdir -p "${VAULT_PROJ}"
if [[ ! -f "${VAULT_PROJ}/plan.md" ]]; then
  TODAY=$(date -u +%Y-%m-%d)
  NOW=$(date -u +%Y-%m-%dT%H:%M:%S)
  {
    printf -- '---\n'
    printf 'type: project-plan\n'
    printf 'title: "%s (cloned)"\n' "$SLUG"
    printf 'source: %s\n' "$REPO_URL"
    printf 'created: %s\n' "$TODAY"
    printf 'updated: %s\n' "$NOW"
    printf 'status: planning\n'
    printf -- '---\n\n'
    printf '# %s — Plan\n\n' "$SLUG"
    printf 'Working on a clone of `%s`.\n\n' "$REPO_URL"
    printf '## Status\n- Workspace replaced: %s\n\n' "$TODAY"
    printf '## Plan\n_(filled in by the agent on first turn)_\n'
  } > "${VAULT_PROJ}/plan.md"
fi

echo "ok: cloned $REPO_URL into $WS"
