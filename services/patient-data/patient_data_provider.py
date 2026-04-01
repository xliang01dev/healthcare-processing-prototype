import logging
from uuid import UUID

from shared.data_provider import DataProvider
from patient_data_models import GoldenRecord, SourceIdentity, SourceSystem, PatientInfo

logger = logging.getLogger(__name__)


class PatientDataProvider(DataProvider):
    """
    Postgres access for the Patient Data service.
    Schema: patient_data (patients, source_systems, source_identities, golden_records)
    """

    async def fetch_patient(self, shared_identifier: str) -> PatientInfo | None:
        logger.info("fetch_patient: shared_identifier=%s", shared_identifier)

        row = await self.fetch_row(
            "SELECT canonical_patient_id, shared_identifier FROM patient_data.patients WHERE shared_identifier = $1",
            shared_identifier
        )
        return PatientInfo(canonical_patient_id=row[0], shared_identifier=row[1]) if row else None

    async def upsert_patient(self, shared_identifier: str) -> PatientInfo:
        logger.info("upsert_patient: shared_identifier=%s", shared_identifier)

        await self.execute(
            "INSERT INTO patient_data.patients (shared_identifier) VALUES ($1) ON CONFLICT (shared_identifier) DO NOTHING",
            shared_identifier
        )
        return await self.fetch_patient(shared_identifier)

    async def fetch_source_system(self, source_system_name: str) -> SourceSystem | None:
        logger.info("fetch_source_system: source_system_name=%s", source_system_name)

        row = await self.fetch_row(
            "SELECT source_system_id, source_system_name FROM patient_data.source_systems WHERE source_system_name = $1",
            source_system_name,
        )
        return SourceSystem(source_system_id=row[0], source_system_name=row[1]) if row else None

    async def fetch_source_identity(
        self, source_system_id: int, source_patient_id: str
    ) -> SourceIdentity | None:
        logger.info(
            "fetch_source_identity: source_system_id=%s source_patient_id=%s",
            source_system_id,
            source_patient_id,
        )

        row = await self.fetch_row(
            "SELECT id, canonical_patient_id, source_system_id, source_patient_id, created_at FROM patient_data.source_identities WHERE source_system_id = $1 AND source_patient_id = $2",
            source_system_id,
            source_patient_id,
        )
        return (
            SourceIdentity(
                id=row[0],
                canonical_patient_id=row[1],
                source_system_id=row[2],
                source_patient_id=row[3],
                created_at=row[4],
            )
            if row
            else None
        )

    async def upsert_source_identity(
        self, canonical_patient_id: str, source_system_id: int, source_patient_id: str
    ) -> None:
        logger.info(
            "upsert_source_identity: canonical_patient_id=%s source_system_id=%s source_patient_id=%s",
            canonical_patient_id,
            source_system_id,
            source_patient_id,
        )

        sql = """
        INSERT INTO patient_data.source_identities
          (canonical_patient_id, source_system_id, source_patient_id)
        VALUES ($1, $2, $3)
        ON CONFLICT (source_system_id, source_patient_id) DO NOTHING
        """

        await self.execute(sql, canonical_patient_id, source_system_id, source_patient_id)

    async def upsert_golden_record(self, canonical_patient_id: str, record: GoldenRecord) -> None:
        logger.info("upsert_golden_record: canonical_patient_id=%s", canonical_patient_id)

        sql = """
        INSERT INTO patient_data.golden_records
          (canonical_patient_id, source_system_ids, given_name, family_name, date_of_birth, gender, record_version, last_reconciled_at)
        VALUES ($1, $2, $3, $4, $5, $6, 1, NOW())
        ON CONFLICT (canonical_patient_id) DO UPDATE SET
          source_system_ids = EXCLUDED.source_system_ids,
          given_name = EXCLUDED.given_name,
          family_name = EXCLUDED.family_name,
          date_of_birth = EXCLUDED.date_of_birth,
          gender = EXCLUDED.gender,
          record_version = golden_records.record_version + 1,
          last_reconciled_at = NOW()
        """

        await self.execute(
            sql,
            canonical_patient_id,
            record.source_system_ids,
            record.given_name,
            record.family_name,
            record.date_of_birth,
            record.gender,
        )

    async def fetch_golden_record(self, canonical_patient_id: str) -> GoldenRecord | None:
        logger.info("fetch_golden_record: canonical_patient_id=%s", canonical_patient_id)

        row = await self.fetch_row(
            """
            SELECT 
                canonical_patient_id, 
                source_system_ids, 
                given_name,
                family_name, 
                date_of_birth, 
                gender 
            FROM
                patient_data.golden_records
            WHERE
                canonical_patient_id = $1
            """,
            canonical_patient_id,
        )
        return (
            GoldenRecord(
                canonical_patient_id=row[0],
                source_system_ids=row[1],
                given_name=row[2],
                family_name=row[3],
                date_of_birth=row[4],
                gender=row[5]
            )
            if row
            else None
        )
