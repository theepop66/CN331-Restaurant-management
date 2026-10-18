"""[US-03][UC-03] Owner-only access through business requests."""

from django.test import TestCase
from django.urls import reverse

from .models import CustomUser, Restaurant


class OwnerAccessTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.restaurant = Restaurant.objects.create(name='ร้านทดสอบ')
        cls.owner = CustomUser.objects.create_user(
            'owner',
            restaurant=cls.restaurant,
        )
        cls.staff = CustomUser.objects.create_user(
            'staff',
            restaurant=cls.restaurant,
            role=CustomUser.Role.STAFF,
        )
        cls.no_shop = CustomUser.objects.create_user('no-shop')

    def test_anonymous_business_access_requires_login(self):
        for route in ('accounts:home', 'inventory:list'):
            with self.subTest(route=route):
                response = self.client.get(reverse(route))
                self.assertEqual(response.status_code, 302)
                self.assertIn(reverse('accounts:login'), response.url)

    def test_staff_cannot_view_or_mutate_business_data(self):
        self.client.force_login(self.staff)
        for route in ('accounts:home', 'inventory:list', 'inventory:create'):
            for method in ('get', 'post'):
                with self.subTest(route=route, method=method):
                    response = getattr(self.client, method)(reverse(route))
                    self.assertEqual(response.status_code, 403)

    def test_owner_can_view_business_screens(self):
        self.client.force_login(self.owner)
        for route in ('accounts:home', 'inventory:list'):
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)

    def test_no_restaurant_redirect_does_not_loop(self):
        self.client.force_login(self.no_shop)
        response = self.client.get(reverse('inventory:list'), follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.redirect_chain), 1)

    def test_public_authentication_screens_remain_available(self):
        for route in ('accounts:login', 'accounts:register'):
            self.assertEqual(self.client.get(reverse(route)).status_code, 200)
