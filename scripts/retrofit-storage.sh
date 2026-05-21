#!/usr/bin/env bash
# Retrofit an existing pawpad VM with the tiered-storage layout
# (smaller hot SSD + new cold HDD).
#
# What it does:
#   1. Stops the bot on the VM.
#   2. tar /srv/pawpad-data → /tmp/pawpad-data-backup.tar.gz (survives the swap).
#   3. Takes a GCP snapshot of the current data disk for belt-and-suspenders.
#   4. Stops the VM.
#   5. Detaches the existing data disk.
#   6. Creates two new disks: a smaller SSD (hot) + a fresh HDD (cold).
#   7. Attaches both, starts the VM.
#   8. SSH in: formats both disks, mounts them, restores data from /tmp,
#      rewires the _archived symlinks to point at the cold disk, restarts bot.
#   9. Leaves the OLD data disk un-deleted so you can roll back. Delete it
#      manually after a day of "yep, everything's fine."
#
# Args (all required):
#   --project       GCP project ID
#   --zone          GCP zone (e.g. us-central1-a)
#   --instance      VM instance name (default: pawpad-vm)
#   --hot-size      new hot SSD size in GB (e.g. 100)
#   --cold-size     new cold HDD size in GB (e.g. 1000)
#   --ssh-key       SSH private key path (e.g. ~/.pawpad/vm_ssh_key)
#   --ssh-user      SSH user (default: pawpad)
#
# Brief downtime (~3-5 min) during the disk swap. Snapshot + tar are safety
# nets; if anything blows up, reattach the old disk and re-fstab the UUID.

set -euo pipefail

PROJECT=""
ZONE=""
INSTANCE="pawpad-vm"
HOT_SIZE=""
COLD_SIZE=""
SSH_KEY=""
SSH_USER="pawpad"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --project)    PROJECT="$2"; shift 2;;
    --zone)       ZONE="$2"; shift 2;;
    --instance)   INSTANCE="$2"; shift 2;;
    --hot-size)   HOT_SIZE="$2"; shift 2;;
    --cold-size)  COLD_SIZE="$2"; shift 2;;
    --ssh-key)    SSH_KEY="$2"; shift 2;;
    --ssh-user)   SSH_USER="$2"; shift 2;;
    *)            echo "unknown arg: $1" >&2; exit 1;;
  esac
done

for v in PROJECT ZONE HOT_SIZE COLD_SIZE SSH_KEY; do
  if [[ -z "${!v}" ]]; then
    echo "missing required arg: --${v,,}" >&2
    exit 1
  fi
done

TS=$(date -u +%Y%m%dT%H%M%SZ)
SNAP_NAME="${INSTANCE}-pre-retrofit-${TS}"
OLD_DATA_DISK="${INSTANCE}-data"
NEW_DATA_DISK="${INSTANCE}-data-v2"
COLD_DISK="${INSTANCE}-cold"

echo "==> Retrofit plan:"
echo "    project:    ${PROJECT}"
echo "    instance:   ${INSTANCE} (zone ${ZONE})"
echo "    old data:   ${OLD_DATA_DISK} (will be DETACHED, not deleted)"
echo "    new data:   ${NEW_DATA_DISK} (${HOT_SIZE}GB pd-balanced, empty)"
echo "    new cold:   ${COLD_DISK} (${COLD_SIZE}GB pd-standard, empty)"
echo "    snapshot:   ${SNAP_NAME}"
echo

ssh_vm() {
  ssh -i "${SSH_KEY}" \
      -o StrictHostKeyChecking=no \
      -o UserKnownHostsFile=/dev/null \
      -o ConnectTimeout=15 \
      "${SSH_USER}@$(gcloud compute instances describe "${INSTANCE}" --project="${PROJECT}" --zone="${ZONE}" --format='value(networkInterfaces[0].accessConfigs[0].natIP)')" \
      "$@"
}

# ---- 1. stop the bot, tar the data ----------------------------------------

echo "==> Stopping bot + tar'ing data..."
ssh_vm '
  set -e
  sudo systemctl stop jojo-bot.service 2>/dev/null || true
  sudo tar -czf /tmp/pawpad-data-backup.tar.gz -C / srv/pawpad-data
  ls -la /tmp/pawpad-data-backup.tar.gz
'

# ---- 2. snapshot the old data disk (belt+suspenders) ----------------------

echo "==> Taking GCP snapshot of ${OLD_DATA_DISK}..."
gcloud compute disks snapshot "${OLD_DATA_DISK}" \
    --project="${PROJECT}" --zone="${ZONE}" \
    --snapshot-names="${SNAP_NAME}"

# ---- 3. create the new disks (while the VM still runs) --------------------

echo "==> Creating ${NEW_DATA_DISK} (${HOT_SIZE}GB pd-balanced)..."
gcloud compute disks create "${NEW_DATA_DISK}" \
    --project="${PROJECT}" --zone="${ZONE}" \
    --size="${HOT_SIZE}GB" --type=pd-balanced \
    --labels=pawpad=true,tier=hot

echo "==> Creating ${COLD_DISK} (${COLD_SIZE}GB pd-standard)..."
gcloud compute disks create "${COLD_DISK}" \
    --project="${PROJECT}" --zone="${ZONE}" \
    --size="${COLD_SIZE}GB" --type=pd-standard \
    --labels=pawpad=true,tier=cold

