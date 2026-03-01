from datetime import date, time

from rest_framework import serializers


class CreateAppointmentSerializer(serializers.Serializer):
    date = serializers.DateField()
    time = serializers.TimeField(format='%H:%M', input_formats=['%H:%M', '%H:%M:%S'])
    name = serializers.CharField(max_length=255, required=False, allow_blank=True)
    email = serializers.EmailField(required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True)

    def validate_date(self, value):
        if value < date.today():
            raise serializers.ValidationError('La fecha no puede ser en el pasado.')
        return value

    def validate(self, attrs):
        # Visitantes no autenticados deben proveer name, email, phone
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            for field in ('name', 'email', 'phone'):
                if not attrs.get(field):
                    raise serializers.ValidationError(
                        {field: 'Este campo es obligatorio para visitantes no registrados.'}
                    )
        return attrs
