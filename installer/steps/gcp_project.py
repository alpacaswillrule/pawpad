"""GCP project + region + zone selection.

Lists the operator's accessible projects via `gcloud projects list`, asks
them to pick one. Then picks a region (with latency hints from the operator's
geographic location, ideally inferred from `gcloud config get-value compute/region`
or a simple ping test to known endpoints).

Writes:
  state["gcp_project_id"]
  state["gcp_region"]
  state["gcp_zone"]
"""

from __future__ import annotations

# TODO:
#   - `gcloud projects list --format=json` → present a list to pick from
#   - region picker: us-central1, us-west1, us-east1, europe-west1, etc.
#   - zone picker (within region)
#   - validate Compute Engine API is enabled in chosen project, else prompt to enable


def run(state: dict) -> None:
    raise NotImplementedError("TODO: GCP project/region/zone selection")
