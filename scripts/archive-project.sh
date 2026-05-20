#!/usr/bin/env bash
# Archive a project workspace (moves workspace + Obsidian project dir to _archived/).
# Does NOT delete the GitHub repo.

set -euo pipefail

SLUG="${1:?missing slug}"
WORKSPACES_ROOT="${WORKSPACES_ROOT:-$HOME/projects}"
VAULT_ROOT="${VAULT_ROOT:-$HOME/obsidian-vault}"

TIMESTAMP="$(date -u +%Y%m%dT%H%M%SZ)"

mkdir -p "${WORKSPACES_ROOT}/_archived"
mkdir -p "${VAULT_ROOT}/_archived"

if [[ -d "${WORKSPACES_ROOT}/${SLUG}" ]]; then
  mv "${WORKSPACES_ROOT}/${SLUG}" "${WORKSPACES_ROOT}/_archived/${SLUG}-${TIMESTAMP}"
fi

if [[ -d "${VAULT_ROOT}/projects/${SLUG}" ]]; then
  mv "${VAULT_ROOT}/projects/${SLUG}" "${VAULT_ROOT}/_archived/${SLUG}-${TIMESTAMP}"
fi

echo "ok: archived ${SLUG} -> ${SLUG}-${TIMESTAMP}"
