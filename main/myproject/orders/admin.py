"""[US-04] Admin registration for Order and OrderItem."""

from django.contrib import admin

from .models import Order, OrderItem, StockDeduction


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('name_snapshot', 'unit_price', 'quantity', 'line_total')


class StockDeductionInline(admin.TabularInline):
    model = StockDeduction
    extra = 0
    readonly_fields = ('ingredient', 'lot', 'quantity')


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'restaurant', 'created_at', 'total_amount', 'status', 'created_by')
    list_filter = ('status', 'created_at')
    inlines = [OrderItemInline]


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('id', 'order', 'name_snapshot', 'quantity', 'unit_price', 'line_total')
    inlines = [StockDeductionInline]
