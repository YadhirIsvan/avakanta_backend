from rest_framework import serializers

from ..models import Appointment

# Valid transitions for appointment status
VALID_TRANSITIONS = {
    Appointment.Status.PROGRAMADA: [
        Appointment.Status.CONFIRMADA,
        Appointment.Status.CANCELADA,
        Appointment.Status.NO_SHOW,
        Appointment.Status.REAGENDADA,
    ],
    Appointment.Status.CONFIRMADA: [
        Appointment.Status.EN_PROGRESO,
        Appointment.Status.CANCELADA,
        Appointment.Status.NO_SHOW,
        Appointment.Status.REAGENDADA,
    ],
    Appointment.Status.EN_PROGRESO: [
        Appointment.Status.COMPLETADA,
        Appointment.Status.CANCELADA,
        Appointment.Status.NO_SHOW,
        Appointment.Status.REAGENDADA,
    ],
}


class AgentAppointmentListSerializer(serializers.ModelSerializer):
    property = serializers.SerializerMethodField()

    class Meta:
        model = Appointment
        fields = [
            'id', 'matricula', 'scheduled_date', 'scheduled_time',
            'duration_minutes', 'status', 'client_name', 'client_phone', 'property',
        ]

    def get_property(self, obj):
        return {'id': obj.property_id, 'title': obj.property.title}


class AgentAppointmentStatusSerializer(serializers.Serializer):
    status = serializers.ChoiceField(choices=Appointment.Status.choices)
    notes = serializers.CharField(required=False, allow_blank=True, default='')
