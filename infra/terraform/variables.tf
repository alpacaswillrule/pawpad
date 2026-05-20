variable "gcp_project_id" {
  type        = string
  description = "GCP project ID"
}

variable "gcp_region" {
  type    = string
  default = "us-central1"
}

variable "gcp_zone" {
  type    = string
  default = "us-central1-a"
}

variable "machine_type" {
  type    = string
  default = "e2-standard-4"
}

variable "disk_size_gb" {
  type    = number
  default = 1024
}

variable "disk_type" {
  type    = string
  default = "pd-balanced" # pd-standard | pd-balanced | pd-ssd
}

variable "tailscale_authkey" {
  type      = string
  sensitive = true
}

variable "ssh_pub_key" {
  type        = string
  description = "SSH public key for the initial deploy login (subsequent ops go via Tailscale SSH)"
}

variable "instance_name" {
  type    = string
  default = "pawpad-vm"
}
