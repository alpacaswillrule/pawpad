"""Anthropic API key validation."""

from __future__ import annotations

import httpx

from installer._helpers import prompt, section


def run(state: dict) -> None:
    key = state.get("anthropic_api_key") or prompt(
        "Anthropic API key (sk-ant-...)", password=True
    )
    if not key.startswith("sk-ant-"):
        raise RuntimeError("API key should start with 'sk-ant-'")

    try:
        with httpx.Client(timeout=10) as client:
            r = client.get(
                "https://api.anthropic.com/v1/models",
                headers={"x-api-key": key, "anthropic-version": "2023-06-01"},
            )
            r.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"Anthropic key validation failed: {exc}") from exc

    state["anthropic_api_key"] = key
    section("Anthropic: OK", "key validated against /v1/models")
