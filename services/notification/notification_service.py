class NotificationService:
    async def handle_risk_computed(self, msg) -> None:
        # TODO: Parse risk_tier from msg payload.
        # TODO: Route alert for High/Critical risk tier to console log or WEBHOOK_URL.
        # TODO: WEBHOOK_URL = os.getenv("WEBHOOK_URL") — placeholder for outbound webhook delivery.
        print(f"[NotificationService] risk.computed received: {msg.data}")
