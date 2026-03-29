import logging

from shared.message_bus import MessageBus

logger = logging.getLogger(__name__)


class NotificationService:
    def __init__(self, bus: MessageBus) -> None:
        self.bus = bus

    async def handle_risk_computed(self, msg) -> None:
        logger.info("handle_risk_computed: data=%s", msg.data)
        # TODO: Parse risk_tier from msg payload.
        # TODO: Route alert for High/Critical risk tier to console log or WEBHOOK_URL.
        # TODO: WEBHOOK_URL = os.getenv("WEBHOOK_URL") — placeholder for outbound webhook delivery.
