"""GCP auth step.

Two paths:
  1. Operator already has gcloud authed → verify and continue.
  2. Operator pastes a service-account JSON path → verify it has compute admin.

Writes `state["gcp_creds_path"]` (or marks `state["gcp_uses_adc"] = True`).
"""

from __future__ import annotations

# TODO:
#   - shell out to `gcloud auth application-default print-access-token`
#     to verify ADC works
#   - or accept a service-account JSON path, validate it parses, validate
#     the SA has roles/compute.admin via `gcloud iam` or by attempting a dry-run
#   - link to https://console.cloud.google.com/iam-admin/serviceaccounts
#     with copy-pasteable instructions


def run(state: dict) -> None:
    raise NotImplementedError("TODO: GCP auth step")
