#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import secrets
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CONFIG = ROOT / ".dana_workers.json"
POOL = [
    "Atlas", "Nova", "Orion", "Vega", "Echo", "Luna", "Pixel", "Nexus",
    "Iris", "Argo", "Cobalt", "Milo", "Astra", "Onyx", "Raven", "Sol",
    "Kairo", "Zephyr", "Axiom", "Ember", "Sage", "Bolt", "Lyra", "Quill",
    "Phoenix", "Cosmo", "Drift", "Halo", "Indigo", "Juno", "Mars", "River",
    "Storm", "Titan", "Willow", "Zen", "Orbit", "Comet", "Frost", "Dawn",
]

def generate(first: str, count: int) -> list[str]:
    first = first.strip()
    if not first:
        raise ValueError("The first Worker name cannot be empty.")
    if count < 1 or count > 128:
        raise ValueError("Worker count must be between 1 and 128.")
    names = [first]
    available = [n for n in POOL if n.casefold() != first.casefold()]
    # Deterministic ordering with a fresh installation-independent shuffle.
    # The generated file itself is the source of truth, so names never change
    # unless this command is explicitly run again.
    secrets.SystemRandom().shuffle(available)
    for name in available:
        if len(names) >= count:
            break
        names.append(name)
    while len(names) < count:
        candidate = f"{first}-{len(names) + 1}"
        if candidate.casefold() not in {n.casefold() for n in names}:
            names.append(candidate)
    return names

def main() -> int:
    parser = argparse.ArgumentParser(description="Regenerate Dana Worker names.")
    parser.add_argument("first", nargs="?", help="Name to assign to Worker #1")
    parser.add_argument("--count", type=int, default=None, help="Number of Workers (1-128)")
    args = parser.parse_args()

    first = args.first or input("Name for Worker #1: ").strip()
    count = args.count
    if count is None:
        count = int(input("Number of Dana workers (5): ") or "5")

    names = generate(first, count)
    CONFIG.write_text(json.dumps({"workers": names}, indent=2) + "\n", encoding="utf-8")
    print("\nDana Worker names regenerated.\n")
    for i, name in enumerate(names, 1):
        print(f"  #{i:<3} {name}")
    print(f"\nSaved to {CONFIG.name}")
    print("Restart Dana with ./run for the new names to take effect.")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
