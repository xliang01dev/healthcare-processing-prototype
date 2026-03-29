"""
Healthcare Event Emitter — interactive terminal client.

Publishes synthetic patient events directly onto the NATS message bus,
bypassing the Ingestion Gateway. Use this to seed the pipeline during
local development without needing real source system integrations.

Usage:
    python client/main.py                       # default: nats://localhost:4222
    python client/main.py nats://localhost:4222

Dependencies (install via project venv):
    nats-py>=2.7    pydantic>=2.6
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import nats.errors

from emitter import Emitter
from factory import PATIENTS, build, build_random

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_NATS_URL = "nats://localhost:4222"

_DIVIDER = "─" * 52

_SOURCE_LABELS = {
    "i": ("Hydrate patient",  "patient.hydrate"),
    "a": ("Medicare",         "raw.source-a"),
    "b": ("Hospital",         "raw.source-b"),
    "c": ("Labs",             "raw.source-c"),
}

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _patient_label(p: dict) -> str:
    return f"{p['first_name']} {p['last_name']}  ({p['medicare_id']})"


def _print_menu(patient: dict, nats_url: str) -> None:
    print(f"\n{_DIVIDER}")
    print("  Healthcare Event Emitter")
    print(f"  NATS: {nats_url}")
    print(_DIVIDER)
    print(f"  Patient: {_patient_label(patient)}")
    print()
    for key, (label, topic) in _SOURCE_LABELS.items():
        print(f"  [{key}]  {label:<20} {topic}")
    print()
    print(f"  [r]  Random event")
    print(f"  [p]  Pick patient")
    print(f"  [q]  Quit")
    print(_DIVIDER)


def _print_success(subject: str, event) -> None:
    payload = event.model_dump(mode="json")
    pretty = json.dumps(payload, indent=4, default=str)
    print(f"\n  ✓  Published → {subject}")
    print(f"     event_type : {payload.get('event_type', 'patient_hydrate')}")
    if "message_id" in payload:
        print(f"     message_id : {payload['message_id'][:16]}...")
    print()
    # indent each line of the JSON for readability
    for line in pretty.splitlines():
        print(f"     {line}")
    print()


def _print_patient_picker(current: dict) -> dict:
    print(f"\n{_DIVIDER}")
    print("  Select patient:")
    print()
    for i, p in enumerate(PATIENTS):
        marker = " ◀" if p["medicare_id"] == current["medicare_id"] else ""
        print(f"  [{i + 1}]  {_patient_label(p)}{marker}")
    print(_DIVIDER)
    while True:
        raw = input("  Choice: ").strip()
        if raw.isdigit():
            idx = int(raw) - 1
            if 0 <= idx < len(PATIENTS):
                return PATIENTS[idx]
        print(f"  Enter a number between 1 and {len(PATIENTS)}")


# ---------------------------------------------------------------------------
# Main loop
# ---------------------------------------------------------------------------

async def run(nats_url: str) -> None:
    emitter = Emitter(nats_url)
    try:
        await emitter.connect()
    except nats.errors.NoServersError:
        print(f"\n  ✗  Could not connect to NATS at {nats_url}")
        print("     Is the stack running?  docker-compose up\n")
        return

    patient = PATIENTS[0]

    try:
        while True:
            _print_menu(patient, nats_url)
            choice = input("  Choice: ").strip().lower()

            if choice == "q":
                break

            elif choice == "p":
                patient = _print_patient_picker(patient)

            elif choice == "r":
                subject, event = build_random(patient)
                await emitter.publish(subject, event.model_dump(mode="json"))
                _print_success(subject, event)

            elif choice in _SOURCE_LABELS:
                subject, event = build(choice, patient)
                await emitter.publish(subject, event.model_dump(mode="json"))
                _print_success(subject, event)

            else:
                print("\n  Unknown choice — try again.\n")

    finally:
        await emitter.close()
        print("  Disconnected.\n")


def main() -> None:
    url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("NATS_URL", DEFAULT_NATS_URL)
    asyncio.run(run(url))


if __name__ == "__main__":
    main()
