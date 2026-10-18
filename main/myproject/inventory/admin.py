from django.contrib import admin

from accounts.admin_scope import RestaurantOwnerAdmin
from accounts.models import CustomUser

from .models import Ingredient, StockIn


@admin.register(Ingredient)
class IngredientAdmin(RestaurantOwnerAdmin):
    list_display = ['name', 'restaurant', 'barcode', 'stock_quantity', 'unit', 'price']
    list_filter = ['unit']
    search_fields = ['name', 'barcode']


@admin.register(StockIn)
class StockInAdmin(RestaurantOwnerAdmin):
    list_display = ['lot_code', 'ingredient', 'restaurant', 'quantity',
                    'remaining_quantity', 'expiry_date', 'received_at']
    list_filter = ['expiry_date']
    search_fields = ['lot_code', 'ingredient__name']

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'ingredient':
            kwargs['queryset'] = Ingredient.objects.filter(restaurant_id=request.user.restaurant_id)
        elif db_field.name == 'received_by':
            kwargs['queryset'] = CustomUser.objects.filter(restaurant_id=request.user.restaurant_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)
