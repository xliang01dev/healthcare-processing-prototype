import logging

from fastapi import APIRouter, HTTPException

from shared.singleton_store import get_singleton
from npi_service import NPIRegistryService
from npi_models import Provider

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/v1/npi", tags=["npi"])


@router.get("/{npi_id}", response_model=Provider)
async def get_provider(npi_id: str):
    """
    Look up a provider by NPI.

    Args:
        npi_id: 10-digit National Provider Identifier

    Returns:
        Provider with name, title, specialty.

    Raises:
        404: Provider not found.
    """
    service = get_singleton(NPIRegistryService)
    provider = await service.get_provider(npi_id)

    if not provider:
        logger.warning("get_provider: npi not found=%s", npi_id)
        raise HTTPException(status_code=404, detail=f"NPI {npi_id} not found")

    logger.info("get_provider: found npi=%s name=%s %s", npi_id, provider.first_name, provider.last_name)
    return provider


@router.get("", response_model=list[Provider])
async def list_providers(limit: int = 100, offset: int = 0):
    """
    List all providers.

    Args:
        limit: Maximum results per page (default 100)
        offset: Results to skip (default 0)

    Returns:
        List of providers.
    """
    service = get_singleton(NPIRegistryService)
    providers = await service.list_providers(limit, offset)
    logger.info("list_providers: returned %d providers", len(providers))
    return providers
