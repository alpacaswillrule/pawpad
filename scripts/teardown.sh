#!/usr/bin/env bash
# Tear down the pawpad VM. Asks for explicit confirmation.
# Snapshots the data disk first by default — pass --no-snapshot to skip.

set -euo pipefail

NO_SNAPSHOT=0
for arg in "$@"; do
  case "$arg" in
    --no-snapshot) NO_SNAPSHOT=1 ;;
  esac
done

RUNTIME="$HOME/.pawpad/runtime.json"
if [[ ! -f "${RUNTIME}" ]]; then
  echo "missing ${RUNTIME}" >&2
  exit 1
fi

echo "This will destroy the pawpad VM and (unless --no-snapshot) snapshot its data disk."
read -r -p "Type 'destroy' to confirm: " ans
[[ "${ans}" == "destroy" ]] || { echo "aborted"; exit 1; }

if [[ "${NO_SNAPSHOT}" == "0" ]]; then
  "$(dirname "$0")/snapshot.sh" "pawpad-teardown-$(date -u +%Y%m%dT%H%M%SZ)"
fi

cd "$(dirname "$0")/../infra/terraform"
terraform destroy -auto-approve
echo "ok: pawpad VM destroyed"
