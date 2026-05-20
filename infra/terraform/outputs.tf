output "instance_name" {
  description = "Compute instance name"
  value       = "TODO: google_compute_instance.pawpad.name"
}

output "external_ip" {
  description = "Ephemeral external IP (only used during initial install; afterwards use tailnet)"
  value       = "TODO: google_compute_instance.pawpad.network_interface[0].access_config[0].nat_ip"
}

output "internal_ip" {
  description = "Internal VPC IP"
  value       = "TODO: google_compute_instance.pawpad.network_interface[0].network_ip"
}

# tailnet hostname is set via metadata startup script (`tailscale up --hostname=pawpad-vm`)
# we'll read it back from Tailscale's API in the installer's deploy step.
