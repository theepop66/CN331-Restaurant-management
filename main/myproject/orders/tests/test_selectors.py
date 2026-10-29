"""[US-04] Unit tests for orders selectors layer (PosCard availability, order detail)."""

from decimal import Decimal

from django.http import Http404
from django.test import TestCase

from accounts.models import CustomUser, Restaurant
from inventory.models import Ingredient
from menus.models import MenuItem, RecipeItem
from orders.models import Order
from orders.selectors import get_order_detail, get_pos_cards


class OrdersSelectorsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.restaurant = Restaurant.objects.create(name='ร้านคัดสรร A')
        cls.other_restaurant = Restaurant.objects.create(name='ร้านคัดสรร B')

        cls.owner = CustomUser.objects.create_user(
            'selector_owner',
            restaurant=cls.restaurant,
            role=CustomUser.Role.OWNER,
        )

        # Ingredients
        cls.pork = Ingredient.objects.create(
            restaurant=cls.restaurant,
            name='หมูกรอบ',
            unit='kg',
            price=Decimal('200.00'),
            stock_quantity=Decimal('1.000'),  # 1 kg
        )
        cls.basil = Ingredient.objects.create(
            restaurant=cls.restaurant,
            name='ใบกะเพรา',
            unit='kg',
            price=Decimal('50.00'),
            stock_quantity=Decimal('0.050'),  # 50g
        )

        # Menu 1: Basil Crispy Pork (Pork 0.1 kg -> 10 servings max; Basil 0.02 kg -> 2.5 = 2 servings max!)
        # The bottleneck is basil (only 2 servings!)
        cls.basil_pork = MenuItem.objects.create(
            restaurant=cls.restaurant,
            name='กะเพราหมูกรอบ',
            price=Decimal('65.00'),
            is_active=True,
        )
        RecipeItem.objects.create(
            menu_item=cls.basil_pork,
            ingredient=cls.pork,
            quantity_used=Decimal('0.100'),
        )
        RecipeItem.objects.create(
            menu_item=cls.basil_pork,
            ingredient=cls.basil,
            quantity_used=Decimal('0.020'),
        )

        # Menu 2: Out of stock menu (requires egg which has 0 stock)
        cls.egg = Ingredient.objects.create(
            restaurant=cls.restaurant,
            name='ไข่เป็ด',
            unit='egg',
            price=Decimal('6.00'),
            stock_quantity=Decimal('0.000'),
        )
        cls.duck_egg_menu = MenuItem.objects.create(
            restaurant=cls.restaurant,
            name='ไข่ดาวเป็ด',
            price=Decimal('15.00'),
            is_active=True,
        )
        RecipeItem.objects.create(
            menu_item=cls.duck_egg_menu,
            ingredient=cls.egg,
            quantity_used=Decimal('1.000'),
        )

        # Other restaurant menu
        cls.foreign_menu = MenuItem.objects.create(
            restaurant=cls.other_restaurant,
            name='เมนูร้าน B',
            price=Decimal('50.00'),
            is_active=True,
        )

    def test_pos_cards_calculates_max_servings_bottleneck(self):
        """Max servings must be the bottleneck among required ingredients."""
        cards = get_pos_cards(restaurant=self.restaurant)
        card_map = {c.menu_id: c for c in cards}

        basil_card = card_map.get(self.basil_pork.pk)
        self.assertIsNotNone(basil_card)
        self.assertTrue(basil_card.is_orderable)
        self.assertEqual(basil_card.reason, 'ok')
        # 1.0 kg pork / 0.1 = 10; 0.05 kg basil / 0.02 = 2 -> Bottleneck = 2
        self.assertEqual(basil_card.max_servings, 2)

    def test_pos_cards_mark_out_of_stock_when_one_serving_not_available(self):
        """When an ingredient is 0, is_orderable must be False and reason 'out_of_stock'."""
        cards = get_pos_cards(restaurant=self.restaurant)
        card_map = {c.menu_id: c for c in cards}

        egg_card = card_map.get(self.duck_egg_menu.pk)
        self.assertIsNotNone(egg_card)
        self.assertFalse(egg_card.is_orderable)
        self.assertEqual(egg_card.reason, 'out_of_stock')
        self.assertEqual(egg_card.max_servings, 0)

    def test_pos_cards_tenant_isolation(self):
        """Only current restaurant's active menus should appear."""
        cards = get_pos_cards(restaurant=self.restaurant)
        menu_ids = [c.menu_id for c in cards]
        self.assertNotIn(self.foreign_menu.pk, menu_ids)

    def test_get_order_detail_tenant_isolation(self):
        """Querying an order belonging to another restaurant must raise Http404."""
        order_b = Order.objects.create(
            restaurant=self.other_restaurant,
            total_amount=Decimal('100.00'),
        )
        with self.assertRaises(Http404):
            get_order_detail(restaurant=self.restaurant, order_id=order_b.pk)

    def test_pos_cards_menu_without_recipe_is_marked_incomplete(self):
        """A menu without any recipe items should be marked incomplete."""
        no_recipe_menu = MenuItem.objects.create(
            restaurant=self.restaurant,
            name='เมนูไม่มีสูตร',
            price=Decimal('20.00'),
            is_active=True,
        )
        cards = get_pos_cards(restaurant=self.restaurant)
        card = next((c for c in cards if c.menu_id == no_recipe_menu.pk), None)
        self.assertIsNotNone(card)
        self.assertFalse(card.is_orderable)
        self.assertEqual(card.reason, 'incomplete')
        self.assertEqual(card.max_servings, 0)
