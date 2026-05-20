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
  type        = string
  default     = "pd-balanced"
  description = "pd-standard | pd-balanced | pd-ssd"
}

variable "tailscale_authkey" {
  type      = string
  sensitive = true
}

variable "ssh_user" {
  type        = string
  default     = "pawpad"
  description = "OS user for initial SSH login (also runs the bot)"
}

variable "ssh_pub_key" {
  type        = string
  description = "SSH public key for initial deploy login (use Tailscale SSH for ongoing access)"
}

variable "instance_name" {
  type    = string
  default = "pawpad-vm"
}

variable "repo_url" {
  type        = string
  default     = "https://github.com/alpacaswillrule/pawpad.git"
  description = "Repo to clone onto the VM at /opt/pawpad"
}

variable "repo_ref" {
  type        = string
  default     = "main"
  description = "Branch or tag to check out"
}
