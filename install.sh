#!/usr/bin/env bash
# pawpad installer entry point.
#
# Runs locally on the operator's machine. Bootstraps a Python venv with the
# installer's dependencies, then hands off to the TUI in installer/tui.py.
#
# The installer itself walks through credential gathering, provisions the GCP
# VM, and SSHes in to run the on-VM install. Nothing here runs on the VM.

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
VENV_DIR="${REPO_ROOT}/.venv"
PYTHON_BIN="${PYTHON_BIN:-python3}"

bold()  { printf "\033[1m%s\033[0m\n" "$*"; }
green() { printf "\033[32m%s\033[0m\n" "$*"; }
red()   { printf "\033[31m%s\033[0m\n" "$*" >&2; }

require_cmd() {
  if ! command -v "$1" >/dev/null 2>&1; then
    red "Missing required command: $1"
    red "Install it and re-run ./install.sh"
    exit 1
  fi
}

bold "pawpad installer"
echo "Repo: ${REPO_ROOT}"
echo

# --- prerequisites -----------------------------------------------------------

require_cmd "${PYTHON_BIN}"
require_cmd gh
require_cmd gcloud
require_cmd terraform
require_cmd tailscale

# --- venv --------------------------------------------------------------------

if [[ ! -d "${VENV_DIR}" ]]; then
  bold "Creating Python venv at ${VENV_DIR}"
  "${PYTHON_BIN}" -m venv "${VENV_DIR}"
fi

# shellcheck disable=SC1091
source "${VENV_DIR}/bin/activate"

bold "Installing installer dependencies"
pip install --quiet --upgrade pip
pip install --quiet -r "${REPO_ROOT}/requirements.txt"

# --- launch TUI --------------------------------------------------------------

green "Launching installer..."
exec python -m installer.tui "$@"
