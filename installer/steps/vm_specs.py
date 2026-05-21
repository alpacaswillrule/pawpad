"""VM machine type + hot/cold disk sizing.

Presets let the operator pick a budget tier (Tiny / Standard / Heavy) and skip
all the individual prompts, or pick Custom to set everything by hand.

Two-tier storage:
  HOT  — SSD (pd-balanced default). Live workspaces. Under the 500GB SSD
         quota to avoid quota-increase friction.
  COLD — HDD (pd-standard default). _archived/ projects + vault. Cheap.
"""

from __future__ import annotations

from installer._helpers import console, prompt, section

# Roughly accurate as of 2026 — recheck https://cloud.google.com/compute/all-pricing periodically.
MACHINE_TYPES = [
    ("e2-medium",    "2 vCPU,  4 GB ·  ~$25/mo"),
    ("e2-standard-2", "2 vCPU,  8 GB ·  ~$50/mo"),
    ("e2-standard-4", "4 vCPU, 16 GB · ~$100/mo · recommended"),
    ("e2-standard-8", "8 vCPU, 32 GB · ~$200/mo · heavy concurrency"),
    ("n2-standard-4", "4 vCPU, 16 GB · ~$140/mo · faster CPU than e2"),
]

DISK_TYPES = [
    ("pd-standard", "HDD · ~$0.04/GB/mo · slow random IO"),
    ("pd-balanced", "SSD-class · ~$0.10/GB/mo · recommended for hot"),
    ("pd-ssd",       "fastest · ~$0.17/GB/mo · only if you need it"),
]

DISK_COST_PER_GB = {"pd-standard": 0.04, "pd-balanced": 0.10, "pd-ssd": 0.17}

# Curated configurations. Each is a full set of vm_specs answers.
# Compute cost is rough — disk cost is computed.
PRESETS = [
    {
        "name": "Tiny",
        "tagline": "single user, light usage — ~$45/mo total",
        "machine_type": "e2-medium",
        "compute_est": 25.0,
        "disk_size_gb": 50,
        "disk_type": "pd-balanced",
        "cold_disk_size_gb": 200,
        "cold_disk_type": "pd-standard",
    },
    {
        "name": "Standard",
        "tagline": "daily use, multi-channel — ~$155/mo total",
        "machine_type": "e2-standard-4",
        "compute_est": 100.0,
        "disk_size_gb": 100,
        "disk_type": "pd-balanced",
        "cold_disk_size_gb": 1000,
        "cold_disk_type": "pd-standard",
    },
    {
        "name": "Heavy",
        "tagline": "many channels, big builds — ~$330/mo total",
        "machine_type": "e2-standard-8",
        "compute_est": 200.0,
        "disk_size_gb": 500,
        "disk_type": "pd-balanced",
        "cold_disk_size_gb": 2000,
        "cold_disk_type": "pd-standard",
    },
    {
        "name": "Custom",
        "tagline": "set every value yourself",
    },
]


def _est_cost(size_gb: int, disk_type: str) -> float:
    return size_gb * DISK_COST_PER_GB.get(disk_type, 0.10)


def _preset_total(p: dict) -> float:
    boot = _est_cost(30, "pd-balanced")
    hot = _est_cost(p["disk_size_gb"], p["disk_type"])
    cold = _est_cost(p["cold_disk_size_gb"], p["cold_disk_type"])
    return p["compute_est"] + boot + hot + cold


def _pick_preset(state: dict) -> dict | None:
    section(
        "Pick a preset (or Custom to set every value)",
        "Disk numbers are GB. SSD = pd-balanced, HDD = pd-standard. Boot disk is a\n"
        "fixed 30GB SSD on every preset.",
    )
    for i, p in enumerate(PRESETS, 1):
        if p["name"] == "Custom":
            console.print(f"  [bold]{i}.[/bold] {p['name']:9s}  {p['tagline']}")
            continue
        cost = _preset_total(p)
        console.print(
            f"  [bold]{i}.[/bold] {p['name']:9s}  "
            f"{p['machine_type']:14s}  "
            f"{p['disk_size_gb']:>4d}GB SSD + {p['cold_disk_size_gb']:>4d}GB HDD  "
            f"~${cost:.0f}/mo total"
        )
    choice = prompt("Preset number or name", default="2")
    selected = None
    if choice.isdigit():
        idx = int(choice)
        if 1 <= idx <= len(PRESETS):
            selected = PRESETS[idx - 1]
    else:
        for p in PRESETS:
            if p["name"].lower() == choice.strip().lower():
                selected = p
                break
    if selected is None:
        raise RuntimeError(f"unknown preset: {choice!r}")
    return selected


