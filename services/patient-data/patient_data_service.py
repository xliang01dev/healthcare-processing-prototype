import asyncio
import json
import logging

from typing import Any
from datetime import date, datetime
from uuid import UUID

import nats

from patient_data_models import (
    HydrateEvent,
    GoldenRecord,
    MedicareEvent,
    HospitalEvent,
    LabEvent,
    SourceSystem,
)
from patient_data_provider import PatientDataProvider
from shared.message_bus import MessageBus

logger = logging.getLogger(__name__)


class PatientDataService:
    def __init__(self, data_provider: PatientDataProvider, bus: MessageBus) -> None:
        self.data_provider = data_provider
        self.bus = bus
        self.handlers = {
            "Medicare": self._handle_medicare_event,
            "Hospital": self._handle_hospital_event,
            "Labs": self._handle_lab_event,
        }

    async def handle_hydration_event(self, msg) -> None:
        data = json.loads(msg.data.decode())
        logger.info("handle_hydration_event: data=%s", data)

        hydrate_event = HydrateEvent.model_validate(data)
        canonical_patient_id = await self.data_provider.upsert_patient(hydrate_event.medicare_id)

        golden_record = GoldenRecord(
            canonical_patient_id=UUID(canonical_patient_id),
            source_system_ids=[],
            given_name=hydrate_event.first_name,
            family_name=hydrate_event.last_name,
            date_of_birth=hydrate_event.date_of_birth,
            gender=hydrate_event.gender,
            record_version=1,
            last_reconciled_at=datetime.now(),
        )

        await self.data_provider.upsert_golden_record(canonical_patient_id, golden_record)

    async def handle_source_event(self, msg) -> None:
        data = json.loads(msg.data.decode())
        logger.info("handle_source_event: subject=%s data=%s", msg.subject, data)
 
        source_system_name = data.get("source_system")
        handler = self.handlers.get(source_system_name)
        canonical_patient_id = await handler(data)
        # Update data with canonical_patient_id for downstream processing and reconciliation
        data["canonical_patient_id"] = canonical_patient_id

        try:
            await self.bus.publish(
                topic=f"reconcile.{source_system_name.lower()}",
                payload=data
            )
            await self.bus.flush()
        except nats.errors.UnexpectedEOF:
            # Connection may have been closed, but publish was queued
            pass

    async def fetch_golden_record(self, canonical_patient_id: str) -> dict | None:
        logger.info("fetch_golden_record: canonical_patient_id=%s", canonical_patient_id)
        return await self.data_provider.fetch_golden_record(canonical_patient_id)
    
    async def _handle_medicare_event(self, payload: dict) -> str:
        medicare_event = MedicareEvent.model_validate(payload)

        source_system = await self.data_provider.fetch_source_system(medicare_event.source_system)
        canonical_patient_id = await self._get_or_upsert_patient(medicare_event.medicare_id)

        logger.info("_handle_medicare_event: canonical_patient_id=%s", canonical_patient_id)

        await self._update_patient_info(
            canonical_patient_id=canonical_patient_id,
            source_system_id=source_system.source_system_id,
            source_patient_id=medicare_event.source_patient_id,
            first_name=medicare_event.first_name,
            last_name=medicare_event.last_name,
            date_of_birth=medicare_event.date_of_birth,
            gender=medicare_event.gender
        )

        return canonical_patient_id

    async def _handle_hospital_event(self, payload: dict) -> str:
        hospital_event = HospitalEvent.model_validate(payload)

        source_system = await self.data_provider.fetch_source_system(hospital_event.source_system)
        canonical_patient_id = await self._get_or_upsert_patient(hospital_event.medicare_id)

        await self._update_patient_info(
            canonical_patient_id=canonical_patient_id,
            source_system_id=source_system.source_system_id,
            source_patient_id=hospital_event.source_patient_id,
            first_name=hospital_event.first_name,
            last_name=hospital_event.last_name,
            date_of_birth=hospital_event.date_of_birth,
            gender=hospital_event.gender
        )

        return canonical_patient_id

    async def _handle_lab_event(self, payload: dict) -> str:
        lab_event = LabEvent.model_validate(payload)
        
        source_system = await self.data_provider.fetch_source_system(lab_event.source_system)
        canonical_patient_id = await self._get_or_upsert_patient(lab_event.medicare_id)

        await self._update_patient_info(
            canonical_patient_id=canonical_patient_id,
            source_system_id=source_system.source_system_id,
            source_patient_id=lab_event.source_patient_id,
            first_name=lab_event.patient_first_name,
            last_name=lab_event.patient_last_name,
            date_of_birth=lab_event.date_of_birth,
            gender=lab_event.gender
        )

        return canonical_patient_id

    async def _get_or_upsert_patient(self, shared_identifier: str) -> str:
        canonical_patient_id = await self.data_provider.fetch_patient(shared_identifier)
        if not canonical_patient_id:
            canonical_patient_id = await self.data_provider.upsert_patient(shared_identifier)
        return canonical_patient_id
    
    async def _update_patient_info(
        self,
            canonical_patient_id: str, 
            source_system_id: int,
            source_patient_id: str,
            first_name: str,
            last_name: str,
            date_of_birth: date,
            gender: str
    ) -> None:

        await asyncio.gather(
            self.data_provider.upsert_source_identity(
                canonical_patient_id,
                source_system_id=source_system_id,
                source_patient_id=source_patient_id,
            ),
            self.data_provider.upsert_golden_record(
                canonical_patient_id,
                GoldenRecord(
                    canonical_patient_id=UUID(canonical_patient_id),
                    source_system_ids=[source_system_id],
                    given_name=first_name,
                    family_name=last_name,
                    date_of_birth=date_of_birth,
                    gender=gender,
                )
            )
        )
        
       