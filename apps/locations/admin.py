from django.contrib import admin

from .models import Country, State, City, Amenity


@admin.register(Country)
class CountryAdmin(admin.ModelAdmin):
    list_display = ('name', 'code')
    search_fields = ('name', 'code')


@admin.register(State)
class StateAdmin(admin.ModelAdmin):
    list_display = ('name', 'country', 'code')
    list_filter = ('country',)
    search_fields = ('name', 'code')
    raw_id_fields = ('country',)


@admin.register(City)
class CityAdmin(admin.ModelAdmin):
    list_display = ('name', 'state')
    list_filter = ('state__country',)
    search_fields = ('name',)
    raw_id_fields = ('state',)


@admin.register(Amenity)
class AmenityAdmin(admin.ModelAdmin):
    list_display = ('name', 'icon')
    search_fields = ('name',)
