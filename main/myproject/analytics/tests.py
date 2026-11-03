"""Core analytics coverage: costing, tenant isolation, and offline AI fallback."""

import os
from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import Restaurant
from inventory.models import Ingredient
from menus.models import MenuItem, RecipeItem
from orders.models import Order

from .services import build_dashboard_data, get_ai_insights


class AnalyticsServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.restaurant = Restaurant.objects.create(name='Analytics A')
        cls.other_restaurant = Restaurant.objects.create(name='Analytics B')
        cls.ingredient = Ingredient.objects.create(
            restaurant=cls.restaurant,
            name='Rice A',
            unit='kg',
            price=Decimal('40.00'),
            stock_quantity=Decimal('3.000'),
            par_level=Decimal('5.000'),
        )
        cls.other_ingredient = Ingredient.objects.create(
            restaurant=cls.other_restaurant,
            name='Secret Rice B',
            unit='kg',
            price=Decimal('99.00'),
            stock_quantity=Decimal('10.000'),
            par_level=Decimal('2.000'),
        )
        cls.menu = MenuItem.objects.create(
            restaurant=cls.restaurant, name='Rice Bowl', price=Decimal('100.00')
        )
        RecipeItem.objects.create(
            menu_item=cls.menu,
            ingredient=cls.ingredient,
            quantity_used=Decimal('0.250'),
            ingredient_name_snapshot=cls.ingredient.name,
            ingredient_unit_snapshot=cls.ingredient.unit,
        )
        cls.other_menu = MenuItem.objects.create(
            restaurant=cls.other_restaurant, name='Secret Bowl', price=Decimal('500.00')
        )

    def test_cost_and_margin_are_computed_from_recipe_and_current_ingredient_price(self):
        data = build_dashboard_data(self.restaurant)

        self.assertEqual(len(data['menu_costs']), 1)
        self.assertEqual(data['menu_costs'][0]['cost'], Decimal('10.00000'))
        self.assertEqual(data['menu_costs'][0]['gross_profit'], Decimal('90.00000'))
        self.assertEqual(data['menu_costs'][0]['margin'], Decimal('90.00000'))

    def test_dashboard_data_is_scoped_to_requested_restaurant(self):
        data = build_dashboard_data(self.restaurant)

        self.assertEqual(data['stock_value'], Decimal('120.00000'))
        self.assertEqual([row['menu'].name for row in data['menu_costs']], ['Rice Bowl'])
        self.assertEqual([item.name for item in data['low_stock']], ['Rice A'])
        self.assertNotIn('Secret Rice B', [item.name for item in data['low_stock']])
        self.assertEqual(data['restock_suggestions'][0]['quantity'], Decimal('7.000'))

    def test_sales_trend_compares_current_and_previous_30_day_periods(self):
        now = timezone.now()
        current = Order.objects.create(restaurant=self.restaurant, total_amount=Decimal('200.00'))
        previous = Order.objects.create(restaurant=self.restaurant, total_amount=Decimal('100.00'))
        other_tenant = Order.objects.create(
            restaurant=self.other_restaurant, total_amount=Decimal('999.00')
        )
        Order.objects.filter(pk=current.pk).update(created_at=now - timedelta(days=5))
        Order.objects.filter(pk=previous.pk).update(created_at=now - timedelta(days=40))
        Order.objects.filter(pk=other_tenant.pk).update(created_at=now - timedelta(days=5))

        data = build_dashboard_data(self.restaurant)

        self.assertEqual(data['sales_30d'], Decimal('200.00'))
        self.assertEqual(data['sales_previous_30d'], Decimal('100.00'))
        self.assertEqual(data['sales_change_percent'], Decimal('100'))

    @patch.dict(os.environ, {}, clear=True)
    def test_ai_insights_fall_back_without_api_key(self):
        data = build_dashboard_data(self.restaurant)

        content, provider = get_ai_insights(self.restaurant, data)

        self.assertEqual(provider, 'rules')
        self.assertIn('Rice A', content)
        self.assertIn('สั่งประมาณ', content)
