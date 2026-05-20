# Credentials to gather before running `./install.sh`

You don't need to have these *paste-ready* — the installer walks you through
getting each one. This doc is just the cheat sheet so you know what's coming.

## 1. GCP service-account JSON

The installer needs to provision a VM, a disk, and firewall rules in your GCP
project.

**Path A — easiest:**
```bash
gcloud auth login
gcloud auth application-default login
```
The installer detects ADC and uses it. Skip the service-account step.

**Path B — if you don't want to use your personal GCP identity:**
1. Open https://console.cloud.google.com/iam-admin/serviceaccounts
2. Pick your project (or create one).
3. **Create service account** → name `pawpad-installer`.
4. Grant role: **Compute Admin** (and **Service Account User** if it asks).
5. Done → click the service account → **Keys** tab → **Add Key** → **JSON**.
6. A JSON file downloads. Save its path; the installer asks for it.

You also need:
- The **GCP project ID** (visible at the top of the console).
- **Compute Engine API** enabled. The installer enables it for you if missing.
- **Billing** enabled on the project. The installer cannot enable billing.

## 2. Tailscale auth key

1. Open https://login.tailscale.com/admin/settings/keys
2. **Generate auth key**:
   - Reusable: yes (so the VM can re-join the tailnet on reboot)
   - Ephemeral: optional (drops the node when offline — fine for dev)
   - Tags: `tag:pawpad` (you'll need to add this tag in your tailnet ACL — see below)
3. Copy the key (`tskey-auth-...`). The installer asks for it.

In your **Access Controls** (Tailscale admin → Access Controls), add:
```jsonc
{
  "tagOwners": {
    "tag:pawpad": ["autogroup:admin"]
  }
}
```

## 3. GitHub auth

Already set up if `gh auth status` shows `Logged in to github.com account alpacaswillrule`. Otherwise:
```bash
gh auth login -s repo,admin:public_key
```
Scopes needed:
- `repo` — create and push to private repos (the bot uses this per channel)
- `admin:public_key` — add the VM's deploy SSH key to your account

The installer verifies and stops with instructions if anything's missing.

## 4. Discord bot token + guild ID

1. https://discord.com/developers/applications → **New Application** → name it **Jojo**.
2. **Bot** tab → **Add Bot** → **Reset Token** → copy the token (this is what the installer wants).
3. **Privileged Gateway Intents**: enable
   - **MESSAGE CONTENT INTENT**
   - **SERVER MEMBERS INTENT**
4. **OAuth2 → URL Generator**:
   - Scopes: `bot`, `applications.commands`
   - Permissions: `View Channels`, `Send Messages`, `Manage Channels`, `Read Message History`, `Attach Files`, `Use Slash Commands`, `Embed Links`, `Add Reactions`
5. Open the generated URL in a browser → invite the bot to your Discord server.
6. In Discord, **User Settings → Advanced → Developer Mode = on**.
7. Right-click your server icon → **Copy Server ID**. That's the guild ID.
8. In your Discord server, create a category named exactly **`projects`** (lowercase). The bot only watches text channels under this category.

## 5. Anthropic API key

1. https://console.anthropic.com/settings/keys
2. **Create Key** → copy.
3. Recommended: also set a **workspace spend limit** in the Anthropic console as a hard safety net (the bot's `/budget` enforces a softer day-by-day cap on top).

## 6. Obsidian LiveSync passphrase

Not gathered ahead of time — the installer offers to auto-generate a strong
passphrase. You'll paste the same passphrase into the **Self-hosted LiveSync**
plugin on each device (laptop, phone) where you want the vault to sync.

You'll need to install the **Obsidian** app on those devices (free):
- Desktop: https://obsidian.md/download
- iOS: App Store, search "Obsidian"
- Android: Play Store, search "Obsidian"

The first time you open the vault on a device, paste the passphrase + the
Tailscale URL + the CouchDB credentials (the installer prints these at the
end). Subsequent devices can use the "Copy current setting to clipboard"
shortcut from the first device.

## Summary checklist

Have these in hand (or know how to get them) before running `./install.sh`:

- [ ] `gcloud` CLI installed, ADC done (or service-account JSON path)
- [ ] GCP project ID with billing enabled
- [ ] Tailscale auth key (with `tag:pawpad` in your ACL)
- [ ] `gh auth status` green for `alpacaswillrule` with `repo` + `admin:public_key`
- [ ] Discord bot token + your guild ID + bot invited to your guild
- [ ] `projects` category created in your Discord guild
- [ ] Anthropic API key
- [ ] Obsidian installed on each device you'll sync (paste passphrase later)
- [ ] `terraform` CLI installed locally
- [ ] `tailscale` CLI installed locally (only needed if you want `tailscale ssh`)

Total time to gather everything fresh: ~30 minutes if you've never done it
before, ~5 if you have most of it already.
