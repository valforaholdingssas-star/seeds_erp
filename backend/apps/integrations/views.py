from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.integrations.models import RawEventStatus, RawWebhookEvent
from apps.integrations.serializers import RawWebhookEventSerializer
from apps.users.permissions import IsAdmin, IsAdminOrSupervisor


class RawWebhookEventViewSet(viewsets.ReadOnlyModelViewSet):
    queryset = RawWebhookEvent.objects.all()
    serializer_class = RawWebhookEventSerializer
    permission_classes = [IsAdminOrSupervisor]
    filterset_fields = ["source", "status", "event_type"]
    search_fields = ["dedupe_key", "error", "event_type"]
    ordering_fields = ["received_at", "status", "attempts"]

    @action(detail=True, methods=["post"], permission_classes=[IsAdmin])
    def reprocess(self, request, pk=None):
        event = self.get_object()
        event.status = RawEventStatus.RECEIVED
        event.error = ""
        event.attempts = (event.attempts or 0) + 1
        event.processed_at = None
        event.save(
            update_fields=["status", "error", "attempts", "processed_at", "updated_at"]
        )
        from apps.sales.tasks import process_raw_event

        process_raw_event.delay(str(event.id))
        return Response(
            {
                "detail": "Evento marcado para reproceso.",
                "event": RawWebhookEventSerializer(event).data,
            },
            status=status.HTTP_202_ACCEPTED,
        )
