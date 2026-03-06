import os, django
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from apps.transactions.models import SellerLead
from apps.properties.models import Property

lead = SellerLead.objects.filter(status='converted').first()
if lead:
    print(f'SellerLead: {lead.full_name}')
    print(f'  location: {lead.location}')
    print(f'  square_meters: {lead.square_meters}')
    
    prop = Property.objects.filter(title__contains=lead.location).first() if lead.location else None
    if prop:
        print(f'\nProperty: {prop.title}')
        print(f'  city: {prop.city}')
        print(f'  address_neighborhood: {prop.address_neighborhood}')
        print(f'  construction_sqm: {prop.construction_sqm}')
        print(f'  land_sqm: {prop.land_sqm}')
    else:
        print(f'\nNo property found with location {lead.location}')
else:
    print('No converted SellerLead found')
