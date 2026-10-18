from django.contrib import admin

from .models import Ingredient, StockIn


@admin.register(Ingredient)
class IngredientAdmin(admin.ModelAdmin):
    list_display = ['name', 'restaurant', 'barcode', 'stock_quantity', 'unit', 'price']
    list_filter = ['restaurant', 'unit']
    search_fields = ['name', 'barcode']


@admin.register(StockIn)
class StockInAdmin(admin.ModelAdmin):
    list_display = ['lot_code', 'ingredient', 'restaurant', 'quantity',
                    'remaining_quantity', 'expiry_date', 'received_at']
    list_filter = ['restaurant']
    search_fields = ['lot_code', 'ingredient__name']
