import os

from django.conf import settings
from django.db.models import Count, Sum

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.pagination import StandardPagination
from core.permissions import IsClient
from core.validators import (
    validate_file_type, validate_file_size,
    ALLOWED_DOCUMENT_TYPES, MAX_DOCUMENT_SIZE_MB,
)
from apps.users.models import TenantMembership
from apps.properties.models import PropertyDocument
from ..models import SaleProcess, PurchaseProcess
from ..serializers.client import (
    ClientSaleProcessListSerializer,
    ClientSaleProcessDetailSerializer,
    ClientPurchaseProcessListSerializer,
    ClientPurchaseProcessDetailSerializer,
)


def _get_client_membership(request):
    return TenantMembership.objects.get(
        user=request.user, tenant=request.tenant, is_active=True
    )


def _sale_qs(membership):
    return (
        SaleProcess.objects
        .filter(client_membership=membership)
        .select_related(
            'property__city__state',
            'agent_membership__user',
        )
        .prefetch_related('property__images')
        .order_by('-created_at')
    )


def _purchase_qs(membership):
    return (
        PurchaseProcess.objects
        .filter(client_membership=membership)
        .select_related(
            'property__city__state',
            'agent_membership__user',
        )
        .prefetch_related('property__images', 'documents')
        .order_by('-created_at')
    )


# ── Sale Processes ────────────────────────────────────────────────────────────

class ClientSaleListView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request):
        membership = _get_client_membership(request)
        qs = _sale_qs(membership)

        # Global stats
        agg = qs.aggregate(
            total_properties=Count('id'),
            total_views=Sum('property__views'),
            total_value=Sum('property__price'),
        )
        total_interested = sum(
            sp.property.purchase_processes.count() for sp in qs
        )

        return Response({
            'stats': {
                'total_properties': agg['total_properties'] or 0,
                'total_views': agg['total_views'] or 0,
                'total_interested': total_interested,
                'total_value': str(agg['total_value'] or 0),
            },
            'results': ClientSaleProcessListSerializer(qs, many=True).data,
        })


class ClientSaleDetailView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request, pk):
        membership = _get_client_membership(request)
        process = _sale_qs(membership).filter(pk=pk).first()
        if not process:
            return Response({'error': 'Proceso no encontrado.'}, status=404)
        return Response(ClientSaleProcessDetailSerializer(process).data)


# ── Purchase Processes ────────────────────────────────────────────────────────

class ClientPurchaseListView(APIView):
    permission_classes = [IsAuthenticated, IsClient]
    pagination_class = StandardPagination

    def get(self, request):
        membership = _get_client_membership(request)
        qs = _purchase_qs(membership)

        paginator = self.pagination_class()
        page = paginator.paginate_queryset(qs, request)
        return paginator.get_paginated_response(
            ClientPurchaseProcessListSerializer(page, many=True).data
        )


class ClientPurchaseDetailView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def get(self, request, pk):
        membership = _get_client_membership(request)
        process = _purchase_qs(membership).filter(pk=pk).first()
        if not process:
            return Response({'error': 'Proceso no encontrado.'}, status=404)
        return Response(ClientPurchaseProcessDetailSerializer(process).data)


# Stages that allow document upload
ALLOW_UPLOAD_STAGES = {'pre_aprobacion', 'credito', 'docs_finales'}


class ClientPurchaseDocumentUploadView(APIView):
    permission_classes = [IsAuthenticated, IsClient]

    def post(self, request, pk):
        membership = _get_client_membership(request)

        process = PurchaseProcess.objects.filter(
            pk=pk, client_membership=membership
        ).select_related('property').first()
        if not process:
            return Response({'error': 'Proceso no encontrado.'}, status=404)

        if process.status not in ALLOW_UPLOAD_STAGES:
            return Response(
                {'error': f'La etapa actual ({process.status}) no permite subir documentos.'},
                status=403,
            )

        file = request.FILES.get('file')
        name = request.data.get('name', '').strip()

        if not file:
            return Response({'error': 'Se requiere el archivo.'}, status=400)
        if not name:
            return Response({'error': 'Se requiere el nombre del documento.'}, status=400)

        try:
            validate_file_type(file, ALLOWED_DOCUMENT_TYPES)
            validate_file_size(file, MAX_DOCUMENT_SIZE_MB)
        except Exception as e:
            return Response({'error': str(e)}, status=400)

        rel_path = f'documents/purchases/{process.pk}/{file.name}'
        abs_path = os.path.join(settings.MEDIA_ROOT, rel_path)
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, 'wb+') as dest:
            for chunk in file.chunks():
                dest.write(chunk)

        doc = PropertyDocument.objects.create(
            property=process.property,
            uploaded_by_membership=membership,
            purchase_process=process,
            name=name,
            file_url=f'/media/{rel_path}',
            mime_type=file.content_type,
            size_bytes=file.size,
            document_stage=process.status,
        )

        return Response({
            'id': doc.pk,
            'name': doc.name,
            'file_url': doc.file_url,
            'mime_type': doc.mime_type,
            'size_bytes': doc.size_bytes,
            'document_stage': doc.document_stage,
        }, status=201)
