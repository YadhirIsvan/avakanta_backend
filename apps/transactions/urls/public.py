from django.urls import path
from ..views.public import SellerLeadCreateView

urlpatterns = [
    path('seller-leads', SellerLeadCreateView.as_view(), name='public-seller-leads'),
]
