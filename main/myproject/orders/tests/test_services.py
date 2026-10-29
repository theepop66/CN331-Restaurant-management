"""[US-04] Unit tests for orders services layer (checkout, FEFO stock deduction)."""

from datetime import date, timedelta
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import CustomUser, Restaurant
from inventory.models import Ingredient, StockIn
from menus.models import MenuItem, RecipeItem
from orders.models import Order, StockDeduction
from orders.services import CartLine, StockInsufficient, checkout_order


class OrdersServicesTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.restaurant = Restaurant.objects.create(name='ร้านทดสอบ A')
        cls.other_restaurant = Restaurant.objects.create(name='ร้านทดสอบ B')

        cls.owner = CustomUser.objects.create_user(
            'owner_test',
            restaurant=cls.restaurant,
            role=CustomUser.Role.OWNER,
        )

        # Ingredients for Restaurant A
        cls.rice = Ingredient.objects.create(
            restaurant=cls.restaurant,
            name='ข้าวหอมมะลิ',
            unit='kg',
            price=Decimal('40.00'),
            stock_quantity=Decimal('10.000'),
        )
        cls.egg = Ingredient.objects.create(
            restaurant=cls.restaurant,
            name='ไข่ไก่',
            unit='egg',
            price=Decimal('5.00'),
            stock_quantity=Decimal('20.000'),
        )
        cls.pork = Ingredient.objects.create(
            restaurant=cls.restaurant,
            name='หมูสับ',
            unit='kg',
            price=Decimal('150.00'),
            stock_quantity=Decimal('5.000'),
        )

        # Menu 1: Fried Rice (requires Rice 0.2 kg, Egg 1 egg)
        cls.fried_rice = MenuItem.objects.create(
            restaurant=cls.restaurant,
            name='ข้าวผัดโบราณ',
            price=Decimal('55.00'),
            is_active=True,
        )
        RecipeItem.objects.create(
            menu_item=cls.fried_rice,
            ingredient=cls.rice,
            quantity_used=Decimal('0.200'),
        )
        RecipeItem.objects.create(
            menu_item=cls.fried_rice,
            ingredient=cls.egg,
            quantity_used=Decimal('1.000'),
        )

        # Menu 2: Omelet (requires Egg 2 eggs, Pork 0.1 kg)
        cls.omelet = MenuItem.objects.create(
            restaurant=cls.restaurant,
            name='ไข่เจียวหมูสับ',
            price=Decimal('45.00'),
            is_active=True,
        )
        RecipeItem.objects.create(
            menu_item=cls.omelet,
            ingredient=cls.egg,
            quantity_used=Decimal('2.000'),
        )
        RecipeItem.objects.create(
            menu_item=cls.omelet,
            ingredient=cls.pork,
            quantity_used=Decimal('0.100'),
        )

        # Inactive Menu
        cls.inactive_menu = MenuItem.objects.create(
            restaurant=cls.restaurant,
            name='เมนูปิดปรับปรุง',
            price=Decimal('99.00'),
            is_active=False,
        )
        RecipeItem.objects.create(
            menu_item=cls.inactive_menu,
            ingredient=cls.rice,
            quantity_used=Decimal('0.100'),
        )

        # Menu from other restaurant
        cls.other_menu = MenuItem.objects.create(
            restaurant=cls.other_restaurant,
            name='เมนูร้านอื่น',
            price=Decimal('100.00'),
            is_active=True,
        )

    def test_checkout_deducts_ingredient_stock_and_lots_earliest_expiry_first(self):
        """[Review Focus 1] Test FEFO deduction: earliest expiring lot deducted first."""
        today = date.today()
        # Create 2 lots for Egg: lot 1 expires in 3 days (qty 5), lot 2 expires in 10 days (qty 15)
        lot_early = StockIn.objects.create(
            restaurant=self.restaurant,
            ingredient=self.egg,
            lot_code='LOT-EXP-EARLY',
            quantity=Decimal('5.000'),
            remaining_quantity=Decimal('5.000'),
            expiry_date=today + timedelta(days=3),
        )
        lot_later = StockIn.objects.create(
            restaurant=self.restaurant,
            ingredient=self.egg,
            lot_code='LOT-EXP-LATER',
            quantity=Decimal('15.000'),
            remaining_quantity=Decimal('15.000'),
            expiry_date=today + timedelta(days=10),
        )

        # Order 7 fried rice -> needs 7 eggs
        order = checkout_order(
            restaurant=self.restaurant,
            user=self.owner,
            lines=[CartLine(menu_item_id=self.fried_rice.pk, quantity=7)],
        )

        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.assertEqual(order.total_amount, Decimal('385.00'))  # 55 * 7

        # Refresh egg stock
        self.egg.refresh_from_db()
        self.assertEqual(self.egg.stock_quantity, Decimal('13.000'))  # 20 - 7

        # Check lot deductions: lot_early should be fully depleted (5), lot_later should have 13 left (deducted 2)
        lot_early.refresh_from_db()
        lot_later.refresh_from_db()
        self.assertEqual(lot_early.remaining_quantity, Decimal('0.000'))
        self.assertEqual(lot_later.remaining_quantity, Decimal('13.000'))

        # Check StockDeduction records
        deductions = StockDeduction.objects.filter(ingredient=self.egg)
        self.assertEqual(deductions.count(), 2)
        self.assertEqual(deductions.get(lot=lot_early).quantity, Decimal('5.000'))
        self.assertEqual(deductions.get(lot=lot_later).quantity, Decimal('2.000'))

    def test_checkout_creates_order_items_with_price_snapshot_and_total(self):
        """Order item must snapshot name and price; later menu changes should not affect old orders."""
        order = checkout_order(
            restaurant=self.restaurant,
            user=self.owner,
            lines=[CartLine(menu_item_id=self.fried_rice.pk, quantity=2)],
        )

        item = order.items.first()
        self.assertEqual(item.name_snapshot, 'ข้าวผัดโบราณ')
        self.assertEqual(item.unit_price, Decimal('55.00'))
        self.assertEqual(item.quantity, 2)
        self.assertEqual(item.line_total, Decimal('110.00'))

        # Change menu price afterwards
        self.fried_rice.price = Decimal('99.00')
        self.fried_rice.save()

        # Order and item prices remain intact
        order.refresh_from_db()
        item.refresh_from_db()
        self.assertEqual(order.total_amount, Decimal('110.00'))
        self.assertEqual(item.unit_price, Decimal('55.00'))

    def test_checkout_rejects_when_any_ingredient_short_and_changes_nothing(self):
        """If any ingredient is insufficient, rollback everything and do not create order."""
        # Pork stock is 5.0 kg; each omelet needs 0.1 kg. Request 60 servings -> needs 6.0 kg (short by 1.0 kg)
        init_rice_stock = self.rice.stock_quantity
        init_egg_stock = self.egg.stock_quantity
        init_pork_stock = self.pork.stock_quantity

        with self.assertRaises(StockInsufficient):
            checkout_order(
                restaurant=self.restaurant,
                user=self.owner,
                lines=[CartLine(menu_item_id=self.omelet.pk, quantity=60)],
            )

        # Nothing created, stocks unchanged
        self.assertEqual(Order.objects.count(), 0)
        self.rice.refresh_from_db()
        self.egg.refresh_from_db()
        self.pork.refresh_from_db()
        self.assertEqual(self.rice.stock_quantity, init_rice_stock)
        self.assertEqual(self.egg.stock_quantity, init_egg_stock)
        self.assertEqual(self.pork.stock_quantity, init_pork_stock)

    def test_cart_lines_sharing_ingredient_are_aggregated(self):
        """[Review Focus 1] If multiple items share an ingredient, sum requirements before checking stock."""
        # Set Egg stock to 5 eggs
        self.egg.stock_quantity = Decimal('5.000')
        self.egg.save()

        # Fried Rice needs 1 egg. Omelet needs 2 eggs.
        # Order 2 Fried Rice (needs 2) + 2 Omelet (needs 4) -> Total needed = 6 eggs > 5 available!
        with self.assertRaises(StockInsufficient):
            checkout_order(
                restaurant=self.restaurant,
                user=self.owner,
                lines=[
                    CartLine(menu_item_id=self.fried_rice.pk, quantity=2),
                    CartLine(menu_item_id=self.omelet.pk, quantity=2),
                ],
            )

        # Now increase stock to 6 eggs -> Should succeed
        self.egg.stock_quantity = Decimal('6.000')
        self.egg.save()

        order = checkout_order(
            restaurant=self.restaurant,
            user=self.owner,
            lines=[
                CartLine(menu_item_id=self.fried_rice.pk, quantity=2),
                CartLine(menu_item_id=self.omelet.pk, quantity=2),
            ],
        )
        self.assertEqual(order.status, Order.Status.COMPLETED)
        self.egg.refresh_from_db()
        self.assertEqual(self.egg.stock_quantity, Decimal('0.000'))

    def test_checkout_rechecks_sellable_after_menu_deactivated(self):
        """[Review Focus 3] If menu is deactivated, checkout must reject it."""
        with self.assertRaises(ValidationError):
            checkout_order(
                restaurant=self.restaurant,
                user=self.owner,
                lines=[CartLine(menu_item_id=self.inactive_menu.pk, quantity=1)],
            )

    def test_checkout_rejects_other_restaurant_menu_and_invalid_quantity(self):
        """[Review Focus 4] Reject invalid quantities (<=0) or menus belonging to another tenant."""
        # Quantity <= 0
        with self.assertRaises(ValidationError):
            checkout_order(
                restaurant=self.restaurant,
                user=self.owner,
                lines=[CartLine(menu_item_id=self.fried_rice.pk, quantity=0)],
            )

        with self.assertRaises(ValidationError):
            checkout_order(
                restaurant=self.restaurant,
                user=self.owner,
                lines=[CartLine(menu_item_id=self.fried_rice.pk, quantity=-2)],
            )

        # Other restaurant's menu
        with self.assertRaises(ValidationError):
            checkout_order(
                restaurant=self.restaurant,
                user=self.owner,
                lines=[CartLine(menu_item_id=self.other_menu.pk, quantity=1)],
            )

    def test_empty_cart_raises_validation_error(self):
        with self.assertRaises(ValidationError):
            checkout_order(
                restaurant=self.restaurant,
                user=self.owner,
                lines=[],
            )

    def test_model_str_representations(self):
        """Test __str__ methods of Order, OrderItem, and StockDeduction."""
        order = checkout_order(
            restaurant=self.restaurant,
            user=self.owner,
            lines=[CartLine(menu_item_id=self.fried_rice.pk, quantity=1)],
        )
        self.assertIn(f'Order #{order.pk}', str(order))
        item = order.items.first()
        self.assertIn('ข้าวผัดโบราณ x 1', str(item))
        ded = item.stock_deductions.first()
        self.assertIn('ข้าวหอมมะลิ', str(ded))
