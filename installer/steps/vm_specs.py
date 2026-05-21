"""VM machine type + hot/cold disk sizing.

Two-tier storage:
  HOT  — SSD (pd-balanced default). Live workspaces. Under the 500GB SSD
         quota by default to avoid quota-increase friction.
  COLD — HDD (pd-standard default). _archived/ projects + vault. Cheaper,
         huge quota, slower.
"""

from __future__ import annotations

from installer._helpers import console, prompt, section

MACHINE_TYPES = [
    ("e2-standard-2", "2 vCPU,  8 GB · ~$50/mo · cheap"),
    ("e2-standard-4", "4 vCPU, 16 GB · ~$100/mo · recommended"),
    ("e2-standard-8", "8 vCPU, 32 GB · ~$200/mo · heavy concurrency"),
    ("n2-standard-4", "4 vCPU, 16 GB · ~$140/mo · faster CPU than e2"),
]

DISK_TYPES = [
    ("pd-standard", "HDD · ~$0.04/GB/mo · slow random IO"),
    ("pd-balanced", "SSD-class · ~$0.10/GB/mo · recommended for hot"),
    ("pd-ssd", "fastest · ~$0.17/GB/mo · only if you need it"),
]

DISK_COST_PER_GB = {"pd-standard": 0.04, "pd-balanced": 0.10, "pd-ssd": 0.17}


def _pick_machine_type(state: dict) -> None:
    section("VM machine type", "")
    for i, (t, desc) in enumerate(MACHINE_TYPES, 1):
        console.print(f"  [bold]{i}.[/bold] {t:18s}  {desc}")
    default_idx = next(
        (i for i, (t, _) in enumerate(MACHINE_TYPES, 1) if t == state.get("machine_type")),
        2,
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


def _est_cost(size_gb: int, disk_type: str) -> float:
    return size_gb * DISK_COST_PER_GB.get(disk_type, 0.10)


def run(state: dict) -> None:
    _pick_machine_type(state)

    section(
        "Hot disk (SSD) — live workspaces",
        "Holds the active ~/projects and ~/obsidian-vault. Keep under the 500GB "
        "SSD quota to avoid filing a quota request.",
    )
    hot_size = int(prompt(
        "Hot disk size in GB",
        default=str(state.get("disk_size_gb", 200)),
    ))
    state["disk_size_gb"] = hot_size
    _pick_disk_type("Hot disk", "disk_type", state, "pd-balanced")

    section(
        "Cold disk (HDD) — archives + bulk",
        "Holds _archived/ projects + vault. Slow random IO, but cheap and "
        "large quotas. Enter 0 to skip — single-tier setup like before.",
    )
    cold_size = int(prompt(
        "Cold disk size in GB (0 to skip)",
        default=str(state.get("cold_disk_size_gb", 1000)),
    ))
    state["cold_disk_size_gb"] = cold_size
    if cold_size > 0:
        _pick_disk_type("Cold disk", "cold_disk_type", state, "pd-standard")
    else:
        state["cold_disk_type"] = "pd-standard"  # unused but set for tfvars

    # Cost summary
    hot_cost = _est_cost(hot_size, state["disk_type"])
    cold_cost = _est_cost(cold_size, state["cold_disk_type"]) if cold_size > 0 else 0
    boot_cost = _est_cost(30, "pd-balanced")
    section(
        "estimated monthly disk cost",
        f"  boot (30GB pd-balanced):     ~${boot_cost:5.2f}\n"
        f"  hot ({hot_size}GB {state['disk_type']}):  ~${hot_cost:5.2f}\n"
        f"  cold ({cold_size}GB {state['cold_disk_type']}):" + " " * max(0, 14 - len(state['cold_disk_type']) - len(str(cold_size)))
        + f" ~${cold_cost:5.2f}\n"
        f"  -------------------------------------\n"
        f"  disk total:                  ~${boot_cost + hot_cost + cold_cost:5.2f}/mo\n"
        f"\n"
        f"  (VM compute is separate — e2-standard-4 is ~$100/mo)",
    )
