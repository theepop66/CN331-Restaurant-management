"""[US-03][UC-03] Availability, ingredient protection and missing-row repair."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models.signals import post_delete
from django.urls import reverse

from inventory.models import Ingredient
from menus.models import MenuItem, RecipeItem
from menus.services import read_menu

from .base import MenuTestCase


class MenuLifecycleTests(MenuTestCase):
    def test_explicit_activation_deactivation_and_saved_recipe_contract(self):
        self.assertEqual(self.activate().status_code, 200)
        self.save_recipe()
        self.assertFalse(read_menu(self.menu).is_sellable)
        self.assertEqual(self.activate().status_code, 302)
        self.assertTrue(read_menu(self.menu, require_sellable=True).is_sellable)
        self.save_recipe(rows=[(self.rice, '.300'), (self.egg, '1')])
        self.assertTrue(read_menu(self.menu).is_sellable)
        data = self.recipe_payload(rows=[(self.rice, '0'), (self.egg, '1')])
        self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data)
        self.assertTrue(read_menu(self.menu).is_sellable)
        self.assertEqual(self.activate(active=False).status_code, 302)
        self.assertFalse(read_menu(self.menu).is_sellable)
        self.assertEqual(len(read_menu(self.menu).requirements), 2)

    def test_availability_is_post_only_and_version_checked(self):
        self.save_recipe()
        url = reverse('menus:availability', args=[self.menu.pk])
        self.assertEqual(self.client.get(url).status_code, 405)
        self.assertEqual(self.client.post(url, {'is_active': 'on'}).status_code, 200)
        self.assertEqual(
            self.client.post(url, {'expected_revision': 0, 'is_active': 'on'}).status_code, 409
        )
        self.assertFalse(read_menu(self.menu).is_sellable)

    def test_high_cost_does_not_prevent_activation(self):
        self.save_recipe(rows=[(self.rice, '2')])
        self.assertEqual(self.activate().status_code, 302)
        self.assertTrue(read_menu(self.menu).is_sellable)

    def test_deletion_deactivates_all_affected_menus_retaining_labels(self):
        self.save_recipe()
        self.activate()
        sibling = MenuItem.objects.create(restaurant=self.shop, name='Second dish', price=40)
        self.save_recipe(menu=sibling, rows=[(self.rice, '.100')])
        self.activate(menu=sibling)
        self.rice.name = 'Renamed Rice'
        self.rice.save()
        old_revision = read_menu(self.menu).revision
        self.client.post(reverse('inventory:delete', args=[self.rice.pk]))
        for menu in (self.menu, sibling):
            snapshot = read_menu(menu)
            self.assertFalse(snapshot.is_sellable)
            self.assertIsNone(snapshot.cost_per_serving)
            missing = menu.recipe_items.get(ingredient=None)
            self.assertEqual(missing.ingredient_name_snapshot, 'Renamed Rice')
            self.assertEqual(missing.ingredient_unit_snapshot, 'kg')
        self.assertEqual(read_menu(self.menu).revision, old_revision + 1)
        self.other_menu.refresh_from_db()
        self.assertEqual(self.other_menu.revision, 0)
        response = self.client.get(reverse('menus:recipe', args=[self.menu.pk]))
        self.assertContains(response, 'วัตถุดิบถูกลบ')
        self.assertContains(response, 'Renamed Rice')
        self.assertEqual(self.activate().status_code, 200)

    def test_missing_row_replacement_then_explicit_reactivation(self):
        self.save_recipe()
        self.activate()
        self.rice.delete()
        replacement = Ingredient.objects.create(
            restaurant=self.shop, name='New rice', unit='kg', price=30
        )
        self.save_recipe(rows=[(replacement, '.200'), (self.egg, '1')])
        self.assertFalse(read_menu(self.menu).is_sellable)
        self.activate()
        self.assertTrue(read_menu(self.menu).is_sellable)

    def test_missing_row_can_be_explicitly_removed_but_not_last_row(self):
        self.save_recipe()
        self.rice.delete()
        data = self.recipe_payload(rows=[(None, '.200'), (self.egg, '1')])
        data['items-0-DELETE'] = 'on'
        self.assertEqual(
            self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data).status_code, 302
        )
        self.assertEqual(read_menu(self.menu).cost_per_serving, Decimal('5'))
        data = self.recipe_payload(rows=[(self.egg, '1')])
        data['items-0-DELETE'] = 'on'
        self.assertEqual(
            self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data).status_code, 200
        )

    def test_deletion_invalidates_open_editor(self):
        self.save_recipe()
        data = self.recipe_payload()
        data['items-0-DELETE'] = 'on'
        self.rice.delete()
        response = self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data)
        self.assertEqual(response.status_code, 409)
        self.assertTrue(self.menu.recipe_items.filter(ingredient=None).exists())

    def test_queryset_deletion_preserves_missing_rows(self):
        self.save_recipe()
        self.activate()
        Ingredient.objects.filter(pk__in=[self.rice.pk, self.egg.pk]).delete()
        self.assertEqual(self.menu.recipe_items.filter(ingredient=None).count(), 2)
        self.assertFalse(read_menu(self.menu).is_sellable)

    def test_deletion_failure_rolls_back_deactivation_and_snapshots(self):
        self.save_recipe()
        self.activate()
        version = read_menu(self.menu).revision

        def fail_after_delete(**kwargs):
            raise RuntimeError('failed')

        post_delete.connect(fail_after_delete, sender=Ingredient, weak=False)
        try:
            with self.assertRaises(RuntimeError), transaction.atomic():
                self.rice.delete()
        finally:
            post_delete.disconnect(fail_after_delete, sender=Ingredient)
        self.assertTrue(Ingredient.objects.filter(pk=self.rice.pk).exists())
        self.assertTrue(read_menu(self.menu).is_sellable)
        self.assertEqual(read_menu(self.menu).revision, version)

    def test_units_protected_in_form_model_and_queryset_edits(self):
        self.save_recipe()
        response = self.client.post(
            reverse('inventory:update', args=[self.rice.pk]),
            {
                'name': 'Rice',
                'barcode': self.rice.barcode,
                'unit': 'g',
                'price': 40,
                'stock_quantity': 10,
                'expected_revision': self.rice.revision,
            },
        )
        self.assertContains(response, 'เปลี่ยนหน่วยไม่ได้')
        self.rice.unit = 'g'
        with self.assertRaises(ValidationError):
            self.rice.save()
        with self.assertRaises(ValidationError):
            Ingredient.objects.filter(pk=self.rice.pk).update(unit='g')
        self.rice.refresh_from_db()
        self.assertEqual(self.rice.unit, 'kg')
        self.assertEqual(read_menu(self.menu).cost_per_serving, Decimal('13'))

    def test_read_contract_rejects_invalid_servings_and_unsellable_menus(self):
        for servings in (0, -1, 'NaN', 'Infinity', 'bad'):
            with self.subTest(servings=servings), self.assertRaises(ValidationError):
                read_menu(self.menu, servings)
        with self.assertRaises(ValidationError):
            read_menu(self.menu, require_sellable=True)
        with self.assertRaises(ValidationError):
            _ = read_menu(self.menu).requirements

    def test_direct_model_recipe_cannot_link_another_restaurants_ingredient(self):
        with self.assertRaises(ValidationError):
            RecipeItem.objects.create(menu_item=self.menu, ingredient=self.foreign, quantity_used=1)
