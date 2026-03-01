class TenantQuerySetMixin:
    """
    Filtra automáticamente el queryset por el tenant del request
    y asigna el tenant en perform_create sin intervención del serializer.

    El orden de herencia importa:
        class MyViewSet(TenantQuerySetMixin, ModelViewSet): ...
    """

    def get_queryset(self):
        qs = super().get_queryset()
        tenant = getattr(self.request, 'tenant', None)
        if tenant is None:
            return qs.none()
        return qs.filter(tenant=tenant)

    def perform_create(self, serializer):
        serializer.save(tenant=self.request.tenant)
