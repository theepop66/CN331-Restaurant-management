"""[US-04][Review Focus 2] Concurrency test for simultaneous checkout on the last serving."""

from decimal import Decimal
from queue import Queue
from threading import Thread

from django.db import OperationalError
from django.test import TransactionTestCase

from accounts.models import CustomUser, Restaurant
from inventory.models import Ingredient
from menus.models import MenuItem, RecipeItem
from orders.models import Order
from orders.services import CartLine, StockInsufficient, checkout_order


class ConcurrencyTestCase(TransactionTestCase):
    def setUp(self):
        self.restaurant = Restaurant.objects.create(name='ร้านทดสอบ Concurrency')
        self.owner = CustomUser.objects.create_user(
            'concurrency_owner',
            restaurant=self.restaurant,
            role=CustomUser.Role.OWNER,
        )

        # Ingredient: exactly 0.200 kg (only enough for 1 serving)
        self.beef = Ingredient.objects.create(
            restaurant=self.restaurant,
            name='เนื้อวัวพรีเมียม',
            unit='kg',
            price=Decimal('500.00'),
            stock_quantity=Decimal('0.200'),
        )

        # Menu: Steak (uses 0.200 kg beef)
        self.steak = MenuItem.objects.create(
            restaurant=self.restaurant,
            name='สเต๊กเนื้อริบอาย',
            price=Decimal('350.00'),
            is_active=True,
        )
        RecipeItem.objects.create(
            menu_item=self.steak,
            ingredient=self.beef,
            quantity_used=Decimal('0.200'),
        )

    def test_sequential_checkout_last_serving_rejects_second(self):
        """Sequential checkout: first order depletes stock, second raises StockInsufficient."""
        order1 = checkout_order(
            restaurant=self.restaurant,
            user=self.owner,
            lines=[CartLine(menu_item_id=self.steak.pk, quantity=1)],
        )
        self.assertIsNotNone(order1)
        self.assertEqual(Order.objects.filter(restaurant=self.restaurant).count(), 1)

        with self.assertRaises(StockInsufficient):
            checkout_order(
                restaurant=self.restaurant,
                user=self.owner,
                lines=[CartLine(menu_item_id=self.steak.pk, quantity=1)],
            )

        self.beef.refresh_from_db()
        self.assertEqual(self.beef.stock_quantity, Decimal('0.000'))

    def test_concurrent_checkout_competing_for_last_serving(self):
        """[Review Focus 2] Two orders attempt to checkout the last serving simultaneously.

        Exactly ONE order must succeed, and the other must be rejected (either via
        StockInsufficient or SQLite's database lock serialization).
        The stock must never become negative.
        """
        results = Queue()

        def try_order(thread_id):
            try:
                order = checkout_order(
                    restaurant=self.restaurant,
                    user=self.owner,
                    lines=[CartLine(menu_item_id=self.steak.pk, quantity=1)],
                )
                results.put(('SUCCESS', order.pk))
            except StockInsufficient:
                results.put(('INSUFFICIENT', None))
            except OperationalError as exc:
                if 'locked' in str(exc).lower():
                    results.put(('LOCKED', str(exc)))
                else:
                    results.put(('ERROR', str(exc)))
            except Exception as exc:
                results.put(('ERROR', str(exc)))

        t1 = Thread(target=try_order, args=(1,))
        t2 = Thread(target=try_order, args=(2,))

        t1.start()
        t2.start()

        t1.join()
        t2.join()

        outcomes = [results.get_nowait(), results.get_nowait()]
        successes = [out for out in outcomes if out[0] == 'SUCCESS']
        failures = [out for out in outcomes if out[0] in ('INSUFFICIENT', 'LOCKED')]

        self.assertEqual(len(successes), 1, f'Expected 1 success, got: {outcomes}')
        self.assertEqual(len(failures), 1, f'Expected 1 failure, got: {outcomes}')

        # Stock must be exactly 0, never negative
        self.beef.refresh_from_db()
        self.assertEqual(self.beef.stock_quantity, Decimal('0.000'))
        self.assertEqual(Order.objects.filter(restaurant=self.restaurant).count(), 1)
