# pawpad — GCP VM provisioning.
#
# Creates:
#   - 1× Compute Engine VM (machine_type, disk size/type from variables)
#   - boot disk (Ubuntu 24.04 LTS)
#   - firewall rules (NO inbound public — Tailscale-only)
#   - startup-script that installs tailscale and connects via authkey
#   - SSH key pair for deploy

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
  zone    = var.gcp_zone
}

# TODO:
#   - google_compute_instance "pawpad" with metadata startup-script that:
#       curl -fsSL https://tailscale.com/install.sh | sh
#       tailscale up --authkey=$TAILSCALE_AUTHKEY --hostname=pawpad-vm --advertise-tags=tag:pawpad --ssh
#       systemctl enable --now tailscaled
#   - google_compute_disk for the 1TB workspace disk
#   - google_compute_attached_disk to attach it
#   - google_compute_firewall ALLOW from tag:pawpad on the tailnet only
#     (or no firewall rules at all — VPC default-deny inbound is fine since
#     Tailscale's WireGuard goes outbound)
#   - outputs: instance external IP (only used during initial SSH/install),
#     instance internal IP, tailnet hostname (set as metadata)
