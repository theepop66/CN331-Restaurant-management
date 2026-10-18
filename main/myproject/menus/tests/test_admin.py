"""[US-03] Enabled inventory admin is owner-only and restaurant-scoped."""

from django.urls import reverse

from .base import MenuTestCase


class InventoryAdminAccessTests(MenuTestCase):
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
