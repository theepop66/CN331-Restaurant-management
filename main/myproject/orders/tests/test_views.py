"""[US-04] Unit tests for orders views (POS screen, checkout, authorization)."""

import json
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, Restaurant
from inventory.models import Ingredient
from menus.models import MenuItem, RecipeItem
from orders.models import Order


class OrdersViewsTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.restaurant = Restaurant.objects.create(name='ร้านวิว')
        cls.owner = CustomUser.objects.create_user(
            'view_owner',
            restaurant=cls.restaurant,
            role=CustomUser.Role.OWNER,
        )
        cls.staff = CustomUser.objects.create_user(
            'view_staff',
            restaurant=cls.restaurant,
            role=CustomUser.Role.STAFF,
        )

        cls.chicken = Ingredient.objects.create(
            restaurant=cls.restaurant,
            name='ไก่สด',
            unit='kg',
            price=Decimal('80.00'),
            stock_quantity=Decimal('2.000'),
        )
        cls.curry = MenuItem.objects.create(
            restaurant=cls.restaurant,
            name='แกงเขียวหวานไก่',
            price=Decimal('70.00'),
            is_active=True,
        )
        RecipeItem.objects.create(
            menu_item=cls.curry,
            ingredient=cls.chicken,
            quantity_used=Decimal('0.250'),
        )

    def test_unauthenticated_user_redirected_to_login(self):
        """Guests must be redirected to login page."""
        response = self.client.get(reverse('orders:pos'))
        self.assertEqual(response.status_code, 302)
        self.assertIn('/login/', response.url)

    def test_non_owner_forbidden_403(self):
        """Staff without owner role must receive 403 Forbidden under current owner_required rule."""
        self.client.force_login(self.staff)
        response = self.client.get(reverse('orders:pos'))
        self.assertEqual(response.status_code, 403)

    def test_pos_view_renders_cards_for_owner(self):
        """Owner can access POS and view the menu cards."""
        self.client.force_login(self.owner)
        response = self.client.get(reverse('orders:pos'))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/pos.html')
        self.assertContains(response, 'แกงเขียวหวานไก่')
        self.assertContains(response, '70.00')

    def test_checkout_get_returns_405(self):
        """GET request to checkout endpoint is disallowed."""
        self.client.force_login(self.owner)
        response = self.client.get(reverse('orders:checkout'))
        self.assertEqual(response.status_code, 405)

    def test_checkout_post_valid_redirects_to_success(self):
        """Valid cart checkout creates order and redirects to success screen."""
        self.client.force_login(self.owner)
        cart_data = json.dumps([{'menu_id': self.curry.pk, 'quantity': 2}])

        response = self.client.post(
            reverse('orders:checkout'),
            {'cart_data': cart_data},
        )

        order = Order.objects.filter(restaurant=self.restaurant).first()
        self.assertIsNotNone(order)
        self.assertEqual(order.total_amount, Decimal('140.00'))
        self.assertRedirects(response, reverse('orders:success', kwargs={'pk': order.pk}))

    def test_checkout_post_insufficient_stock_shows_flash_and_redirects(self):
        """Insufficient stock should catch exception, add error flash and redirect."""
        self.client.force_login(self.owner)
        # 2 kg chicken / 0.25 = 8 servings max. Request 20 servings.
        cart_data = json.dumps([{'menu_id': self.curry.pk, 'quantity': 20}])

        response = self.client.post(
            reverse('orders:checkout'),
            {'cart_data': cart_data},
            follow=True,
        )

        self.assertRedirects(response, reverse('orders:pos'))
        self.assertContains(response, 'ไม่สามารถขายได้')
        self.assertEqual(Order.objects.count(), 0)

    def test_checkout_post_invalid_json_redirects_with_error(self):
        """Corrupted JSON payload in cart_data should redirect safely with error."""
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('orders:checkout'),
            {'cart_data': 'not-a-valid-json'},
            follow=True,
        )
        self.assertRedirects(response, reverse('orders:pos'))
        self.assertContains(response, 'รูปแบบข้อมูลตะกร้าสินค้าไม่ถูกต้อง')

    def test_order_success_view_renders_details(self):
        """Owner can view the receipt page."""
        self.client.force_login(self.owner)
        order = Order.objects.create(
            restaurant=self.restaurant,
            created_by=self.owner,
            total_amount=Decimal('70.00'),
        )
        response = self.client.get(reverse('orders:success', kwargs={'pk': order.pk}))
        self.assertEqual(response.status_code, 200)
        self.assertTemplateUsed(response, 'orders/order_success.html')
        self.assertContains(response, f'#{order.pk}')

    def test_checkout_fallback_form_fields(self):
        """Test checkout using direct menu_id and quantity form parameters."""
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('orders:checkout'),
            {'menu_id': str(self.curry.pk), 'quantity': '1'},
        )
        order = Order.objects.filter(restaurant=self.restaurant).first()
        self.assertIsNotNone(order)
        self.assertRedirects(response, reverse('orders:success', kwargs={'pk': order.pk}))

    def test_checkout_empty_lines_redirects(self):
        """Test submitting checkout with no items."""
        self.client.force_login(self.owner)
        response = self.client.post(reverse('orders:checkout'), {})
        self.assertRedirects(response, reverse('orders:pos'))

    def test_checkout_generic_validation_error(self):
        """Test submitting menu item with quantity <= 0 raising ValidationError."""
        self.client.force_login(self.owner)
        response = self.client.post(
            reverse('orders:checkout'),
            {'menu_id': str(self.curry.pk), 'quantity': '-1'},
            follow=True,
        )
        self.assertRedirects(response, reverse('orders:pos'))
        self.assertContains(response, 'เกิดข้อผิดพลาด')
