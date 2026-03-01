from datetime import date

from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

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
