"""[US-03] The optional administration site is owner-only too."""

from functools import wraps

from django.contrib.admin import AdminSite
from django.core.exceptions import PermissionDenied

from .models import CustomUser


class OwnerAdminSite(AdminSite):
    def has_permission(self, request):
        return (
            super().has_permission(request)
            and request.user.role == CustomUser.Role.OWNER
            and request.user.restaurant_id is not None
        )

    def admin_view(self, view, cacheable=False):
        protected = super().admin_view(view, cacheable)

        @wraps(view)
        def owner_view(request, *args, **kwargs):
            if request.user.is_authenticated and (
                request.user.role != CustomUser.Role.OWNER or request.user.restaurant_id is None
            ):
                raise PermissionDenied('เฉพาะเจ้าของร้านที่มีข้อมูลร้านเท่านั้น')
            return protected(request, *args, **kwargs)

        return owner_view
