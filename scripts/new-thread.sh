#!/usr/bin/env bash
# Create a git worktree + vault folder for a Discord thread that belongs to
# a channel project.
#
# Args:
#   $1  parent channel slug (e.g. tachi-extension)
#   $2  thread id           (Discord snowflake; unused for paths but stored
#                            for traceability)
#   $3  thread slug         (e.g. debug-empty-page)
#
# Env:
#   WORKSPACES_ROOT  default $HOME/projects
#   VAULT_ROOT       default $HOME/obsidian-vault
#
# The worktree lives at $WORKSPACES_ROOT/$parent-threads/$thread/, on a new
# branch `thread/<slug>` off main. The parent's main workspace is the source
# of the worktree — `git worktree add` shares git history but isolates working
# files so multiple agents can work on the same repo in parallel.
#
# Idempotent: re-running on an existing worktree is a no-op.

set -euo pipefail

CHANNEL_SLUG="${1:?missing channel slug}"
THREAD_ID="${2:?missing thread id}"
THREAD_SLUG="${3:?missing thread slug}"

WORKSPACES_ROOT="${WORKSPACES_ROOT:-$HOME/projects}"
VAULT_ROOT="${VAULT_ROOT:-$HOME/obsidian-vault}"

MAIN_WORKSPACE="${WORKSPACES_ROOT}/${CHANNEL_SLUG}"
WT_DIR="${WORKSPACES_ROOT}/${CHANNEL_SLUG}-threads/${THREAD_SLUG}"
BRANCH="thread/${THREAD_SLUG}"
THREAD_VAULT="${VAULT_ROOT}/projects/${CHANNEL_SLUG}/threads/${THREAD_SLUG}"

if [[ ! -d "${MAIN_WORKSPACE}/.git" ]]; then
  echo "new-thread.sh: main workspace not initialized: ${MAIN_WORKSPACE}" >&2
  exit 2
fi

mkdir -p "$(dirname "$WT_DIR")"
mkdir -p "$(dirname "$THREAD_VAULT")"
mkdir -p "${THREAD_VAULT}"

# Idempotent worktree creation.
if [[ -d "${WT_DIR}/.git" ]] || [[ -f "${WT_DIR}/.git" ]]; then
  echo "ok: worktree already exists at ${WT_DIR}"
else
  # Detect the main branch name (main or master).
  DEFAULT_BRANCH=$(git -C "${MAIN_WORKSPACE}" symbolic-ref --short HEAD 2>/dev/null || echo main)

  # If the branch already exists (rare — e.g. operator created it manually),
  # check it out as-is. Otherwise create it off the default branch.
  if git -C "${MAIN_WORKSPACE}" rev-parse --verify "${BRANCH}" >/dev/null 2>&1; then
    git -C "${MAIN_WORKSPACE}" worktree add "${WT_DIR}" "${BRANCH}"
  else
    git -C "${MAIN_WORKSPACE}" worktree add -b "${BRANCH}" "${WT_DIR}" "${DEFAULT_BRANCH}"
  fi
fi

# Per-thread CLAUDE.md so the agent knows it's in a worktree.
if [[ ! -f "${WT_DIR}/CLAUDE.md" ]]; then
  {
    printf '# Thread workspace\n\n'
    printf 'You are running in a git worktree off the parent channel project.\n\n'
    printf 'Worktree:  `%s`\n' "$WT_DIR"
    printf 'Branch:    `%s`\n' "$BRANCH"
    printf 'Thread ID: `%s`\n\n' "$THREAD_ID"
    printf 'Multiple agents may be working on this repo in parallel — '
    printf 'commit and push to your branch and open a PR rather than '
    printf 'touching `main` directly.\n'
  } > "${WT_DIR}/CLAUDE.md"
fi

# Vault plan stub for the thread.
if [[ ! -f "${THREAD_VAULT}/plan.md" ]]; then
  TODAY=$(date -u +%Y-%m-%d)
  NOW=$(date -u +%Y-%m-%dT%H:%M:%S)
  {
    printf -- '---\n'
    printf 'type: thread-plan\n'
    printf 'title: "%s/%s"\n' "$CHANNEL_SLUG" "$THREAD_SLUG"
    printf 'thread_id: "%s"\n' "$THREAD_ID"
    printf 'branch: %s\n' "$BRANCH"
    printf 'created: %s\n' "$TODAY"
    printf 'updated: %s\n' "$NOW"
    printf 'status: planning\n'
    printf -- '---\n\n'
    printf '# Thread: %s/%s\n\n' "$CHANNEL_SLUG" "$THREAD_SLUG"
    printf 'Working on branch `%s` off `%s`.\n\n' "$BRANCH" "$CHANNEL_SLUG"
    printf '## Goal\n_(set by the first user message in the thread)_\n\n'
    printf '## Notes\n\n'
  } > "${THREAD_VAULT}/plan.md"
fi

echo "ok: worktree=${WT_DIR} branch=${BRANCH} vault=${THREAD_VAULT}"
