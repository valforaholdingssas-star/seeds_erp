from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.ai.models import Document
from apps.ai.serializers import AskSerializer, DocumentSerializer, SearchSerializer
from apps.ai.services import ask_agent, ingest_document, similarity_search
from apps.users.permissions import IsAdmin, IsModuleRole


class DocumentViewSet(viewsets.ModelViewSet):
    permission_module = "ai"
    queryset = Document.objects.all()
    serializer_class = DocumentSerializer
    filterset_fields = ["kind", "ref_type", "ref_id"]
    search_fields = ["title", "content"]
    ordering_fields = ["created_at", "kind", "title"]

    def get_permissions(self):
        if self.action in {"list", "retrieve", "search"}:
            self.module_roles = ["VENTAS", "LOGISTICA", "CONTABILIDAD", "SUPERVISOR", "VIEWER"]
            return [IsModuleRole()]
        return [IsAdmin()]

    def perform_create(self, serializer):
        data = serializer.validated_data
        doc = ingest_document(
            kind=data["kind"],
            content=data["content"],
            title=data.get("title") or "",
            ref_type=data.get("ref_type") or "",
            ref_id=data.get("ref_id") or "",
            metadata=data.get("metadata") or {},
            actor=self.request.user,
        )
        serializer.instance = doc

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        out = DocumentSerializer(serializer.instance)
        return Response(out.data, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=["get"])
    def search(self, request):
        ser = SearchSerializer(data=request.query_params)
        ser.is_valid(raise_exception=True)
        hits = similarity_search(
            ser.validated_data["q"],
            limit=ser.validated_data.get("limit") or 5,
            kind=ser.validated_data.get("kind") or None,
        )
        return Response({"results": hits})


class AgentAskView(APIView):
    permission_module = "ai"
    permission_crud = "r"
    def get_permissions(self):
        self.module_roles = ["VENTAS", "LOGISTICA", "CONTABILIDAD", "SUPERVISOR", "VIEWER"]
        return [IsModuleRole()]

    def post(self, request):
        ser = AskSerializer(data=request.data)
        ser.is_valid(raise_exception=True)
        result = ask_agent(ser.validated_data["question"], actor=request.user)
        return Response(result)
