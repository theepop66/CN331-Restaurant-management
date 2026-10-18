from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser, Restaurant
from inventory.models import Ingredient
from menus.models import MenuItem


class MenuTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.shop = Restaurant.objects.create(name='ร้าน A')
        cls.other_shop = Restaurant.objects.create(name='ร้าน B')
        cls.owner = CustomUser.objects.create_user('owner', restaurant=cls.shop)
        cls.other_owner = CustomUser.objects.create_user(
            'other',
            restaurant=cls.other_shop,
        )
        cls.staff = CustomUser.objects.create_user(
            'staff',
            restaurant=cls.shop,
            role=CustomUser.Role.STAFF,
        )
        cls.menu = MenuItem.objects.create(
            restaurant=cls.shop,
            name='Fried Rice',
            price=50,
        )
        cls.other_menu = MenuItem.objects.create(
            restaurant=cls.other_shop,
            name='Secret dish',
            price=60,
        )
        cls.rice = Ingredient.objects.create(
            restaurant=cls.shop,
            name='Rice',
            unit='kg',
            price=40,
            stock_quantity=10,
        )
        cls.egg = Ingredient.objects.create(
            restaurant=cls.shop,
            name='Egg',
            unit='egg',
            price=5,
            stock_quantity=20,
        )
        cls.foreign = Ingredient.objects.create(
            restaurant=cls.other_shop,
            name='Secret ingredient',
            unit='kg',
            price=20,
        )

    def setUp(self):
        self.client.force_login(self.owner)

    def recipe_payload(self, menu=None, rows=None):
        menu = menu or self.menu
        rows = rows if rows is not None else [(self.rice, '.200'), (self.egg, '1')]
        page = self.client.get(reverse('menus:recipe', args=[menu.pk]))
        version = page.context['revision_form']
        existing = list(menu.recipe_items.order_by('pk'))
        payload = {
            'expected_revision': version['expected_revision'].value(),
            'ingredient_state': version['ingredient_state'].value(),
            'items-TOTAL_FORMS': str(len(rows)),
            'items-INITIAL_FORMS': str(len(existing)),
        }
        for index, (ingredient, quantity) in enumerate(rows):
            payload[f'items-{index}-ingredient'] = str(ingredient.pk) if ingredient else ''
            payload[f'items-{index}-quantity_used'] = str(quantity)
            if index < len(existing):
                payload[f'items-{index}-id'] = str(existing[index].pk)
        return payload

    def save_recipe(self, menu=None, rows=None):
        menu = menu or self.menu
        response = self.client.post(
            reverse('menus:recipe', args=[menu.pk]),
            self.recipe_payload(menu, rows),
        )
        self.assertEqual(response.status_code, 302)
        menu.refresh_from_db()
        return response

    def activate(self, menu=None, active=True):
        menu = menu or self.menu
        menu.refresh_from_db()
        return self.client.post(
            reverse('menus:availability', args=[menu.pk]),
            {
                'expected_revision': menu.revision,
                'is_active': 'on' if active else '',
            },
        )

    def assert_example_recipe(self, menu=None):
        menu = menu or self.menu
        self.assertEqual(
            dict(
                menu.recipe_items.values_list(
                    'ingredient_id',
                    'quantity_used',
                )
            ),
            {self.rice.pk: Decimal('.200'), self.egg.pk: Decimal('1')},
        )
