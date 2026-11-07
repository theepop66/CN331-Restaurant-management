import os

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import CustomUser, Restaurant


class Command(BaseCommand):
    help = 'Provision an owner-scoped deployment administrator'

    @transaction.atomic
    def handle(self, *args, **options):
        password = os.environ.get('DJANGO_SUPERUSER_PASSWORD')
        if not password:
            raise CommandError('Set DJANGO_SUPERUSER_PASSWORD before provisioning an admin.')

        username = os.environ.get('DJANGO_SUPERUSER_USERNAME') or 'admin'
        email = os.environ.get('DJANGO_SUPERUSER_EMAIL') or 'admin@example.com'
        restaurant_id = os.environ.get('DJANGO_SUPERUSER_RESTAURANT_ID')
        restaurant = None
        if restaurant_id:
            try:
                restaurant = Restaurant.objects.get(pk=int(restaurant_id))
            except (ValueError, Restaurant.DoesNotExist) as exc:
                raise CommandError(
                    'DJANGO_SUPERUSER_RESTAURANT_ID must identify a restaurant.'
                ) from exc

        admin = CustomUser.objects.select_for_update().filter(username=username).first()
        if admin is not None:
            if not (admin.is_active and admin.is_staff and admin.is_superuser):
                raise CommandError('The configured username belongs to a non-admin account.')
            if admin.role != CustomUser.Role.OWNER:
                raise CommandError('The configured admin must have the restaurant owner role.')
            if admin.restaurant_id is not None:
                if restaurant is not None and admin.restaurant_id != restaurant.pk:
                    raise CommandError('The existing admin belongs to a different restaurant.')
                self.stdout.write('Deployment admin is already provisioned.')
                return

        if restaurant is None:
            restaurant = Restaurant.objects.create(name='Deployment Administration')

        if admin is None:
            CustomUser.objects.create_superuser(
                username=username, email=email, password=password, restaurant=restaurant
            )
        else:
            admin.restaurant = restaurant
            admin.save(update_fields=['restaurant'])

        self.stdout.write(self.style.SUCCESS('Deployment admin is ready.'))
