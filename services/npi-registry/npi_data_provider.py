import logging

from shared.data_provider import DataProvider
from npi_models import Provider

logger = logging.getLogger(__name__)


class NPIDataProvider(DataProvider):
    """
    Postgres access for the NPI Registry service.

    Schema: npi_registry (providers)
    """

    async def get_provider_by_npi(self, npi: str) -> Provider | None:
        """Fetch provider details by NPI. Returns None if not found."""
        logger.info("get_provider_by_npi: npi=%s", npi)
        sql = """
            SELECT npi, first_name, last_name, title, specialty
            FROM npi_registry.providers
            WHERE npi = %s
        """
        row = await self.fetchrow(sql, npi)

        if row:
            return Provider(
                npi=row[0],
                first_name=row[1],
                last_name=row[2],
                title=row[3],
                specialty=row[4],
            )
        return None

    async def list_providers(self, limit: int = 100, offset: int = 0) -> list[Provider]:
        """List all providers with pagination."""
        logger.info("list_providers: limit=%s offset=%s", limit, offset)
        sql = """
            SELECT npi, first_name, last_name, title, specialty
            FROM npi_registry.providers
            ORDER BY last_name, first_name
            LIMIT %s OFFSET %s
        """
        rows = await self.fetch(sql, limit, offset)

        return [
            Provider(
                npi=row[0],
                first_name=row[1],
                last_name=row[2],
                title=row[3],
                specialty=row[4],
            )
            for row in rows
        ]
