"""[US-03][UC-03] Saved BOM behavior through owner requests."""

from decimal import Decimal
from unittest.mock import patch

from django.db import IntegrityError
from django.urls import reverse

from inventory.models import Ingredient, StockIn
from menus.models import MenuItem, RecipeItem
from menus.services import read_menu

from .base import MenuTestCase


class RecipeBuilderTests(MenuTestCase):
    def test_save_cost_scale_and_no_stock_side_effects(self):
        StockIn.objects.create(
            restaurant=self.shop,
            ingredient=self.rice,
            quantity=10,
        )
        before = list(Ingredient.objects.values_list('pk', 'stock_quantity', 'revision'))
        self.save_recipe()
        self.assert_example_recipe()
        self.assertFalse(self.menu.is_active)
        snapshot = read_menu(self.menu, servings=3)
        self.assertEqual(snapshot.cost_per_serving, Decimal('13'))
        self.assertEqual(snapshot.requirements, {self.rice.pk: Decimal('.600'), self.egg.pk: 3})
        self.assertEqual(
            before, list(Ingredient.objects.values_list('pk', 'stock_quantity', 'revision'))
        )
        self.assertEqual(StockIn.objects.get().remaining_quantity, 10)
        response = self.client.get(reverse('menus:recipe', args=[self.menu.pk]))
        self.assertContains(response, '฿13.00')
        self.assertNotContains(response, 'Secret ingredient')

    def test_add_edit_and_delete_rows(self):
        self.save_recipe(rows=[(self.rice, '.200')])
        self.save_recipe(rows=[(self.rice, '.300'), (self.egg, '2')])
        data = self.recipe_payload(rows=[(self.rice, '.300'), (self.egg, '2')])
        data['items-0-DELETE'] = 'on'
        response = self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data)
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            list(self.menu.recipe_items.values_list('ingredient_id', 'quantity_used')),
            [(self.egg.pk, Decimal('2'))],
        )

    def test_invalid_rows_leave_original_recipe_and_revision_unchanged(self):
        self.save_recipe()
        revision = self.menu.revision
        for quantity in ('0', '-1', '.0001', 'garbage', ''):
            with self.subTest(quantity=quantity):
                data = self.recipe_payload(rows=[(self.rice, quantity), (self.egg, '1')])
                response = self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data)
                self.assertEqual(response.status_code, 200)
                self.assert_example_recipe()
                self.menu.refresh_from_db()
                self.assertEqual(self.menu.revision, revision)

    def test_duplicate_ingredients_and_last_row_removal_rejected(self):
        self.save_recipe()
        data = self.recipe_payload(rows=[(self.rice, '.2'), (self.rice, '1')])
        self.assertEqual(
            self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data).status_code, 200
        )
        data = self.recipe_payload()
        data.update({'items-0-DELETE': 'on', 'items-1-DELETE': 'on'})
        self.assertEqual(
            self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data).status_code, 200
        )
        self.assert_example_recipe()

    def test_forged_ingredient_and_row_ids_cannot_change_recipes(self):
        self.save_recipe()
        data = self.recipe_payload(rows=[(self.foreign, '.2'), (self.egg, '1')])
        self.assertEqual(
            self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data).status_code, 200
        )
        sibling = MenuItem.objects.create(restaurant=self.shop, name='Sibling', price=40)
        row = RecipeItem.objects.create(menu_item=sibling, ingredient=self.egg, quantity_used=1)
        data = self.recipe_payload()
        data['items-0-id'] = str(row.pk)
        self.assertEqual(
            self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data).status_code, 200
        )
        self.assert_example_recipe()
        self.assertEqual(sibling.recipe_items.get().pk, row.pk)

    def test_initial_row_count_cannot_be_forged_to_drop_rows(self):
        self.save_recipe()
        data = self.recipe_payload(rows=[(self.rice, '.1')])
        data['items-INITIAL_FORMS'] = '0'
        self.assertEqual(
            self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data).status_code, 200
        )
        self.assert_example_recipe()

    def test_stale_recipe_save_preserves_submitted_and_current_values(self):
        self.save_recipe()
        data = self.recipe_payload(rows=[(self.rice, '.500'), (self.egg, '1')])
        self.save_recipe(rows=[(self.rice, '.300'), (self.egg, '1')])
        response = self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data)
        self.assertEqual(response.status_code, 409)
        self.assertContains(response, 'value=".500"', status_code=409)
        self.assertEqual(
            self.menu.recipe_items.get(ingredient=self.rice).quantity_used, Decimal('.300')
        )

    def test_missing_revision_and_tampered_unit_state_are_rejected(self):
        for field in ('expected_revision', 'ingredient_state'):
            data = self.recipe_payload()
            data[field] = 'invalid'
            self.assertEqual(
                self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data).status_code,
                200,
            )
            self.assertFalse(self.menu.recipe_items.exists())

    def test_unit_changed_after_page_load_requires_reload(self):
        data = self.recipe_payload()
        self.rice.unit = 'g'
        self.rice.save()
        response = self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data)
        self.assertContains(response, 'หน่วยนับเปลี่ยนไป')
        self.assertFalse(self.menu.recipe_items.exists())
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.revision, 0)

    def test_price_change_updates_current_cost_without_changing_recipe(self):
        self.save_recipe()
        self.rice.price = Decimal('50')
        self.rice.save()
        self.assertEqual(read_menu(self.menu).cost_per_serving, Decimal('15'))
        self.assert_example_recipe()

    def test_above_price_cost_warns_but_does_not_block_save(self):
        self.save_recipe(rows=[(self.rice, '2')])
        response = self.client.get(reverse('menus:recipe', args=[self.menu.pk]))
        self.assertContains(response, 'ต้นทุนวัตถุดิบสูงกว่าราคาขาย')
        self.assertTrue(read_menu(self.menu).exceeds_price)

    def test_row_swap_is_valid_without_transient_unique_conflicts(self):
        self.save_recipe()
        self.save_recipe(rows=[(self.egg, '2'), (self.rice, '.300')])
        self.assertEqual(read_menu(self.menu).cost_per_serving, Decimal('22'))

    def test_persistence_failure_rolls_back_all_rows_and_menu_revision(self):
        self.save_recipe()
        revision = self.menu.revision
        data = self.recipe_payload(rows=[(self.rice, '.500'), (self.egg, '1')])
        with patch(
            'menus.services.RecipeItem.objects.bulk_create', side_effect=IntegrityError('failed')
        ):
            with self.assertRaises(IntegrityError):
                self.client.post(reverse('menus:recipe', args=[self.menu.pk]), data)
        self.assert_example_recipe()
        self.menu.refresh_from_db()
        self.assertEqual(self.menu.revision, revision)
