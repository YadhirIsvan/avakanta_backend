from django.urls import path
from ..views.admin import (
    AdminPurchaseProcessListCreateView,
    AdminPurchaseProcessStatusView,
    AdminPurchaseProcessDetailView,
    AdminSaleProcessListCreateView,
    AdminSaleProcessStatusView,
)

urlpatterns = [
    # Purchase processes
    path('purchase-processes', AdminPurchaseProcessListCreateView.as_view(), name='admin-purchase-list-create'),
    path('purchase-processes/<int:pk>/status', AdminPurchaseProcessStatusView.as_view(), name='admin-purchase-status'),
    path('purchase-processes/<int:pk>', AdminPurchaseProcessDetailView.as_view(), name='admin-purchase-detail'),
    # Sale processes
    path('sale-processes', AdminSaleProcessListCreateView.as_view(), name='admin-sale-list-create'),
    path('sale-processes/<int:pk>/status', AdminSaleProcessStatusView.as_view(), name='admin-sale-status'),
]
