from django.contrib import admin
from .models import BusCollection, BusData


class BusDataInline(admin.TabularInline):
    model = BusData
    extra = 0
    readonly_fields = ('plate_no', 'remain_seat_cnt', 'station_seq')


@admin.register(BusCollection)
class BusCollectionAdmin(admin.ModelAdmin):
    list_display = ('route_id', 'collection_date', 'query_time', 'bus_count', 'is_error', 'is_skipped')
    list_filter = ('collection_date', 'is_error', 'is_skipped', 'route_id')
    search_fields = ('route_id',)
    date_hierarchy = 'collection_date'
    ordering = ('-query_time',)
    readonly_fields = ('created_at',)
    inlines = [BusDataInline]
    
    def bus_count(self, obj):
        return obj.buses.count()
    bus_count.short_description = '버스 수'


@admin.register(BusData)
class BusDataAdmin(admin.ModelAdmin):
    list_display = ('collection', 'plate_no', 'remain_seat_cnt', 'station_seq')
    list_filter = ('collection__collection_date', 'remain_seat_cnt')
    search_fields = ('plate_no', 'collection__route_id')
    ordering = ('-collection__query_time', 'plate_no')
