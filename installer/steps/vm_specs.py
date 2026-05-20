"""VM machine type + disk size + disk type selection.

Defaults (recommended for the v1 workload):
  machine_type: e2-standard-4 (4 vCPU, 16 GB RAM)
  disk_size: 1024 (GB)
  disk_type: pd-balanced

Writes:
  state["machine_type"]
  state["disk_size_gb"]
  state["disk_type"]
"""

from __future__ import annotations

# TODO:
#   - dropdown / radio for machine type:
#       e2-standard-2  (2 vCPU,  8 GB)  cheap
#       e2-standard-4  (4 vCPU, 16 GB)  recommended
#       e2-standard-8  (8 vCPU, 32 GB)  heavy concurrency
#       n2-standard-4  (4 vCPU, 16 GB)  faster CPU
#   - disk size: slider 100..4000 GB, default 1024
#   - disk type: pd-standard (HDD) | pd-balanced (recommended) | pd-ssd
#   - show monthly cost estimate below selection (compute API has a pricing
#     SKU lookup; or hardcode rough $/mo numbers per combo)


def run(state: dict) -> None:
    raise NotImplementedError("TODO: VM specs picker")
