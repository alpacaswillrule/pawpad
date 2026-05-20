# Obsidian LiveSync

CouchDB-backed Obsidian sync. Runs on the VM, only reachable over Tailscale.

## On the VM

The installer's `deploy` step writes a `.env` here with `COUCHDB_USER` and
`COUCHDB_PASSWORD` (generated during the `obsidian` install step), then starts
the `livesync.service` systemd unit which `docker compose up -d` this.

## On your laptop / phone

1. Install the **Self-hosted LiveSync** community plugin in Obsidian.
2. Open the same vault on every device you want to sync (one machine "Setup
   wizard" to seed, then "Copy current setting to clipboard" → paste on the
   other devices).
3. Plugin settings:
   - **Remote database URI:** `https://pawpad-vm:5984` (tailnet hostname) or
     `https://<tailscale-ip>:5984`
   - **Database name:** `obsidian`
   - **Username / Password:** from VM `.env`
   - **End-to-end encryption passphrase:** the one you set during install

Verify Tailscale is running on the device before opening Obsidian, or sync
will fail silently.
