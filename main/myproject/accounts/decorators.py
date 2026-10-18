"""Shared owner access rules for [US-03][UC-03] and business screens."""

from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.shortcuts import redirect

from .models import CustomUser


def owner_required(view):
    @wraps(view)
    @login_required
    def wrapper(request, *args, **kwargs):
        if request.user.role != CustomUser.Role.OWNER:
            raise PermissionDenied('เฉพาะเจ้าของร้านเท่านั้นที่ใช้งานระบบนี้ได้')
        return view(request, *args, **kwargs)

    return wrapper


def restaurant_owner_required(view):
    @wraps(view)
    @owner_required
    def wrapper(request, *args, **kwargs):
        restaurant = request.user.restaurant
        if restaurant is None:
            messages.error(request, 'บัญชีนี้ยังไม่ได้ผูกกับร้าน')
            return redirect('accounts:home')
        return view(request, restaurant, *args, **kwargs)

    return wrapper
