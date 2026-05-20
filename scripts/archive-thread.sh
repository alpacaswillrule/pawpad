#!/usr/bin/env bash
# Tear down a Discord thread's git worktree. Removes the worktree from git's
# bookkeeping, then moves any leftover files (uncommitted changes etc.) to
# the workspaces archive. Same for the vault folder.
#
# The branch is left intact — if the agent committed work there, it remains
# in the repo for later inspection / PR.
#
# Args:
#   $1  parent channel slug
#   $2  thread slug

set -euo pipefail

CHANNEL_SLUG="${1:?missing channel slug}"
THREAD_SLUG="${2:?missing thread slug}"

WORKSPACES_ROOT="${WORKSPACES_ROOT:-$HOME/projects}"
VAULT_ROOT="${VAULT_ROOT:-$HOME/obsidian-vault}"

MAIN_WORKSPACE="${WORKSPACES_ROOT}/${CHANNEL_SLUG}"
WT_DIR="${WORKSPACES_ROOT}/${CHANNEL_SLUG}-threads/${THREAD_SLUG}"
THREAD_VAULT="${VAULT_ROOT}/projects/${CHANNEL_SLUG}/threads/${THREAD_SLUG}"
TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

if [[ -d "${MAIN_WORKSPACE}/.git" && -d "$WT_DIR" ]]; then
  # `--force` so an uncommitted worktree can still be removed; we'll archive
  # the leftover files below if any survive.
  git -C "${MAIN_WORKSPACE}" worktree remove --force "$WT_DIR" 2>/dev/null || true
  git -C "${MAIN_WORKSPACE}" worktree prune 2>/dev/null || true
fi

# Archive any leftover directory contents (uncommitted files, scratch, etc.).
if [[ -d "$WT_DIR" ]]; then
  mkdir -p "${WORKSPACES_ROOT}/_archived/threads"
  mv "$WT_DIR" \
     "${WORKSPACES_ROOT}/_archived/threads/${CHANNEL_SLUG}-${THREAD_SLUG}-${TIMESTAMP}"
fi

# Archive vault dir too.
if [[ -d "$THREAD_VAULT" ]]; then
  mkdir -p "${VAULT_ROOT}/_archived/threads"
  mv "$THREAD_VAULT" \
     "${VAULT_ROOT}/_archived/threads/${CHANNEL_SLUG}-${THREAD_SLUG}-${TIMESTAMP}"
fi

echo "ok: thread ${CHANNEL_SLUG}/${THREAD_SLUG} archived at ${TIMESTAMP}"
