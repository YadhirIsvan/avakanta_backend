from django.urls import path
from ..views.client import (
    ClientSaleListView,
    ClientSaleDetailView,
    ClientPurchaseListView,
    ClientPurchaseDetailView,
    ClientPurchaseDocumentUploadView,
)

urlpatterns = [
    path('sales', ClientSaleListView.as_view(), name='client-sale-list'),
    path('sales/<int:pk>', ClientSaleDetailView.as_view(), name='client-sale-detail'),
    path('purchases', ClientPurchaseListView.as_view(), name='client-purchase-list'),
    path('purchases/<int:pk>', ClientPurchaseDetailView.as_view(), name='client-purchase-detail'),
    path('purchases/<int:pk>/documents', ClientPurchaseDocumentUploadView.as_view(), name='client-purchase-documents'),
]
