from io import StringIO
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, Restaurant
from orders.models import Order

ADMIN_PASSWORD = 'admin-deployment-test-passphrase'
DEMO_PASSWORD = 'demo-deployment-test-passphrase'


class DeploymentBootstrapTests(TestCase):
    @patch.dict(
        'os.environ',
        {'DJANGO_SUPERUSER_PASSWORD': ADMIN_PASSWORD, 'DJANGO_SUPERUSER_USERNAME': 'ａｄｍｉｎ'},
        clear=True,
    )
    def test_admin_can_log_in_and_redeploy_preserves_credentials(self):
        call_command('provision_deployment_admin', stdout=StringIO())
        admin = CustomUser.objects.get(username='admin')
        self.assertIsNotNone(admin.restaurant_id)
        self.assertFalse(admin.is_superuser)
        password_hash, restaurant_id = admin.password, admin.restaurant_id

        login_page = self.client.get(reverse('admin:index'), follow=True)
        self.assertEqual(login_page.status_code, 200)
        response = self.client.post(
            reverse('admin:login'),
            {'username': 'admin', 'password': ADMIN_PASSWORD, 'next': reverse('admin:index')},
            follow=True,
        )
        self.assertEqual(response.redirect_chain, [(reverse('admin:index'), 302)])
        self.assertEqual(response.status_code, 200)

        call_command('provision_deployment_admin', stdout=StringIO())
        admin.refresh_from_db()
        self.assertEqual((admin.password, admin.restaurant_id), (password_hash, restaurant_id))
        self.assertEqual(Restaurant.objects.count(), 1)

        other_restaurant = Restaurant.objects.create(name='Other restaurant')
        foreign_order = Order.objects.create(restaurant=other_restaurant)
        self.assertEqual(
            self.client.get(reverse('admin:inventory_ingredient_changelist')).status_code, 200
        )
        for url in (
            reverse('admin:orders_order_change', args=[foreign_order.pk]),
            reverse('admin:orders_orderitem_changelist'),
            reverse('admin:auth_group_changelist'),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 403)

    @patch.dict('os.environ', {'DJANGO_SUPERUSER_PASSWORD': ADMIN_PASSWORD}, clear=True)
    def test_unscoped_superuser_gets_configured_restaurant_without_password_reset(self):
        admin = CustomUser.objects.create_superuser(username='admin', password=ADMIN_PASSWORD)
        password_hash = admin.password
        restaurant = Restaurant.objects.create(name='Existing restaurant')

        with patch.dict('os.environ', {'DJANGO_SUPERUSER_RESTAURANT_ID': str(restaurant.pk)}):
            call_command('provision_deployment_admin', stdout=StringIO())

        admin.refresh_from_db()
        self.assertEqual(admin.restaurant, restaurant)
        self.assertEqual(admin.password, password_hash)
        self.assertFalse(admin.is_superuser)
        self.assertTrue(admin.has_perm('inventory.change_ingredient'))
        self.assertFalse(admin.has_perm('orders.view_order'))
        self.assertEqual(Restaurant.objects.count(), 1)

    @patch.dict('os.environ', {'DJANGO_SUPERUSER_PASSWORD': ADMIN_PASSWORD}, clear=True)
    def test_admin_bootstrap_refuses_existing_regular_user(self):
        restaurant = Restaurant.objects.create(name='Existing restaurant')
        existing = CustomUser.objects.create_user(username='admin', restaurant=restaurant)

        with self.assertRaisesMessage(CommandError, 'belongs to a non-admin account'):
            call_command('provision_deployment_admin', stdout=StringIO())

        existing.refresh_from_db()
        self.assertFalse(existing.is_superuser)
        self.assertEqual(existing.restaurant, restaurant)
        self.assertEqual(Restaurant.objects.count(), 1)

    @patch.dict(
        'os.environ',
        {'DEMO_OWNER_PASSWORD': DEMO_PASSWORD, 'DEMO_OWNER_USERNAME': 'ｄｅｍｏ-ｏｗｎｅｒ'},
        clear=True,
    )
    def test_demo_seed_leaves_existing_owner_and_demo_changes_intact(self):
        restaurant = Restaurant.objects.create(name='Existing restaurant')
        existing = CustomUser.objects.create_user(username='owner', restaurant=restaurant)
        original_password_hash = existing.password
        output = StringIO()

        call_command('seed_pos_demo', stdout=output)
        demo = CustomUser.objects.get(username='demo-owner')
        self.assertNotEqual(demo.restaurant, restaurant)
        self.assertNotIn(DEMO_PASSWORD, output.getvalue())
        ingredient = demo.restaurant.ingredients.get(name='ไข่ไก่สด')
        ingredient.stock_quantity = 4
        ingredient.save(update_fields=['stock_quantity'])

        call_command('seed_pos_demo', stdout=output)

        ingredient.refresh_from_db()
        existing.refresh_from_db()
        self.assertEqual(ingredient.stock_quantity, 4)
        self.assertEqual(existing.restaurant, restaurant)
        self.assertEqual(existing.password, original_password_hash)
        self.assertEqual(Restaurant.objects.count(), 2)

    @patch.dict('os.environ', {'DEMO_OWNER_PASSWORD': DEMO_PASSWORD}, clear=True)
    def test_demo_seed_refuses_username_collision(self):
        restaurant = Restaurant.objects.create(name='Existing restaurant')
        existing = CustomUser.objects.create_user(username='demo-owner', restaurant=restaurant)
        password_hash = existing.password

        with self.assertRaisesMessage(CommandError, 'belongs to a different account'):
            call_command('seed_pos_demo', stdout=StringIO())

        existing.refresh_from_db()
        self.assertEqual((existing.password, existing.restaurant), (password_hash, restaurant))
        self.assertEqual(Restaurant.objects.count(), 1)
