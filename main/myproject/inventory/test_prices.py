"""[US-03][UC-03] Positive ingredient costs through inventory requests."""

from decimal import Decimal

from django.db import IntegrityError, transaction
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, Restaurant

from .models import Ingredient


class IngredientPriceTests(TestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(name='ร้าน A')
        self.owner = CustomUser.objects.create_user(
            'owner',
            restaurant=self.restaurant,
        )
        self.client.force_login(self.owner)

    def test_nonpositive_and_missing_prices_do_not_create_stock(self):
        for price in ('0', '-1', ''):
            with self.subTest(price=price):
                response = self.client.post(
                    reverse('inventory:create'),
                    {
                        'name': 'Rice',
                        'unit': 'kg',
                        'price': price,
                        'stock_quantity': '0',
                    },
                )
                self.assertEqual(response.status_code, 200)
                self.assertFalse(Ingredient.objects.exists())

    def test_positive_price_and_zero_stock_are_valid(self):
        self.client.post(
            reverse('inventory:create'),
            {
                'name': 'Rice',
                'unit': 'kg',
                'price': '40',
                'stock_quantity': '0',
            },
        )
        ingredient = Ingredient.objects.get()
        self.assertEqual(ingredient.price, Decimal('40'))
        self.assertEqual(ingredient.stock_quantity, 0)

    def test_database_rejects_zero_price_from_bulk_writes(self):
        with self.assertRaises(IntegrityError), transaction.atomic():
            Ingredient.objects.bulk_create(
                [
                    Ingredient(
                        restaurant=self.restaurant,
                        name='Rice',
                        unit='kg',
                        price=0,
                    )
                ]
            )
