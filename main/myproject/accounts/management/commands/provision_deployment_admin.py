import os

from django.contrib.auth.models import Permission
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from accounts.models import CustomUser, Restaurant

RESTAURANT_PERMISSIONS = ('view_restaurant', 'change_restaurant')
INVENTORY_PERMISSIONS = (
    'view_ingredient',
    'add_ingredient',
    'change_ingredient',
    'delete_ingredient',
    'view_stockin',
    'add_stockin',
    'change_stockin',
    'delete_stockin',
)


class Command(BaseCommand):
    help = 'Provision an owner-scoped deployment administrator'

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        if not password:
            raise CommandError('Set DJANGO_SUPERUSER_PASSWORD before provisioning an admin.')

        username = CustomUser.normalize_username(
            os.environ.get('DJANGO_SUPERUSER_USERNAME') or 'admin'
        )
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL') or 'admin@example.com'
        try:
            CustomUser._meta.get_field('username').clean(username, None)
        except ValidationError as exc:
            raise CommandError(
                'Invalid DJANGO_SUPERUSER_USERNAME: ' + ' '.join(exc.messages)
            ) from exc

        restaurant_id = os.environ.get('DJANGO_SUPERUSER_RESTAURANT_ID')
        restaurant = None
        if restaurant_id:
            try:
                restaurant = Restaurant.objects.get(pk=int(restaurant_id))
            except (ValueError, Restaurant.DoesNotExist) as exc:
                raise CommandError(
                    'DJANGO_SUPERUSER_RESTAURANT_ID must identify a restaurant.'
                ) from exc

        permission_ids = set(
            Permission.objects.filter(
                Q(content_type__app_label='accounts', codename__in=RESTAURANT_PERMISSIONS)
                | Q(content_type__app_label='inventory', codename__in=INVENTORY_PERMISSIONS)
            ).values_list('pk', flat=True)
        )
        admin = CustomUser.objects.select_for_update().filter(username=username).first()
        if admin is not None:
            if not (admin.is_active and admin.is_staff):
                raise CommandError('The configured username belongs to a non-admin account.')
            if admin.role != CustomUser.Role.OWNER:
                raise CommandError('The configured admin must have the restaurant owner role.')
            if admin.restaurant_id is not None:
                granted = set(admin.user_permissions.values_list('pk', flat=True))
                if not admin.is_superuser and not granted.issuperset(permission_ids):
                    raise CommandError('The configured account lacks deployment admin permissions.')
                if restaurant is not None and admin.restaurant_id != restaurant.pk:
                    raise CommandError('The existing admin belongs to a different restaurant.')
                self.stdout.write('Deployment admin is already provisioned.')
                return
            if not admin.is_superuser or admin.groups.exists() or admin.user_permissions.exists():
                raise CommandError(
                    'Only an unscoped superuser with default permissions can be repaired.'
                )

        if restaurant is None:
            restaurant = Restaurant.objects.create(name='Deployment Administration')

        if admin is None:
            admin = CustomUser.objects.create_user(
                username=username,
                email=email,
                password=password,
                restaurant=restaurant,
                is_staff=True,
            )
        else:
            # The legacy bootstrap created a superuser that could not enter the owner-only admin.
            # Grant scoped access without activating its global Django admin privileges.
            admin.restaurant = restaurant
            admin.is_superuser = False
            admin.save(update_fields=['restaurant', 'is_superuser'])

        admin.user_permissions.add(*permission_ids)
        self.stdout.write(self.style.SUCCESS('Deployment admin is ready.'))
