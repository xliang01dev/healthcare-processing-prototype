"""
Patient Data Query Client — interactive terminal client.

Queries patient data from the Patient API.
Submits synthetic patient events to the Ingestion Gateway.

Usage:
    python client/main.py                                   # defaults
    python client/main.py http://localhost:8001 http://localhost:8002  # custom urls

Dependencies (install via project venv):
    httpx>=0.24    pydantic>=2.6
"""

import asyncio
import json
import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

import httpx

from typing import Any
from api_client import APIClient
from factory import PATIENTS, build, build_random

# ---------------------------------------------------------------------------
# Config
# ---------------------------------------------------------------------------

DEFAULT_GATEWAY_URL = "http://localhost:8001"
DEFAULT_PATIENT_API_URL = "http://localhost:8000"

_DIVIDER = "─" * 52

_SOURCE_LABELS = {
    "h": ("Hydrate",          "POST /hydrate"),
    "m": ("Medicare",         "POST /ingest"),
    "b": ("Hospital",         "POST /ingest"),
    "l": ("Labs",             "POST /ingest"),
}

# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _patient_label(p: dict) -> str:
    return f"{p['first_name']} {p['last_name']}  ({p['medicare_id']})"


def _print_menu(patient: dict) -> None:
    print(f"\n{_DIVIDER}")
    print("  Patient Data Query Client")
    print(_DIVIDER)
    print(f"  Patient: {_patient_label(patient)}")
    print()
    print(f"  [pi] Fetch patient info")
    print(f"  [pr] Fetch patient recommendation")
    print(f"  [pt] Fetch patient timeline")
    print()
    for key, (label, topic) in _SOURCE_LABELS.items():
        print(f"  [{key}]  {label:<20} {topic}")
    print()
    print(f"  [r]  Random event")
    print(f"  [p]  Pick patient")
    print()
    print(f"  [q]  Quit")
    print(_DIVIDER)


def _print_success(subject: str, event: Any) -> None:
    payload = event.model_dump(mode="json")
    pretty = json.dumps(payload, indent=4, default=str)
    print(f"\n  ✓  Submitted to Ingestion Gateway")
    print(f"     source : {subject}")
    print(f"     event_type : {payload.get('event_type', 'patient_hydrate')}")
    if "message_id" in payload:
        print(f"     message_id : {payload['message_id'][:16]}...")
    print()
    # indent each line of the JSON for readability
    for line in pretty.splitlines():
        print(f"     {line}")
    print()


def _print_golden_record(record: dict[str, Any]) -> None:
    """Display patient info in a readable format."""
    print(f"\n{_DIVIDER}")
    print("  Patient Info")
    print(_DIVIDER)
    pretty = json.dumps(record, indent=4, default=str)
    for line in pretty.splitlines():
        print(f"     {line}")
    print()


def _print_recommendation(record: dict[str, Any]) -> None:
    """Display patient recommendation in a readable format."""
    print(f"\n{_DIVIDER}")
    print("  Patient Recommendation")
    print(_DIVIDER)
    pretty = json.dumps(record, indent=4, default=str)
    for line in pretty.splitlines():
        print(f"     {line}")
    print()


def _print_timeline(record: dict[str, Any]) -> None:
    """Display patient timeline in a readable format."""
    print(f"\n{_DIVIDER}")
    print("  Patient Timeline")
    print(_DIVIDER)
    pretty = json.dumps(record, indent=4, default=str)
    for line in pretty.splitlines():
        print(f"     {line}")
    print()


def _print_patient_picker(current: dict[str, Any]) -> dict:
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

async def run(gateway_url: str, patient_api_url: str) -> None:
    client = APIClient(patient_api_url, gateway_url)

    try:
        await client.connect()
    except httpx.ConnectError:
        print(f"\n  ✗  Could not connect to services")
        print(f"     Gateway: {gateway_url}")
        print(f"     Patient API: {patient_api_url}")
        print("     Is the stack running?  docker-compose up\n")
        return

    patient = PATIENTS[0]

    try:
        while True:
            _print_menu(patient)
            choice = input("  Choice: ").strip().lower()

            if choice == "q":
                break

            elif choice == "p":
                patient = _print_patient_picker(patient)

            elif choice == "f" or choice == "pi":
                record = await client.fetch_golden_record(patient["medicare_id"])
                if record:
                    _print_golden_record(record)
                else:
                    print(f"\n  ✗  Could not fetch patient info for {patient['medicare_id']}\n")

            elif choice == "pr":
                recommendation = await client.fetch_recommendation(patient["medicare_id"])
                if recommendation:
                    _print_recommendation(recommendation)
                else:
                    print(f"\n  ✗  Could not fetch recommendation for {patient['medicare_id']}\n")

            elif choice == "pt":
                timeline = await client.fetch_patient_timeline(patient["medicare_id"])
                if timeline:
                    _print_timeline(timeline)
                else:
                    print(f"\n  ✗  Could not fetch timeline for {patient['medicare_id']}\n")

            elif choice == "r":
                subject, event = build_random(patient)
                await client.submit_event(subject, event.model_dump(mode="json"))
                _print_success(subject, event)

            elif choice in _SOURCE_LABELS:
                subject, event = build(choice, patient)
                await client.submit_event(subject, event.model_dump(mode="json"))
                _print_success(subject, event)

            else:
                print("\n  Unknown choice — try again.\n")

    finally:
        await client.close()
        print("  Disconnected.\n")


def main() -> None:
    gateway_url = sys.argv[1] if len(sys.argv) > 1 else os.getenv("GATEWAY_URL", DEFAULT_GATEWAY_URL)
    patient_api_url = sys.argv[2] if len(sys.argv) > 2 else os.getenv("PATIENT_API_URL", DEFAULT_PATIENT_API_URL)
    asyncio.run(run(gateway_url, patient_api_url))


if __name__ == "__main__":
    main()