# ---- 4. stop VM, swap disks -----------------------------------------------

echo "==> Stopping VM..."
gcloud compute instances stop "${INSTANCE}" --project="${PROJECT}" --zone="${ZONE}"

echo "==> Detaching old data disk..."
gcloud compute instances detach-disk "${INSTANCE}" \
    --project="${PROJECT}" --zone="${ZONE}" --disk="${OLD_DATA_DISK}"

echo "==> Attaching new data disk (device-name=pawpad-data)..."
gcloud compute instances attach-disk "${INSTANCE}" \
    --project="${PROJECT}" --zone="${ZONE}" \
    --disk="${NEW_DATA_DISK}" --device-name=pawpad-data

echo "==> Attaching cold disk (device-name=pawpad-cold)..."
gcloud compute instances attach-disk "${INSTANCE}" \
    --project="${PROJECT}" --zone="${ZONE}" \
    --disk="${COLD_DISK}" --device-name=pawpad-cold

echo "==> Starting VM..."
gcloud compute instances start "${INSTANCE}" --project="${PROJECT}" --zone="${ZONE}"

# ---- 5. wait for SSH ------------------------------------------------------

echo "==> Waiting for SSH..."
for _ in $(seq 1 60); do
  if ssh_vm 'true' >/dev/null 2>&1; then
    echo "  SSH ready."
    break
  fi
  sleep 5
done

# ---- 6. configure mounts + restore + symlinks -----------------------------

echo "==> Formatting + mounting new disks, restoring backup, setting up symlinks..."
ssh_vm '
  set -euo pipefail

  HOT=/dev/disk/by-id/google-pawpad-data
  COLD=/dev/disk/by-id/google-pawpad-cold

  # Format hot if blank.
  if ! sudo blkid "$HOT" >/dev/null 2>&1; then
    echo "  formatting $HOT as ext4..."
    sudo mkfs.ext4 -F "$HOT"
  fi
  HOT_UUID=$(sudo blkid -s UUID -o value "$HOT")

  # Format cold if blank.
  if ! sudo blkid "$COLD" >/dev/null 2>&1; then
    echo "  formatting $COLD as ext4..."
    sudo mkfs.ext4 -F "$COLD"
  fi
  COLD_UUID=$(sudo blkid -s UUID -o value "$COLD")

  # Update fstab: replace the old /srv/pawpad-data entry, append cold.
  sudo sed -i "/[[:space:]]\/srv\/pawpad-data[[:space:]]/d" /etc/fstab
  sudo sed -i "/[[:space:]]\/srv\/pawpad-cold[[:space:]]/d"  /etc/fstab
  echo "UUID=$HOT_UUID  /srv/pawpad-data  ext4  defaults,nofail  0 2" | sudo tee -a /etc/fstab >/dev/null
  echo "UUID=$COLD_UUID /srv/pawpad-cold  ext4  defaults,nofail  0 2" | sudo tee -a /etc/fstab >/dev/null

  # Mount both.
  sudo mkdir -p /srv/pawpad-data /srv/pawpad-cold
  sudo mount /srv/pawpad-data
  sudo mount /srv/pawpad-cold
  sudo chown pawpad:pawpad /srv/pawpad-data /srv/pawpad-cold

  # Restore data from tar (overwrites the empty mount).
  echo "  restoring /srv/pawpad-data from backup..."
  sudo tar -xzf /tmp/pawpad-data-backup.tar.gz -C /
  sudo chown -R pawpad:pawpad /srv/pawpad-data

  # Set up cold-disk subdirs + symlinks for _archived.
  sudo -u pawpad mkdir -p \
    /srv/pawpad-cold/archived-projects \
    /srv/pawpad-cold/archived-vault

  for pair in \
    "/srv/pawpad-data/projects/_archived:/srv/pawpad-cold/archived-projects" \
    "/srv/pawpad-data/obsidian-vault/_archived:/srv/pawpad-cold/archived-vault" \
  ; do
    src=${pair%%:*}
    tgt=${pair##*:}
    if [[ -e "$src" && ! -L "$src" ]]; then
      # Existing dir — move its content into the cold mount, then symlink.
      sudo mv "$src"/* "$tgt"/ 2>/dev/null || true
      sudo rm -rf "$src"
    fi
    sudo -u pawpad ln -sfn "$tgt" "$src"
  done

  # Verify mounts + restart bot.
  df -h | grep -E "pawpad-data|pawpad-cold"
  sudo systemctl start jojo-bot.service
'

# ---- 7. wait for bot, summarize -------------------------------------------

echo "==> Waiting 10s then checking bot status..."
sleep 10
ssh_vm 'sudo journalctl -u jojo-bot.service --since "30 seconds ago" --no-pager | tail -10'

echo
echo "==> DONE."
echo "    Old disk ${OLD_DATA_DISK} is detached but not deleted. Delete with:"
echo "      gcloud compute disks delete ${OLD_DATA_DISK} \\"
echo "          --project=${PROJECT} --zone=${ZONE}"
echo "    Snapshot ${SNAP_NAME} is also available as a longer-term backup."
