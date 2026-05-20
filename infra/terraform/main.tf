# pawpad — GCP VM provisioning.
#
# Creates a single Compute Engine VM joined to your tailnet via an authkey.
# No inbound public firewall rules — VPC default-deny is fine because
# Tailscale's WireGuard is outbound. An ephemeral external IP is used only
# during the initial provisioning SSH; the installer can release it after.

terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.40"
    }
  }
}

provider "google" {
  project = var.gcp_project_id
  region  = var.gcp_region
  zone    = var.gcp_zone
}

# --- service account & APIs --------------------------------------------------

resource "google_project_service" "compute" {
  service            = "compute.googleapis.com"
  disable_on_destroy = false
}

# --- networking --------------------------------------------------------------

data "google_compute_network" "default" {
  name       = "default"
  depends_on = [google_project_service.compute]
}

data "google_compute_subnetwork" "default" {
  name       = "default"
  region     = var.gcp_region
  depends_on = [google_project_service.compute]
}

# --- workspace disk ----------------------------------------------------------

resource "google_compute_disk" "data" {
  name = "${var.instance_name}-data"
  type = var.disk_type
  zone = var.gcp_zone
  size = var.disk_size_gb

  labels = {
    pawpad = "true"
  }

  depends_on = [google_project_service.compute]
}

# --- vm ----------------------------------------------------------------------

locals {
  startup_script = templatefile("${path.module}/startup.sh.tftpl", {
    tailscale_authkey  = var.tailscale_authkey
    tailscale_hostname = var.instance_name
    pawpad_user        = "pawpad"
    repo_url           = var.repo_url
    repo_ref           = var.repo_ref
  })
}

resource "google_compute_instance" "pawpad" {
  name         = var.instance_name
  machine_type = var.machine_type
  zone         = var.gcp_zone

  labels = {
    pawpad = "true"
  }

  boot_disk {
    initialize_params {
      image = "projects/ubuntu-os-cloud/global/images/family/ubuntu-2404-lts-amd64"
      size  = 30
      type  = "pd-balanced"
    }
  }

  attached_disk {
    source      = google_compute_disk.data.self_link
    device_name = "pawpad-data"
    mode        = "READ_WRITE"
  }

  network_interface {
    network    = data.google_compute_network.default.self_link
    subnetwork = data.google_compute_subnetwork.default.self_link
    # Ephemeral external IP — only used during install. Tailscale handles
    # ongoing access. If you want to remove the external IP after install,
    # comment out this block (you'll need a separate machine on the tailnet
    # to bootstrap).
    access_config {}
  }

  metadata = {
    ssh-keys       = "${var.ssh_user}:${var.ssh_pub_key}"
    enable-oslogin = "FALSE"
    serial-port-logging-enable = "TRUE"
  }

  metadata_startup_script = local.startup_script

  service_account {
    scopes = ["cloud-platform"]
  }

  shielded_instance_config {
    enable_secure_boot          = true
    enable_vtpm                 = true
    enable_integrity_monitoring = true
  }

  allow_stopping_for_update = true

  depends_on = [google_project_service.compute]
}

# --- firewall ----------------------------------------------------------------
#
# No `google_compute_firewall` rules permitting public ingress are created.
# GCP's default VPC has a default-allow-ssh rule on the `default` network from
# 0.0.0.0/0 that we explicitly *delete* in the installer (see scripts/post-deploy.sh).
# Tailscale gives you SSH inside the tailnet via `tailscale ssh`.