def _apply_preset(preset: dict, state: dict) -> None:
    for key in ("machine_type", "disk_size_gb", "disk_type",
                "cold_disk_size_gb", "cold_disk_type"):
        state[key] = preset[key]


def _pick_machine_type(state: dict) -> None:
    section("VM machine type", "")
    for i, (t, desc) in enumerate(MACHINE_TYPES, 1):
        console.print(f"  [bold]{i}.[/bold] {t:18s}  {desc}")
    default_idx = next(
        (i for i, (t, _) in enumerate(MACHINE_TYPES, 1) if t == state.get("machine_type")),
        3,
    )
    choice = prompt("Machine type number or name", default=str(default_idx))
    if choice.isdigit() and 1 <= int(choice) <= len(MACHINE_TYPES):
        state["machine_type"] = MACHINE_TYPES[int(choice) - 1][0]
    else:
        state["machine_type"] = choice.strip()


def _pick_disk_type(label: str, state_key: str, state: dict, default: str) -> None:
    for i, (t, desc) in enumerate(DISK_TYPES, 1):
        console.print(f"  [bold]{i}.[/bold] {t:14s}  {desc}")
    current = state.get(state_key, default)
    default_idx = next(
        (i for i, (t, _) in enumerate(DISK_TYPES, 1) if t == current),
        2,
    )
    choice = prompt(f"{label} type (number or name)", default=str(default_idx))
    if choice.isdigit() and 1 <= int(choice) <= len(DISK_TYPES):
        state[state_key] = DISK_TYPES[int(choice) - 1][0]
    else:
        state[state_key] = choice.strip()


def _custom_flow(state: dict) -> None:
    _pick_machine_type(state)

    section(
        "Hot disk (SSD) — live workspaces",
        "Holds the active ~/projects and ~/obsidian-vault. Keep under the\n"
        "500GB SSD quota to avoid filing a quota request.",
    )
    state["disk_size_gb"] = int(prompt(
        "Hot disk size in GB",
        default=str(state.get("disk_size_gb", 100)),
    ))
    _pick_disk_type("Hot disk", "disk_type", state, "pd-balanced")

    section(
        "Cold disk (HDD) — archives + bulk",
        "Holds _archived/ projects + vault. Slow random IO, but cheap and\n"
        "large quotas. Enter 0 to skip — single-tier setup.",
    )
    state["cold_disk_size_gb"] = int(prompt(
        "Cold disk size in GB (0 to skip)",
        default=str(state.get("cold_disk_size_gb", 1000)),
    ))
    if state["cold_disk_size_gb"] > 0:
        _pick_disk_type("Cold disk", "cold_disk_type", state, "pd-standard")
    else:
        state["cold_disk_type"] = "pd-standard"


def run(state: dict) -> None:
    preset = _pick_preset(state)
    if preset["name"] != "Custom":
        _apply_preset(preset, state)
        section(
            "preset applied",
            f"  machine:  {state['machine_type']}\n"
            f"  hot:      {state['disk_size_gb']}GB {state['disk_type']}\n"
            f"  cold:     {state['cold_disk_size_gb']}GB {state['cold_disk_type']}",
        )
    else:
        _custom_flow(state)

    # Final cost summary (always shown)
    hot_cost = _est_cost(state["disk_size_gb"], state["disk_type"])
    cold_cost = (
        _est_cost(state["cold_disk_size_gb"], state["cold_disk_type"])
        if state["cold_disk_size_gb"] > 0 else 0
    )
    boot_cost = _est_cost(30, "pd-balanced")
    section(
        "estimated monthly cost",
        f"  boot (30GB pd-balanced):              ~${boot_cost:5.2f}\n"
        f"  hot ({state['disk_size_gb']}GB {state['disk_type']}):   ~${hot_cost:5.2f}\n"
        f"  cold ({state['cold_disk_size_gb']}GB {state['cold_disk_type']}):     ~${cold_cost:5.2f}\n"
        f"  ------------------------------------------\n"
        f"  disk total:                           ~${boot_cost + hot_cost + cold_cost:5.2f}/mo\n"
        f"\n"
        f"  (VM compute is separate — see the machine-type list above)",
    )
