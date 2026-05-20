output "instance_name" {
  value = google_compute_instance.pawpad.name
}

output "external_ip" {
  description = "Ephemeral external IP (used for initial install SSH only)"
  value       = google_compute_instance.pawpad.network_interface[0].access_config[0].nat_ip
}

output "internal_ip" {
  value = google_compute_instance.pawpad.network_interface[0].network_ip
}

output "ssh_user" {
  value = var.ssh_user
}

output "tailnet_hostname" {
  description = "Hostname the VM advertises to Tailscale (e.g. pawpad-vm)"
  value       = var.instance_name
}

output "data_disk_name" {
  value = google_compute_disk.data.name
}
