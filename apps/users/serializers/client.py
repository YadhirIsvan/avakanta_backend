from rest_framework import serializers

from apps.users.models import User, ClientFinancialProfile, ClientProfile


class ClientDashboardSerializer(serializers.Serializer):
    client = serializers.DictField()
    credit_score = serializers.IntegerField(allow_null=True)
    recent_activity = serializers.ListField()
    sale_processes_preview = serializers.ListField()
    purchase_processes_preview = serializers.ListField()


class ClientProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'email', 'first_name', 'last_name', 'phone', 'avatar', 'city']
        read_only_fields = ['id', 'email']


class ClientProfileUpdateSerializer(serializers.Serializer):
    first_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    last_name = serializers.CharField(max_length=150, required=False, allow_blank=True)
    phone = serializers.CharField(max_length=50, required=False, allow_blank=True, allow_null=True)
    city = serializers.CharField(max_length=150, required=False, allow_blank=True, allow_null=True)
    avatar = serializers.CharField(max_length=500, required=False, allow_blank=True, allow_null=True)


class ClientAvatarUploadSerializer(serializers.Serializer):
    avatar = serializers.ImageField()


class ClientNotificationPreferencesSerializer(serializers.Serializer):
    new_properties = serializers.BooleanField()
    price_updates = serializers.BooleanField()
    appointment_reminders = serializers.BooleanField()
    offers = serializers.BooleanField()


class ClientProfileDetailSerializer(serializers.ModelSerializer):
    class Meta:
        model = ClientProfile
        fields = ['occupation', 'residence_location', 'desired_credit_type', 'desired_property_type', 'updated_at']


class ClientFinancialProfileSerializer(serializers.ModelSerializer):
    """Serializer para guardar/actualizar perfil financiero del cliente."""
    class Meta:
        model = ClientFinancialProfile
        fields = [
            'id',
            'loan_type',
            'monthly_income',
            'partner_monthly_income',
            'savings_for_enganche',
            'has_infonavit',
            'infonavit_subcuenta_balance',
            'calculated_budget',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'calculated_budget', 'created_at', 'updated_at']


class ClientFinancialProfileCreateUpdateSerializer(serializers.Serializer):
    """Serializer para crear/actualizar perfil financiero."""
    loan_type = serializers.ChoiceField(choices=ClientFinancialProfile.LoanType.choices)
    monthly_income = serializers.DecimalField(max_digits=12, decimal_places=2)
    partner_monthly_income = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)
    savings_for_enganche = serializers.DecimalField(max_digits=12, decimal_places=2)
    has_infonavit = serializers.BooleanField(required=False, default=False)
    infonavit_subcuenta_balance = serializers.DecimalField(max_digits=12, decimal_places=2, required=False, allow_null=True)

    def validate(self, data):
        loan_type = data.get('loan_type')
        # Validar que si es conyugal, tenga partner_monthly_income
        if loan_type == 'conyugal' and not data.get('partner_monthly_income'):
            raise serializers.ValidationError("Partner monthly income is required for conyugal loans")
        # Validar que si tiene infonavit, tenga saldo
        if data.get('has_infonavit') and not data.get('infonavit_subcuenta_balance'):
            raise serializers.ValidationError("Infonavit subcuenta balance is required when has_infonavit is True")
        return data
