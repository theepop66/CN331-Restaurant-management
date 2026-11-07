"""[US-04] Management command to seed demo data for Mini-POS live demonstration."""

import os
from datetime import date, timedelta
from decimal import Decimal

from django.contrib.auth.hashers import check_password
from django.contrib.auth.password_validation import validate_password
from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from accounts.models import CustomUser, Restaurant
from inventory.models import Ingredient, StockIn
from menus.models import MenuItem, RecipeItem

DEMO_RESTAURANT_NAME = 'ร้านหมูแองกี้เบิ้ด 🐷'


class Command(BaseCommand):
    help = 'Seeds sample restaurant, ingredients, and menus for POS demo'

    @transaction.atomic
    def handle(self, *args, **options):
        username = os.environ.get('DEMO_OWNER_USERNAME') or 'demo-owner'
        password = os.environ.get('DEMO_OWNER_PASSWORD')
        if not password:
            raise CommandError('Set DEMO_OWNER_PASSWORD before seeding demo data.')

        user = CustomUser.objects.select_related('restaurant').filter(username=username).first()
        if user is not None:
            if (
                user.is_active
                and not user.is_staff
                and not user.is_superuser
                and user.role == CustomUser.Role.OWNER
                and user.restaurant is not None
                and user.restaurant.name == DEMO_RESTAURANT_NAME
                and check_password(password, user.password)
            ):
                self.stdout.write('Demo data is already seeded.')
                return
            raise CommandError('The configured demo username belongs to a different account.')

        try:
            validate_password(password, user=CustomUser(username=username))
        except ValidationError as exc:
            raise CommandError('Invalid DEMO_OWNER_PASSWORD: ' + ' '.join(exc.messages)) from exc

        restaurant = Restaurant.objects.create(name=DEMO_RESTAURANT_NAME)
        CustomUser.objects.create_user(
            username=username, password=password, role=CustomUser.Role.OWNER, restaurant=restaurant
        )
        self._seed_restaurant(restaurant)
        self.stdout.write(self.style.SUCCESS('Demo restaurant, ingredients, and menus are ready.'))

    def _seed_restaurant(self, restaurant):
        today = date.today()

        rice, _ = Ingredient.objects.get_or_create(
            restaurant=restaurant,
            name='ข้าวหอมมะลิ',
            defaults={'unit': 'kg', 'price': Decimal('35.00'), 'stock_quantity': Decimal('10.000')},
        )
        egg, _ = Ingredient.objects.get_or_create(
            restaurant=restaurant,
            name='ไข่ไก่สด',
            defaults={'unit': 'egg', 'price': Decimal('5.00'), 'stock_quantity': Decimal('30.000')},
        )
        pork, _ = Ingredient.objects.get_or_create(
            restaurant=restaurant,
            name='หมูกรอบสูตรเด็ด',
            defaults={'unit': 'kg', 'price': Decimal('220.00'), 'stock_quantity': Decimal('5.000')},
        )
        basil, _ = Ingredient.objects.get_or_create(
            restaurant=restaurant,
            name='ใบกะเพราสด',
            defaults={'unit': 'kg', 'price': Decimal('60.00'), 'stock_quantity': Decimal('1.000')},
        )
        beef_out, _ = Ingredient.objects.get_or_create(
            restaurant=restaurant,
            name='เนื้อริบอายวากิว (หมดสต็อก)',
            defaults={'unit': 'kg', 'price': Decimal('650.00'), 'stock_quantity': Decimal('0.000')},
        )

        # Create StockIn lots for FEFO demo
        StockIn.objects.get_or_create(
            restaurant=restaurant,
            ingredient=egg,
            lot_code='LOT-EGG-EXP3D',
            defaults={
                'quantity': Decimal('10.000'),
                'remaining_quantity': Decimal('10.000'),
                'expiry_date': today + timedelta(days=3),
            },
        )
        StockIn.objects.get_or_create(
            restaurant=restaurant,
            ingredient=egg,
            lot_code='LOT-EGG-EXP14D',
            defaults={
                'quantity': Decimal('20.000'),
                'remaining_quantity': Decimal('20.000'),
                'expiry_date': today + timedelta(days=14),
            },
        )

        # Menu 1: กะเพราหมูกรอบ
        menu1, _ = MenuItem.objects.get_or_create(
            restaurant=restaurant,
            name='กะเพราหมูกรอบจานด่วน',
            defaults={'price': Decimal('65.00'), 'is_active': True},
        )
        RecipeItem.objects.create(menu_item=menu1, ingredient=pork, quantity_used=Decimal('0.100'))
        RecipeItem.objects.create(menu_item=menu1, ingredient=basil, quantity_used=Decimal('0.020'))
        RecipeItem.objects.create(menu_item=menu1, ingredient=rice, quantity_used=Decimal('0.150'))

        # Menu 2: ข้าวผัดไข่
        menu2, _ = MenuItem.objects.get_or_create(
            restaurant=restaurant,
            name='ข้าวผัดไข่โบราณ',
            defaults={'price': Decimal('45.00'), 'is_active': True},
        )
        RecipeItem.objects.create(menu_item=menu2, ingredient=rice, quantity_used=Decimal('0.200'))
        RecipeItem.objects.create(menu_item=menu2, ingredient=egg, quantity_used=Decimal('2.000'))

        # Menu 3: ไข่ดาวฟองโต
        menu3, _ = MenuItem.objects.get_or_create(
            restaurant=restaurant,
            name='ไข่ดาวกรอบ',
            defaults={'price': Decimal('12.00'), 'is_active': True},
        )
        RecipeItem.objects.create(menu_item=menu3, ingredient=egg, quantity_used=Decimal('1.000'))

        # Menu 4: สเต๊กเนื้อวากิว (Out of Stock!)
        menu4, _ = MenuItem.objects.get_or_create(
            restaurant=restaurant,
            name='สเต๊กเนื้อริบอายวากิว',
            defaults={'price': Decimal('380.00'), 'is_active': True},
        )
        RecipeItem.objects.create(
            menu_item=menu4, ingredient=beef_out, quantity_used=Decimal('0.200')
        )
