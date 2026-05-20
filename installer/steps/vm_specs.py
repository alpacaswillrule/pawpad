"""VM machine type + disk size + disk type."""

from __future__ import annotations

from installer._helpers import console, prompt, section

MACHINE_TYPES = [
    ("e2-standard-2", "2 vCPU,  8 GB · ~$50/mo · cheap"),
    ("e2-standard-4", "4 vCPU, 16 GB · ~$100/mo · recommended"),
    ("e2-standard-8", "8 vCPU, 32 GB · ~$200/mo · heavy concurrency"),
    ("n2-standard-4", "4 vCPU, 16 GB · ~$140/mo · faster CPU than e2"),
]

DISK_TYPES = [
    ("pd-standard", "HDD · cheapest · slow"),
    ("pd-balanced", "SSD-class · recommended"),
    ("pd-ssd", "fastest · ~70% more $/GB"),
]


def run(state: dict) -> None:
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

    section("disk size + type", "")
    state["disk_size_gb"] = int(prompt("Disk size in GB", default=str(state.get("disk_size_gb", 1024))))

    for i, (t, desc) in enumerate(DISK_TYPES, 1):
        console.print(f"  [bold]{i}.[/bold] {t:14s}  {desc}")
    default_idx = next(
        (i for i, (t, _) in enumerate(DISK_TYPES, 1) if t == state.get("disk_type")),
        2,
    )
    choice = prompt("Disk type number or name", default=str(default_idx))
    if choice.isdigit() and 1 <= int(choice) <= len(DISK_TYPES):
        state["disk_type"] = DISK_TYPES[int(choice) - 1][0]
    else:
        state["disk_type"] = choice.strip()
