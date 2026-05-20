"""GCP auth verification.

Two paths:
  1. ADC already configured (gcloud auth application-default login done) — verify
  2. Operator provides a service-account JSON path — verify it parses + works
"""

from __future__ import annotations

import json
from pathlib import Path

from installer._helpers import confirm, have_cmd, prompt, section, sh


def run(state: dict) -> None:
    if not have_cmd("gcloud"):
        section(
            "missing gcloud",
            "The `gcloud` CLI is not installed. Install via:\n\n"
            "  [bold]brew install --cask google-cloud-sdk[/bold]\n\n"
            "Then re-run ./install.sh.",
        )
        raise RuntimeError("gcloud not installed")

    res = sh(["gcloud", "auth", "application-default", "print-access-token"], check=False)
    if res.returncode == 0:
        section(
            "GCP auth: OK",
            "Application Default Credentials (ADC) are configured.",
        )
        state["gcp_uses_adc"] = True
        state.pop("gcp_creds_path", None)
        return

    section(
        "GCP auth needed",
        "No Application Default Credentials found. Two options:\n\n"
        "  [bold]A.[/bold] In another terminal:\n"
        "       [bold]gcloud auth application-default login[/bold]\n"
        "     then come back and continue.\n"
        "  [bold]B.[/bold] Provide a service-account JSON key path now.\n",
    )

    if confirm("Use a service-account JSON file?", default=False):
        path_str = prompt("Absolute path to service-account JSON")
        p = Path(path_str).expanduser()
        if not p.exists():
            raise RuntimeError(f"file not found: {p}")
        try:
            data = json.loads(p.read_text())
            if data.get("type") != "service_account":
                raise RuntimeError("JSON does not look like a service-account key")
        except Exception as e:
            raise RuntimeError(f"invalid service-account JSON: {e}") from e
        state["gcp_creds_path"] = str(p)
        state["gcp_uses_adc"] = False
        return

    raise RuntimeError(
        "GCP auth not configured. Run: gcloud auth application-default login, then re-run."
    )
