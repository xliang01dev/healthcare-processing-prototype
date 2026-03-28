from shared.data_provider import DataProvider


class MpiDataProvider(DataProvider):
    """
    Postgres access for the MPI service.
    Schema: mpi (mpi_patients, mpi_source_identities)
    """

    async def upsert_patient(self, shared_identifier: str) -> str | None:
        # TODO: INSERT INTO mpi.mpi_patients (shared_identifier)
        #   VALUES ($1) ON CONFLICT (shared_identifier) DO NOTHING;
        #   SELECT canonical_patient_id FROM mpi.mpi_patients WHERE shared_identifier = $1;
        return None

    async def fetch_patient_by_identifier(self, shared_identifier: str) -> dict | None:
        # TODO: SELECT canonical_patient_id, shared_identifier
        #   FROM mpi.mpi_patients WHERE shared_identifier = $1;
        return None

    async def fetch_source_identities(self, canonical_patient_id: str) -> list:
        # TODO: SELECT source_system, source_patient_id
        #   FROM mpi.mpi_source_identities WHERE canonical_patient_id = $1;
        return []

    async def upsert_source_identity(
        self, canonical_patient_id: str, source_system: str, source_patient_id: str
    ) -> None:
        # TODO: INSERT INTO mpi.mpi_source_identities
        #   (canonical_patient_id, source_system, source_patient_id)
        #   VALUES ($1, $2, $3) ON CONFLICT DO NOTHING;
        pass
