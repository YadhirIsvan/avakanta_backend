from datetime import date

from django.db import transaction
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.properties.models import Property, PropertyAssignment
from apps.appointments.models import Appointment, AppointmentSettings
from apps.transactions.models import PurchaseProcess
from apps.users.models import TenantMembership
from core.utils import generate_matricula
from ..serializers.public import CreateAppointmentSerializer
from ..services import AvailabilityService


class AppointmentSlotsView(APIView):
    permission_classes = [AllowAny]

    def get(self, request):
        property_id = request.query_params.get('property_id')
        date_str = request.query_params.get('date')

        if not property_id or not date_str:
            return Response(
                {'error': 'property_id y date son requeridos.'},
                status=400,
            )

        try:
            property_id = int(property_id)
        except ValueError:
            return Response({'error': 'property_id debe ser un entero.'}, status=400)

        try:
            target_date = date.fromisoformat(date_str)
        except ValueError:
            return Response(
                {'error': 'Formato de fecha inválido. Use YYYY-MM-DD.'},
                status=400,
            )

        if target_date < date.today():
            return Response({'error': 'La fecha no puede ser en el pasado.'}, status=400)

        svc = AvailabilityService()
        result = svc.get_available_slots(property_id, target_date)

        if result['agent'] is None:
            return Response(
                {'error': 'La propiedad no tiene un agente asignado.'},
                status=400,
            )

        return Response({
            'date': date_str,
            'agent': result['agent'],
            'available_slots': result['available_slots'],
            'slot_duration_minutes': result['slot_duration_minutes'],
        })


class CreateAppointmentView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, pk):
        # 1. Obtener la propiedad
        try:
            prop = Property.objects.select_related('tenant').get(
                pk=pk, is_active=True, listing_type='sale', status='disponible'
            )
        except Property.DoesNotExist:
            return Response({'error': 'Propiedad no encontrada.'}, status=404)

        # 2. Validar input
        serializer = CreateAppointmentSerializer(
            data=request.data, context={'request': request}
        )
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        data = serializer.validated_data
        target_date = data['date']
        target_time = data['time']

        # 3. Obtener agente visible
        assignment = (
            PropertyAssignment.objects
            .filter(property=prop, is_visible=True)
            .select_related('agent_membership__user')
            .first()
        )
        if not assignment:
            return Response(
                {'error': 'La propiedad no tiene un agente asignado.'}, status=400
            )

        agent_membership = assignment.agent_membership
        svc = AvailabilityService()

        # 4. Validar disponibilidad del slot
        availability = svc.get_available_slots(prop.pk, target_date)
        time_str = target_time.strftime('%H:%M')
        if time_str not in availability['available_slots']:
            return Response(
                {'error': 'El agente no tiene disponibilidad en ese horario.'}, status=400
            )

        # 5. Obtener slot_duration de los settings
        try:
            settings = AppointmentSettings.objects.get(tenant=prop.tenant)
            slot_duration = settings.slot_duration_minutes
        except AppointmentSettings.DoesNotExist:
            slot_duration = 60

        # 6. Determinar client_membership si el usuario está autenticado
        client_membership = None
        try:
            user = request.user
            if user and user.is_authenticated:
                # Buscar membership en el tenant de la propiedad O cualquier membership activa
                client_membership = TenantMembership.objects.filter(
                    user=user, tenant=prop.tenant, is_active=True
                ).first()
                if not client_membership:
                    client_membership = TenantMembership.objects.filter(
                        user=user, is_active=True
                    ).first()
        except Exception:
            pass

        # 7. Crear la cita de forma atómica
        with transaction.atomic():
            # 7a. Re-verify availability one more time before creating
            # This prevents race condition where another concurrent request booked the slot
            rechecked_availability = svc.get_available_slots(prop.pk, target_date)
            if time_str not in rechecked_availability['available_slots']:
                return Response(
                    {'error': 'El agente no tiene disponibilidad en ese horario. El slot fue reservado por otro cliente.'}, status=409
                )

            # Resolve authenticated user for contact info
            resolved_user = client_membership.user if client_membership else None

            matricula = generate_matricula(prop.tenant_id)
            appointment = Appointment.objects.create(
                tenant=prop.tenant,
                property=prop,
                agent_membership=agent_membership,
                client_membership=client_membership,
                client_name=data.get('name', '') or (
                    resolved_user.get_full_name() if resolved_user else ''
                ),
                client_email=data.get('email', '') or (
                    resolved_user.email if resolved_user else ''
                ),
                client_phone=data.get('phone', ''),
                matricula=matricula,
                scheduled_date=target_date,
                scheduled_time=target_time,
                duration_minutes=slot_duration,
                status=Appointment.Status.PROGRAMADA,
            )
            
            # 7b. Crear PurchaseProcess si el cliente está autenticado
            if client_membership:
                # Verificar si no existe un PurchaseProcess activo para esta propiedad y cliente
                purchase_process_exists = PurchaseProcess.objects.filter(
                    property=prop,
                    client_membership=client_membership,
                    status__in=['lead', 'visita', 'interes', 'pre_aprobacion', 'avaluo', 'credito', 'docs_finales', 'escrituras']
                ).exists()
                
                if not purchase_process_exists:
                    PurchaseProcess.objects.create(
                        tenant=prop.tenant,
                        property=prop,
                        client_membership=client_membership,
                        agent_membership=agent_membership,
                        status=PurchaseProcess.Status.LEAD,
                    )

        agent_user = agent_membership.user
        return Response({
            'id': appointment.pk,
            'matricula': appointment.matricula,
            'scheduled_date': str(appointment.scheduled_date),
            'scheduled_time': appointment.scheduled_time.strftime('%H:%M:%S'),
            'duration_minutes': appointment.duration_minutes,
            'status': appointment.status,
            'property': {'id': prop.pk, 'title': prop.title},
            'agent': {'name': agent_user.get_full_name() or agent_user.email},
        }, status=201)
