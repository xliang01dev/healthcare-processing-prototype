import logging

from npi_data_provider import NPIDataProvider
from npi_models import Provider

logger = logging.getLogger(__name__)


class NPIRegistryService:
    """
    Business logic for NPI Registry lookups.
    """

    def __init__(self, data_provider: NPIDataProvider) -> None:
        self.data_provider = data_provider

    async def get_provider(self, npi: str) -> Provider | None:
        """
        Look up a provider by NPI.

        Args:
            npi: 10-digit National Provider Identifier

        Returns:
            Provider model with name, title, specialty, or None if not found.
        """
        logger.info("get_provider: npi=%s", npi)
        return await self.data_provider.get_provider_by_npi(npi)

    async def list_providers(self, limit: int = 100, offset: int = 0) -> list[Provider]:
        """
        List all providers.

        Args:
            limit: Maximum results per page (default 100)
            offset: Results to skip (default 0)

        Returns:
            List of Provider models.
        """
        logger.info("list_providers: limit=%s offset=%s", limit, offset)
        return await self.data_provider.list_providers(limit, offset)
