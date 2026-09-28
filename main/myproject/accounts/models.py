from django.contrib.auth.models import AbstractUser
from django.db import models


class Restaurant(models.Model):
    """
    [UC-01] Tenant model.

    Every CustomUser belongs to exactly one Restaurant, and every
    business record created by the other apps (Ingredient, MenuItem,
    Order, ...) is expected to carry its own FK back to Restaurant so
    that data between tenants never mixes, e.g.:

        Ingredient.objects.filter(restaurant=request.user.restaurant)
    """

    name = models.CharField(max_length=150)
    address = models.CharField(max_length=255, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['name']

    def __str__(self):
        return self.name


class CustomUser(AbstractUser):
    """
    [UC-01] Custom user model used across the whole project.

    AUTH_USER_MODEL points here (see settings.py) instead of Django's
    default auth.User, so we can attach a tenant FK and a coarse role
    from day one. Every other app's views should filter querysets by
    `request.user.restaurant` to keep tenants isolated.
    """

    class Role(models.TextChoices):
        OWNER = 'owner', 'เจ้าของร้าน'
        STAFF = 'staff', 'พนักงาน'

    restaurant = models.ForeignKey(
        Restaurant,
        on_delete=models.CASCADE,
        related_name='staff_members',
        null=True,
        blank=True,
        help_text='ร้านที่ผู้ใช้คนนี้สังกัดอยู่ (tenant)',
    )
    role = models.CharField(
        max_length=10,
        choices=Role.choices,
        default=Role.OWNER,
    )

    def __str__(self):
        return self.username
