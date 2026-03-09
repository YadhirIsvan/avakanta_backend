from django.urls import path
from ..views.public import SellerLeadCreateView, SaleProcessCreateView

urlpatterns = [
    path('seller-leads', SellerLeadCreateView.as_view(), name='public-seller-leads'),
    path('sale-processes', SaleProcessCreateView.as_view(), name='public-sale-processes'),
]
