from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .admin_scope import RestaurantOwnerAdmin
from .models import CustomUser, Restaurant


@admin.register(Restaurant)
class RestaurantAdmin(RestaurantOwnerAdmin):
    list_display = ['name', 'address', 'created_at']
    search_fields = ['name']

    def has_add_permission(self, request):
        # Restaurant creation belongs to registration; an owner administers
        # only the restaurant already assigned to their account.
        return False


@admin.register(CustomUser)
class CustomUserAdmin(RestaurantOwnerAdmin, UserAdmin):
    fieldsets = UserAdmin.fieldsets + (('ข้อมูลร้าน (Tenant)', {'fields': ('restaurant', 'role')}),)
    list_display = ['username', 'email', 'restaurant', 'role', 'is_staff']
    list_filter = ['role']
