#!/usr/bin/env bash
# Take a GCP disk snapshot of the VM's data disk. Run from operator's laptop or VM.
#
# Args:
#   $1  snapshot label (optional, default: pawpad-$(date))

set -euo pipefail

LABEL="${1:-pawpad-$(date -u +%Y%m%dT%H%M%SZ)}"

# Pull config from ~/.pawpad/runtime.json (written at install time)
RUNTIME="$HOME/.pawpad/runtime.json"
if [[ ! -f "${RUNTIME}" ]]; then
  echo "missing ${RUNTIME} — run from a machine that has the installer state" >&2
  exit 1
fi

PROJECT=$(jq -r '.gcp_project_id' "${RUNTIME}")
ZONE=$(jq -r '.gcp_zone' "${RUNTIME}")
DISK=$(jq -r '.disk_name // "pawpad-vm-data"' "${RUNTIME}")

gcloud compute disks snapshot "${DISK}" \
  --project="${PROJECT}" \
  --zone="${ZONE}" \
  --snapshot-names="${LABEL}"

echo "ok: snapshot ${LABEL} created"
