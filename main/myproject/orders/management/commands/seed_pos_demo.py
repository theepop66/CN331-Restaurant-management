"""[US-04] Management command to seed demo data for Mini-POS live demonstration."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.management.base import BaseCommand

from accounts.models import CustomUser, Restaurant
from inventory.models import Ingredient, StockIn
from menus.models import MenuItem, RecipeItem


class Command(BaseCommand):
    help = 'Seeds sample restaurant, ingredients, and menus for POS demo'

    def handle(self, *args, **options):
        # 1. Create Restaurant
        restaurant, created = Restaurant.objects.get_or_create(
            name='ร้านหมูแองกี้เบิ้ด 🐷',
        )

        # 2. Create Owner User
        user, u_created = CustomUser.objects.get_or_create(
            username='owner',
            defaults={
                'email': 'owner@angrybird.com',
                'role': CustomUser.Role.OWNER,
                'restaurant': restaurant,
            },
        )
        user.set_password('password123')
        user.role = CustomUser.Role.OWNER
        user.restaurant = restaurant
        user.save()

        self.stdout.write(self.style.SUCCESS(f'Created/Updated Owner user: owner (password: password123)'))

        # 3. Create Ingredients
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

        # Ensure quantities are set for demo
        rice.stock_quantity = Decimal('10.000'); rice.save()
        egg.stock_quantity = Decimal('30.000'); egg.save()
        pork.stock_quantity = Decimal('5.000'); pork.save()
        basil.stock_quantity = Decimal('1.000'); basil.save()
        beef_out.stock_quantity = Decimal('0.000'); beef_out.save()

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

        # 4. Create Menus
        # Menu 1: กะเพราหมูกรอบ
        menu1, _ = MenuItem.objects.get_or_create(
            restaurant=restaurant,
            name='กะเพราหมูกรอบจานด่วน',
            defaults={'price': Decimal('65.00'), 'is_active': True},
        )
        menu1.is_active = True
        menu1.price = Decimal('65.00')
        menu1.save()
        menu1.recipe_items.all().delete()
        RecipeItem.objects.create(menu_item=menu1, ingredient=pork, quantity_used=Decimal('0.100'))
        RecipeItem.objects.create(menu_item=menu1, ingredient=basil, quantity_used=Decimal('0.020'))
        RecipeItem.objects.create(menu_item=menu1, ingredient=rice, quantity_used=Decimal('0.150'))

        # Menu 2: ข้าวผัดไข่
        menu2, _ = MenuItem.objects.get_or_create(
            restaurant=restaurant,
            name='ข้าวผัดไข่โบราณ',
            defaults={'price': Decimal('45.00'), 'is_active': True},
        )
        menu2.is_active = True
        menu2.price = Decimal('45.00')
        menu2.save()
        menu2.recipe_items.all().delete()
        RecipeItem.objects.create(menu_item=menu2, ingredient=rice, quantity_used=Decimal('0.200'))
        RecipeItem.objects.create(menu_item=menu2, ingredient=egg, quantity_used=Decimal('2.000'))

        # Menu 3: ไข่ดาวฟองโต
        menu3, _ = MenuItem.objects.get_or_create(
            restaurant=restaurant,
            name='ไข่ดาวกรอบ',
            defaults={'price': Decimal('12.00'), 'is_active': True},
        )
        menu3.is_active = True
        menu3.price = Decimal('12.00')
        menu3.save()
        menu3.recipe_items.all().delete()
        RecipeItem.objects.create(menu_item=menu3, ingredient=egg, quantity_used=Decimal('1.000'))

        # Menu 4: สเต๊กเนื้อวากิว (Out of Stock!)
        menu4, _ = MenuItem.objects.get_or_create(
            restaurant=restaurant,
            name='สเต๊กเนื้อริบอายวากิว',
            defaults={'price': Decimal('380.00'), 'is_active': True},
        )
        menu4.is_active = True
        menu4.price = Decimal('380.00')
        menu4.save()
        menu4.recipe_items.all().delete()
        RecipeItem.objects.create(menu_item=menu4, ingredient=beef_out, quantity_used=Decimal('0.200'))

        self.stdout.write(self.style.SUCCESS('Successfully seeded demo restaurant, ingredients, and menus!'))
