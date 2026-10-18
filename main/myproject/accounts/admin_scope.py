"""[US-03] Restaurant scoping shared by enabled business administrators."""

from django.contrib import admin
from django.core.exceptions import PermissionDenied

from .models import CustomUser, Restaurant


class RestaurantOwnerAdmin(admin.ModelAdmin):
    def _is_owner(self, request):
        return request.user.role == CustomUser.Role.OWNER and request.user.restaurant_id is not None

    def has_module_permission(self, request):
        return self._is_owner(request) and super().has_module_permission(request)

    def has_view_permission(self, request, obj=None):
        return self._is_owner(request) and super().has_view_permission(request, obj)

    def has_add_permission(self, request):
        return self._is_owner(request) and super().has_add_permission(request)

    def has_change_permission(self, request, obj=None):
        return self._is_owner(request) and super().has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        return self._is_owner(request) and super().has_delete_permission(request, obj)

    def get_queryset(self, request):
        queryset = super().get_queryset(request)
        if not self._is_owner(request):
            return queryset.none()
        if self.model is Restaurant:
            return queryset.filter(pk=request.user.restaurant_id)
        return queryset.filter(restaurant_id=request.user.restaurant_id)

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == 'restaurant':
            kwargs['queryset'] = Restaurant.objects.filter(pk=request.user.restaurant_id)
        return super().formfield_for_foreignkey(db_field, request, **kwargs)

    def save_model(self, request, obj, form, change):
        if not self._is_owner(request):
            raise PermissionDenied
        if isinstance(obj, Restaurant):
            if obj.pk != request.user.restaurant_id:
                raise PermissionDenied
        else:
            obj.restaurant = request.user.restaurant
        super().save_model(request, obj, form, change)
