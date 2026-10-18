"""[US-03] Enabled inventory admin is owner-only and restaurant-scoped."""

from django.contrib.auth.models import Permission
from django.urls import reverse

from accounts.models import Restaurant

from .base import MenuTestCase


class InventoryAdminAccessTests(MenuTestCase):
    def test_ordinary_owner_admin_cannot_see_foreign_users_or_tenant_filters(self):
        self.owner.is_staff = True
        self.owner.save()
        self.owner.user_permissions.add(
            *Permission.objects.filter(
                codename__in=[
                    'view_ingredient',
                    'add_stockin',
                    'view_restaurant',
                    'change_restaurant',
                    'view_customuser',
                ]
            )
        )
        self.other_owner.username = 'foreign_sensitive_username'
        self.other_owner.save()
        for route in (
            'admin:inventory_ingredient_changelist',
            'admin:accounts_restaurant_changelist',
        ):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, self.other_shop.name)
        for route in ('admin:inventory_stockin_add', 'admin:accounts_customuser_changelist'):
            response = self.client.get(reverse(route))
            self.assertEqual(response.status_code, 200)
            self.assertNotContains(response, self.other_owner.username)
        self.client.post(
            reverse('admin:accounts_restaurant_change', args=[self.other_shop.pk]),
            {
                'name': 'Stolen tenant',
                'address': '',
                '_save': 'Save',
            },
        )
        self.assertEqual(Restaurant.objects.get(pk=self.other_shop.pk).name, self.other_shop.name)

    def test_staff_with_account_admin_permissions_cannot_cross_owner_boundary(self):
        self.staff.is_staff = True
        self.staff.save()
        self.staff.user_permissions.add(
            *Permission.objects.filter(
                codename__in=[
                    'view_restaurant',
                    'change_restaurant',
                    'view_customuser',
                ]
            )
        )
        self.client.force_login(self.staff)
        for route in (
            'admin:index',
            'admin:accounts_restaurant_changelist',
            'admin:accounts_customuser_changelist',
        ):
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)
        response = self.client.post(
            reverse('admin:accounts_restaurant_change', args=[self.other_shop.pk]),
            {
                'name': 'Stolen tenant',
                'address': '',
                '_save': 'Save',
            },
        )
        self.assertEqual(response.status_code, 403)
        self.other_shop.refresh_from_db()
        self.assertEqual(self.other_shop.name, 'ร้าน B')

    def test_owner_admin_list_and_ingredient_choices_remain_scoped(self):
        self.owner.is_staff = True
        self.owner.is_superuser = True
        self.owner.save()
        response = self.client.get(reverse('admin:inventory_ingredient_changelist'))
        self.assertContains(response, self.rice.name)
        self.assertNotContains(response, self.foreign.name)
        response = self.client.get(reverse('admin:inventory_stockin_add'))
        self.assertNotContains(response, self.foreign.name)
        self.assertContains(response, self.rice.name)

    def test_staff_role_cannot_bypass_owner_rule_using_admin_privileges(self):
        self.staff.is_staff = True
        self.staff.is_superuser = True
        self.staff.save()
        self.client.force_login(self.staff)
        for route in ('admin:inventory_ingredient_changelist', 'admin:inventory_ingredient_add'):
            self.assertEqual(self.client.get(reverse(route)).status_code, 403)
