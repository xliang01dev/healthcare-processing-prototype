import json
import logging

from reconciliation_event_worker_data_provider import ReconciliationEventWorkerDataProvider
from patient_event_reconciliation_rules import PatientEventReconciliationRules
from shared.message_bus import MessageBus
from shared.event_models import ReconciliationTask

logger = logging.getLogger(__name__)


class ReconciliationEventWorkerService:
    def __init__(
            self,
            data_provider: ReconciliationEventWorkerDataProvider,
            reconciliation_rules: PatientEventReconciliationRules,
            bus: MessageBus
        ) -> None:
        self.data_provider = data_provider
        self.reconciliation_rules = reconciliation_rules
        self.bus = bus

    async def handle_reconciliation_task(self, payload: dict) -> None:
        """Process a reconciliation task: fetch event logs, reconcile, publish result."""
        logger.info("handle_reconciliation_task: data=%s", payload)
        task = ReconciliationTask.model_validate(payload)

        # Fetch the event logs in this debounce window
        event_logs = await self.data_provider.fetch_event_log_between(
            task.canonical_patient_id,
            from_event_log_id=task.start_event_log_id,
            to_event_log_id=task.end_event_log_id
        )

        # Apply reconciliation rules to produce ReconciledEvent
        reconciled_event = await self.reconciliation_rules.reconcile_events(
            canonical_patient_id=task.canonical_patient_id,
            event_logs=event_logs
        )

        # Publish result to timeline service
        if reconciled_event:
            await self.bus.publish(
                topic="reconciled.events",
                payload=reconciled_event.model_dump(mode='json')
            )
            logger.info("handle_reconciliation_task: published reconciled event for patient=%s", task.canonical_patient_id)
