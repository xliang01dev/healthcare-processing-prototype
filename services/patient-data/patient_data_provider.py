from shared.data_provider import DataProvider


class PatientDataProvider(DataProvider):
    """
    Postgres access for the Patient Data service.
    Schema: patient_data (patients, source_systems, source_identities, golden_records)
    """

    async def upsert_patient(self, shared_identifier: str) -> str | None:
        # TODO: INSERT INTO patient_data.patients (shared_identifier)
        #   VALUES ($1) ON CONFLICT (shared_identifier) DO NOTHING;
        #   SELECT canonical_patient_id FROM patient_data.patients WHERE shared_identifier = $1;
        return None

    async def upsert_source_identity(
        self, canonical_patient_id: str, source_system_id: int, source_patient_id: str
    ) -> None:
        # TODO: INSERT INTO patient_data.source_identities
        #   (canonical_patient_id, source_system_id, source_patient_id)
        #   VALUES ($1, $2, $3) ON CONFLICT DO NOTHING;
        pass

    async def upsert_golden_record(self, canonical_patient_id: str, record: dict) -> None:
        # TODO: INSERT INTO patient_data.golden_records
        #   (canonical_patient_id, source_system_ids, given_name, family_name, date_of_birth, gender, payload, record_version, last_reconciled_at)
        #   VALUES ($1, $2, $3, $4, $5, $6, $7, 1, NOW())
        #   ON CONFLICT (canonical_patient_id) DO UPDATE SET
        #     source_system_ids = EXCLUDED.source_system_ids,
        #     given_name = EXCLUDED.given_name,
        #     family_name = EXCLUDED.family_name,
        #     date_of_birth = EXCLUDED.date_of_birth,
        #     gender = EXCLUDED.gender,
        #     payload = EXCLUDED.payload,
        #     record_version = patient_data.golden_records.record_version + 1,
        #     last_reconciled_at = NOW();
        pass

    async def fetch_golden_record(self, canonical_patient_id: str) -> dict | None:
        # TODO: SELECT * FROM patient_data.golden_records
        #   WHERE canonical_patient_id = $1;
        return None
