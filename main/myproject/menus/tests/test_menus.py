"""[US-03][UC-03] Menu owner workflow and optimistic edit conflicts."""

from django.test import Client
from django.urls import reverse

from menus.models import MenuItem

from .base import MenuTestCase


class DraftMenuTests(MenuTestCase):
    def test_create_draft_redirects_to_builder_without_activating(self):
        response = self.client.post(
            reverse('menus:create'),
            {
                'name': '  Chicken   Rice ',
                'price': '60',
                'restaurant': self.other_shop.pk,
                'is_active': 'on',
            },
        )
        menu = MenuItem.objects.get(name='Chicken Rice')
        self.assertEqual(menu.restaurant, self.shop)
        self.assertFalse(menu.is_active)
        self.assertFalse(menu.recipe_items.exists())
        self.assertRedirects(response, reverse('menus:recipe', args=[menu.pk]))

    def test_duplicate_normalized_name_including_casefold_is_rejected(self):
        for name in (' fried  RICE ', 'FRIED RICE'):
            response = self.client.post(
                reverse('menus:create'),
                {
                    'name': name,
                    'price': 40,
                },
            )
            self.assertEqual(response.status_code, 200)
            self.assertEqual(MenuItem.objects.filter(restaurant=self.shop).count(), 1)

    def test_names_are_unique_only_within_restaurant(self):
        self.client.force_login(self.other_owner)
        response = self.client.post(
            reverse('menus:create'),
            {
                'name': 'Fried Rice',
                'price': 50,
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_blank_name_and_nonpositive_price_are_rejected(self):
        for name, price in [(' ', '50'), ('New dish', '0'), ('New dish', '-1')]:
            response = self.client.post(
                reverse('menus:create'),
                {
                    'name': name,
                    'price': price,
                },
            )
            self.assertEqual(response.status_code, 200)
        self.assertEqual(MenuItem.objects.filter(restaurant=self.shop).count(), 1)

    def test_two_tab_edit_preserves_current_record_and_submitted_values(self):
        url = reverse('menus:update', args=[self.menu.pk])
        data = {'name': 'First edit', 'price': 55, 'expected_revision': 0}
        self.assertEqual(self.client.post(url, data).status_code, 302)
        data.update(name='Stale edit', price=60)
        response = self.client.post(url, data)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'Stale edit', status_code=409)
        self.assertContains(response, 'First edit', status_code=409)
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.name, 'First edit')
        self.assertEqual(self.menu.revision, 1)

    def test_missing_revision_does_not_allow_edit(self):
        response = self.client.post(
            reverse('menus:update', args=[self.menu.pk]),
            {
                'name': 'Unsafe edit',
                'price': 55,
            },
        )
        self.assertEqual(response.status_code, 200)
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.name, 'Fried Rice')

    def test_other_restaurant_menu_ids_return_404_for_get_and_post(self):
        self.assertNotContains(self.client.get(reverse('menus:list')), 'Secret dish')
        for route in ('update', 'recipe', 'availability'):
            for method in ('get', 'post'):
                response = getattr(self.client, method)(
                    reverse(f'menus:{route}', args=[self.other_menu.pk]),
                )
                self.assertEqual(response.status_code, 404)

    def test_anonymous_staff_and_csrf_checks(self):
        self.client.logout()
        self.assertEqual(self.client.get(reverse('menus:list')).status_code, 302)
        self.client.force_login(self.staff)
        self.assertEqual(self.client.get(reverse('menus:list')).status_code, 403)
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.owner)
        self.assertEqual(client.post(reverse('menus:create'), {}).status_code, 403)

    def test_menu_name_is_escaped(self):
        self.menu.name = '<script>alert(1)</script>'
        self.menu.save()
        response = self.client.get(reverse('menus:list'))
        self.assertContains(response, '&lt;script&gt;')
        self.assertNotContains(response, '<script>alert(1)</script>')
