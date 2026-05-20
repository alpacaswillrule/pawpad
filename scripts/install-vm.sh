#!/usr/bin/env bash
# Runs ON the VM via SSH from the operator's installer. Receives secrets
# through stdin (a JSON blob) so they never appear in process args or logs.
#
# Idempotent — safe to re-run. Picks up where any prior partial run left off.
#
# Stdin format (JSON):
# {
#   "DISCORD_TOKEN":           "...",
#   "DISCORD_GUILD_ID":        "...",
#   "ANTHROPIC_API_KEY":       "...",
#   "COUCHDB_USER":            "...",
#   "COUCHDB_PASSWORD":        "...",
#   "LIVESYNC_PASSPHRASE":     "...",
#   "PAWPAD_GH_OWNER":         "alpacaswillrule",
#   "PAWPAD_DEFAULT_DAILY_CAP_USD": "500"
# }

set -euo pipefail

# Wait for startup script to finish (it sets the marker).
MARKER=/var/lib/pawpad/.bootstrapped
for _ in $(seq 1 60); do
  [[ -f "$MARKER" ]] && break
  echo "waiting for startup script… ($(date -u))"
  sleep 10
done

if [[ ! -f "$MARKER" ]]; then
  echo "startup script never finished, see /var/log/pawpad-startup.log" >&2
  exit 1
fi

PAWPAD_USER=pawpad
PAWPAD_HOME=/home/${PAWPAD_USER}

# --- read secrets ------------------------------------------------------------

SECRETS_JSON=$(cat)
get() { jq -r --arg k "$1" '.[$k] // ""' <<<"$SECRETS_JSON"; }

DISCORD_TOKEN=$(get DISCORD_TOKEN)
DISCORD_GUILD_ID=$(get DISCORD_GUILD_ID)
ANTHROPIC_API_KEY=$(get ANTHROPIC_API_KEY)
COUCHDB_USER=$(get COUCHDB_USER)
COUCHDB_PASSWORD=$(get COUCHDB_PASSWORD)
LIVESYNC_PASSPHRASE=$(get LIVESYNC_PASSPHRASE)
PAWPAD_GH_OWNER=$(get PAWPAD_GH_OWNER)
PAWPAD_DEFAULT_DAILY_CAP_USD=$(get PAWPAD_DEFAULT_DAILY_CAP_USD)
GH_TOKEN=$(get GH_TOKEN)

for var in DISCORD_TOKEN DISCORD_GUILD_ID ANTHROPIC_API_KEY \
           COUCHDB_USER COUCHDB_PASSWORD LIVESYNC_PASSPHRASE; do
  if [[ -z "${!var}" ]]; then
    echo "missing required secret: $var" >&2
    exit 1
  fi
done

PAWPAD_GH_OWNER=${PAWPAD_GH_OWNER:-alpacaswillrule}
PAWPAD_DEFAULT_DAILY_CAP_USD=${PAWPAD_DEFAULT_DAILY_CAP_USD:-500}

# --- write bot .env (root-readable only) -------------------------------------
# Use printf instead of heredoc so secret values containing $ aren't expanded.

write_env() {
  local path="$1"
  shift
  sudo install -m 0600 -o ${PAWPAD_USER} -g ${PAWPAD_USER} /dev/null "$path"
  local kv
  for kv in "$@"; do
    printf '%s\n' "$kv" | sudo tee -a "$path" >/dev/null
  done
}

ENV_PATH=/opt/pawpad/.env
write_env "$ENV_PATH" \
  "DISCORD_TOKEN=$DISCORD_TOKEN" \
  "DISCORD_GUILD_ID=$DISCORD_GUILD_ID" \
  "ANTHROPIC_API_KEY=$ANTHROPIC_API_KEY" \
  "PAWPAD_WORKSPACES=$PAWPAD_HOME/projects" \
  "PAWPAD_VAULT=$PAWPAD_HOME/obsidian-vault" \
  "PAWPAD_GH_OWNER=$PAWPAD_GH_OWNER" \
  "PAWPAD_DEFAULT_DAILY_CAP_USD=$PAWPAD_DEFAULT_DAILY_CAP_USD" \
  "COUCHDB_USER=$COUCHDB_USER" \
  "COUCHDB_PASSWORD=$COUCHDB_PASSWORD"

# --- write livesync .env (docker-compose reads this) -------------------------

LIVESYNC_ENV=/opt/pawpad/obsidian/livesync/.env
write_env "$LIVESYNC_ENV" \
  "COUCHDB_USER=$COUCHDB_USER" \
  "COUCHDB_PASSWORD=$COUCHDB_PASSWORD"

# --- save the LiveSync E2E passphrase locally so the operator can retrieve it -
# (the passphrase is client-side; CouchDB itself doesn't use it)

PASSPHRASE_PATH=$PAWPAD_HOME/.pawpad/livesync-passphrase.txt
sudo -u $PAWPAD_USER mkdir -p "$(dirname "$PASSPHRASE_PATH")"
sudo install -m 0600 -o ${PAWPAD_USER} -g ${PAWPAD_USER} /dev/null "$PASSPHRASE_PATH"
printf '%s\n' "$LIVESYNC_PASSPHRASE" | sudo tee "$PASSPHRASE_PATH" >/dev/null

# --- seed the obsidian vault if missing --------------------------------------

if [[ ! -d "${PAWPAD_HOME}/obsidian-vault/wiki" ]]; then
  sudo -u ${PAWPAD_USER} cp -r /opt/pawpad/obsidian/vault-template "${PAWPAD_HOME}/obsidian-vault"
fi

sudo -u ${PAWPAD_USER} mkdir -p "${PAWPAD_HOME}/projects"

# --- install systemd units ---------------------------------------------------
# v1: bot + livesync. Quartz is deferred (no package.json yet).

for unit in jojo-bot.service livesync.service; do
  sudo install -m 0644 "/opt/pawpad/systemd/$unit" "/etc/systemd/system/$unit"
done

sudo systemctl daemon-reload

# --- gh auth on the VM -------------------------------------------------------
# Reuse the operator's gh token (passed through state). The bot needs
# `gh repo create` to scaffold per-channel private repos.

if [[ -n "$GH_TOKEN" ]]; then
  # pipe token via stdin so it never appears in argv / ps
  printf '%s' "$GH_TOKEN" | sudo -u ${PAWPAD_USER} gh auth login --hostname github.com --with-token
  sudo -u ${PAWPAD_USER} gh auth setup-git 2>/dev/null || true
  echo "gh authed on VM"
else
  echo "NOTE: no GH_TOKEN provided. SSH in and run 'gh auth login' before creating channels."
fi

# --- start the bot -----------------------------------------------------------

sudo systemctl enable --now livesync.service
sudo systemctl enable --now jojo-bot.service

# --- smoke test: wait for bot to come online --------------------------------

echo "waiting for bot to log online…"
for _ in $(seq 1 30); do
  if sudo journalctl -u jojo-bot.service --since "1 minute ago" 2>/dev/null \
        | grep -q "logged in as"; then
    echo "bot online"
    exit 0
  fi
  sleep 2
done

echo "bot didn't come online within 60s. Check: journalctl -u jojo-bot.service" >&2
exit 1
