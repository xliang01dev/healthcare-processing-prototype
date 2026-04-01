"""
HTTP client for interacting with Patient API and Ingestion Gateway.

Provides:
- Read access to patient information, golden records from Patient API
- Write access to submit events to Ingestion Gateway
"""

from typing import Any

import httpx


class APIClient:
    def __init__(self, patient_api_url: str, gateway_url: str) -> None:
        # patient_api_url should be like "http://localhost:8002"
        # gateway_url should be like "http://localhost:8001"
        self._patient_api_url = patient_api_url.rstrip('/')
        self._gateway_url = gateway_url.rstrip('/')
        self._client: httpx.AsyncClient | None = None

    async def connect(self) -> None:
        self._client = httpx.AsyncClient(timeout=10.0)

    async def fetch_golden_record(self, medicare_id: str) -> dict[str, Any] | None:
        """Fetch patient info for a patient from the Patient API.

        Returns the golden record dict or None if not found.
        """
        assert self._client is not None, "APIClient not connected"

        url = f"{self._patient_api_url}/patient/medicare/{medicare_id}"
        try:
            response = await self._client.get(url)
            response.raise_for_status()
            data = response.json()
            if isinstance(data, dict):
                return data
            return None
        except httpx.HTTPError:
            return None

    async def submit_event(self, source: str, payload: dict[str, Any]) -> None:
        """Submit an event to the Ingestion Gateway.

        source: one of 'medicare', 'hospital', 'labs', or 'hydrate'
        payload: event dict with message_id, event_type, fields, etc.
        """
        assert self._client is not None, "APIClient not connected"

        if source == "hydrate":
            # POST to /hydrate endpoint for patient hydration events
            url = f"{self._gateway_url}/hydrate"
            response = await self._client.post(url, json=payload)
        else:
            # POST to /ingest endpoint for regular source events
            body = {**payload, 'source': source}
            url = f"{self._gateway_url}/ingest"
            response = await self._client.post(url, json=body)

        response.raise_for_status()  # Raise on 4xx/5xx

    async def close(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    @property
    def connected(self) -> bool:
        return self._client is not None
