from django.contrib import admin
from django.contrib.auth.admin import UserAdmin

from .models import CustomUser, Restaurant


@admin.register(Restaurant)
class RestaurantAdmin(admin.ModelAdmin):
    list_display = ['name', 'address', 'created_at']
    search_fields = ['name']


@admin.register(CustomUser)
class CustomUserAdmin(UserAdmin):
    fieldsets = UserAdmin.fieldsets + (
        ('ข้อมูลร้าน (Tenant)', {'fields': ('restaurant', 'role')}),
    )
    list_display = ['username', 'email', 'restaurant', 'role', 'is_staff']
    list_filter = ['role', 'restaurant']
