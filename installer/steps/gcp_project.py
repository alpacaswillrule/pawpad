"""GCP project + region + zone selection."""

from __future__ import annotations

import json

from installer._helpers import console, prompt, section, sh

REGIONS = [
    ("us-central1", "Iowa — cheapest US"),
    ("us-east1", "South Carolina"),
    ("us-east4", "Virginia"),
    ("us-west1", "Oregon — best west-coast latency"),
    ("us-west2", "Los Angeles"),
    ("europe-west1", "Belgium"),
    ("europe-west4", "Netherlands"),
    ("asia-east1", "Taiwan"),
    ("asia-northeast1", "Tokyo"),
]


def run(state: dict) -> None:
    # --- project -----------------------------------------------------------
    res = sh(["gcloud", "projects", "list", "--format=json"], check=False)
    project_id = state.get("gcp_project_id")

    if res.returncode == 0:
        try:
            projects = json.loads(res.stdout)
        except json.JSONDecodeError:
            projects = []
    else:
        projects = []

    if projects:
        section(
            "GCP project",
            "Pick a project ID below or paste your own.",
        )
        for i, p in enumerate(projects, 1):
            console.print(f"  [bold]{i:2d}.[/bold] {p['projectId']:30s}  {p.get('name', '')}")
        choice = prompt(
            "Project number or full projectId",
            default=project_id or projects[0]["projectId"],
        )
        if choice.isdigit() and 1 <= int(choice) <= len(projects):
            project_id = projects[int(choice) - 1]["projectId"]
        else:
            project_id = choice.strip()
    else:
        project_id = prompt("GCP project ID", default=project_id)

    state["gcp_project_id"] = project_id

    # --- enable compute API if needed --------------------------------------
    sh(
        ["gcloud", "services", "enable", "compute.googleapis.com", "--project", project_id],
        check=False,
    )

    # --- region ------------------------------------------------------------
    section("region", "Pick a GCP region (lower number = closer to you, usually).")
    for i, (region, desc) in enumerate(REGIONS, 1):
        console.print(f"  [bold]{i:2d}.[/bold] {region:18s}  {desc}")

    region = state.get("gcp_region", "us-central1")
    choice = prompt("Region number or name", default=region)
    if choice.isdigit() and 1 <= int(choice) <= len(REGIONS):
        region = REGIONS[int(choice) - 1][0]
    else:
        region = choice.strip()
    state["gcp_region"] = region

    # --- zone --------------------------------------------------------------
    # default to first zone of region; let operator override
    zone_default = state.get("gcp_zone", f"{region}-a")
    if not zone_default.startswith(region):
        zone_default = f"{region}-a"
    state["gcp_zone"] = prompt("Zone", default=zone_default)
