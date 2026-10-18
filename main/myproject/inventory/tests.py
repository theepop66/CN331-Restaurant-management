from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser, Restaurant

from .forms import IngredientForm
from .models import Ingredient, StockIn
from .views import _add_stock


class InventoryTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.shop_a = Restaurant.objects.create(name='ร้าน A')
        cls.shop_b = Restaurant.objects.create(name='ร้าน B')
        cls.owner = CustomUser.objects.create_user(
            'owner_a', password='pw12345!', restaurant=cls.shop_a,
            role=CustomUser.Role.OWNER)
        cls.staff = CustomUser.objects.create_user(
            'staff_a', password='pw12345!', restaurant=cls.shop_a,
            role=CustomUser.Role.STAFF)
        cls.owner_b = CustomUser.objects.create_user(
            'owner_b', password='pw12345!', restaurant=cls.shop_b)
        cls.no_shop = CustomUser.objects.create_user('lonely', password='pw12345!')

    def make(self, name='ข้าวสาร', shop=None, **kw):
        defaults = dict(unit='kg', price=Decimal('30'), stock_quantity=Decimal('5'))
        defaults.update(kw)
        return Ingredient.objects.create(
            restaurant=shop or self.shop_a, name=name, **defaults)

    def payload(self, **kw):
        data = {'name': 'น้ำปลา', 'barcode': '', 'unit': 'bottle',
                'price': '25', 'stock_quantity': '0'}
        data.update(kw)
        return data


class CrudAndValidationTests(InventoryTestBase):
    def test_login_required(self):
        resp = self.client.get(reverse('inventory:list'))
        self.assertEqual(resp.status_code, 302)
        self.assertIn('/login/', resp.url)

    def test_user_without_restaurant_is_redirected(self):
        self.client.force_login(self.no_shop)
        resp = self.client.get(reverse('inventory:list'))
        self.assertRedirects(resp, reverse('accounts:home'))

    def test_create_generates_barcode_when_blank(self):
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('inventory:create'), self.payload())
        item = Ingredient.objects.get(name='น้ำปลา')
        self.assertRedirects(resp, reverse('inventory:detail', args=[item.pk]))
        self.assertEqual(item.barcode, f'ING-{item.pk:06d}')
        self.assertEqual(item.restaurant, self.shop_a)

    def test_create_keeps_given_barcode(self):
        self.client.force_login(self.owner)
        self.client.post(reverse('inventory:create'), self.payload(barcode='885123'))
        self.assertEqual(Ingredient.objects.get(name='น้ำปลา').barcode, '885123')

    def test_negative_price_and_stock_rejected(self):
        self.client.force_login(self.owner)
        resp = self.client.post(
            reverse('inventory:create'),
            self.payload(price='-1', stock_quantity='-5'))
        self.assertEqual(resp.status_code, 200)
        self.assertFalse(Ingredient.objects.exists())
        self.assertContains(resp, 'ราคาต้องไม่ติดลบ')
        self.assertContains(resp, 'ปริมาณต้องไม่ติดลบ')

    def test_negative_stock_rejected_on_edit(self):
        item = self.make()
        self.client.force_login(self.owner)
        data = self.payload(
            name=item.name, price='30', stock_quantity='-1',
            expected_revision=item.revision,
        )
        resp = self.client.post(reverse('inventory:update', args=[item.pk]), data)
        self.assertEqual(resp.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('5'))

    def test_duplicate_name_same_restaurant_case_insensitive(self):
        self.make('Rice')
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('inventory:create'), self.payload(name='rice'))
        self.assertContains(resp, 'มีวัตถุดิบชื่อนี้ในร้านแล้ว')
        self.assertEqual(Ingredient.objects.count(), 1)

    def test_same_name_and_barcode_allowed_in_other_restaurant(self):
        self.make('Rice', barcode='111')
        self.client.force_login(self.owner_b)
        self.client.post(reverse('inventory:create'),
                         self.payload(name='Rice', barcode='111'))
        self.assertEqual(Ingredient.objects.filter(name='Rice').count(), 2)

    def test_duplicate_barcode_same_restaurant_rejected(self):
        self.make('Rice', barcode='111')
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('inventory:create'),
                                self.payload(barcode='111'))
        self.assertContains(resp, 'บาร์โค้ดนี้ถูกใช้')

    def test_reserved_prefix_rejected(self):
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('inventory:create'),
                                self.payload(barcode='ING-000001'))
        self.assertContains(resp, 'สงวนไว้ให้ระบบ')

    def test_create_with_initial_quantity_makes_first_lot(self):
        self.client.force_login(self.owner)
        future = (timezone.localdate() + timedelta(days=30)).isoformat()
        self.client.post(reverse('inventory:create'),
                         self.payload(stock_quantity='4', expiry_date=future))
        item = Ingredient.objects.get(name='น้ำปลา')
        lot = item.stock_ins.get()
        self.assertEqual(lot.quantity, Decimal('4'))
        self.assertEqual(lot.remaining_quantity, Decimal('4'))
        self.assertEqual(lot.lot_code, f'LOT-{lot.pk:06d}')
        self.assertEqual(lot.expiry_date.isoformat(), future)

    def test_past_expiry_rejected_on_create(self):
        self.client.force_login(self.owner)
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        resp = self.client.post(reverse('inventory:create'),
                                self.payload(stock_quantity='1', expiry_date=past))
        self.assertContains(resp, 'หมดอายุแล้ว')
        self.assertFalse(Ingredient.objects.exists())

    def test_edit_adjusts_stock_without_stockin(self):
        item = self.make()
        self.client.force_login(self.staff)
        data = self.payload(
            name=item.name, price='31', stock_quantity='9',
            expected_revision=item.revision,
        )
        self.client.post(reverse('inventory:update', args=[item.pk]), data)
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('9'))
        self.assertEqual(item.price, Decimal('31'))
        self.assertFalse(StockIn.objects.exists())


class IngredientEditRegressionTests(InventoryTestBase):
    def setUp(self):
        self.client.force_login(self.owner)

    def open_edit(self, item, **changes):
        response = self.client.get(reverse('inventory:update', args=[item.pk]))
        self.assertContains(response, 'name="expected_revision"')
        data = self.payload(
            name=item.name, barcode=item.barcode, unit=item.unit,
            price=str(item.price), stock_quantity=str(item.stock_quantity),
            expected_revision=response.context['form']['expected_revision'].value(),
        )
        data.update(changes)
        return data

    def test_generated_barcode_is_preserved_when_editing_name_and_price(self):
        item = self.make()
        original_barcode = item.barcode
        data = self.open_edit(item, name='Rice renamed', price='31')
        response = self.client.post(
            reverse('inventory:update', args=[item.pk]), data,
        )
        self.assertRedirects(response, reverse('inventory:detail', args=[item.pk]))
        item.refresh_from_db()
        self.assertEqual(item.name, 'Rice renamed')
        self.assertEqual(item.price, Decimal('31'))
        self.assertEqual(item.barcode, original_barcode)
        self.assertEqual(item.stock_quantity, Decimal('5'))
        self.assertEqual(item.revision, 1)

    def test_edit_cannot_assign_another_reserved_barcode(self):
        item = self.make(barcode='555')
        data = self.open_edit(item, barcode='ING-999999')
        response = self.client.post(
            reverse('inventory:update', args=[item.pk]), data,
        )
        self.assertContains(response, 'สงวนไว้ให้ระบบ')
        item.refresh_from_db()
        self.assertEqual(item.barcode, '555')
        self.assertEqual(item.revision, 0)

    def test_edit_cannot_reuse_another_ingredients_barcode(self):
        item = self.make(barcode='555')
        self.make(name='Other', barcode='666')
        data = self.open_edit(item, barcode='666')
        response = self.client.post(
            reverse('inventory:update', args=[item.pk]), data,
        )
        self.assertContains(response, 'บาร์โค้ดนี้ถูกใช้')
        item.refresh_from_db()
        self.assertEqual(item.barcode, '555')

    def test_clearing_barcode_on_edit_still_generates_a_code(self):
        item = self.make(barcode='555')
        data = self.open_edit(item, barcode='')
        response = self.client.post(
            reverse('inventory:update', args=[item.pk]), data,
        )
        self.assertEqual(response.status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.barcode, f'ING-{item.pk:06d}')

    def test_stale_price_edit_does_not_overwrite_stock_receipt(self):
        item = self.make()
        data = self.open_edit(item, price='31')
        self.client.post(
            reverse('inventory:stock_in', args=[item.pk]), {'quantity': '3'},
        )
        response = self.client.post(
            reverse('inventory:update', args=[item.pk]), data,
        )
        self.assertContains(response, 'กรุณาโหลดหน้าใหม่ก่อนบันทึก')
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('8'))
        self.assertEqual(item.price, Decimal('30'))
        self.assertEqual(item.revision, 1)
        lot = item.stock_ins.get()
        self.assertEqual(lot.quantity, Decimal('3'))
        self.assertEqual(lot.remaining_quantity, Decimal('3'))

    def test_stale_edit_does_not_overwrite_quick_scan(self):
        item = self.make(barcode='555')
        data = self.open_edit(item, price='31')
        self.client.post(
            reverse('inventory:scan'), {'barcode': '555', 'quick_mode': 'on'},
        )
        response = self.client.post(
            reverse('inventory:update', args=[item.pk]), data,
        )
        self.assertContains(response, 'กรุณาโหลดหน้าใหม่ก่อนบันทึก')
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('6'))
        self.assertEqual(item.price, Decimal('30'))
        self.assertEqual(item.revision, 1)
        self.assertEqual(item.stock_ins.count(), 1)

    def test_two_editors_cannot_save_the_same_revision(self):
        item = self.make()
        first = self.open_edit(item, price='31')
        second = self.open_edit(item, price='32')
        url = reverse('inventory:update', args=[item.pk])
        self.assertEqual(self.client.post(url, first).status_code, 302)
        self.assertContains(
            self.client.post(url, second), 'กรุณาโหลดหน้าใหม่ก่อนบันทึก',
        )
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal('31'))
        self.assertEqual(item.revision, 1)
        fresh = self.open_edit(item, price='32')
        self.assertEqual(self.client.post(url, fresh).status_code, 302)
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal('32'))
        self.assertEqual(item.revision, 2)

    def test_receipt_during_edit_validation_is_not_overwritten(self):
        item = self.make()
        data = self.open_edit(item, price='31')
        original_is_valid = IngredientForm.is_valid

        def receive_after_validation(form):
            valid = original_is_valid(form)
            _add_stock(self.shop_a, item.pk, Decimal('3'), self.owner)
            return valid

        with patch.object(
            IngredientForm, 'is_valid', autospec=True,
            side_effect=receive_after_validation,
        ):
            response = self.client.post(
                reverse('inventory:update', args=[item.pk]), data,
            )
        self.assertContains(response, 'กรุณาโหลดหน้าใหม่ก่อนบันทึก')
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('8'))
        self.assertEqual(item.price, Decimal('30'))
        self.assertEqual(item.stock_ins.get().remaining_quantity, Decimal('3'))

    def test_missing_revision_cannot_bypass_stale_edit_protection(self):
        item = self.make()
        data = self.open_edit(item, price='31')
        del data['expected_revision']
        response = self.client.post(
            reverse('inventory:update', args=[item.pk]), data,
        )
        self.assertContains(response, 'กรุณาโหลดหน้าใหม่ก่อนบันทึก')
        item.refresh_from_db()
        self.assertEqual(item.price, Decimal('30'))
        self.assertEqual(item.revision, 0)


class StockLimitRegressionTests(InventoryTestBase):
    maximum = Decimal('999999999.999')

    def setUp(self):
        self.client.force_login(self.owner)

    def test_manual_receipt_can_reach_the_exact_limit(self):
        item = self.make(stock_quantity=self.maximum - Decimal('0.001'))
        response = self.client.post(
            reverse('inventory:stock_in', args=[item.pk]),
            {'quantity': '0.001'}, follow=True,
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, self.maximum)
        self.assertEqual(item.revision, 1)
        self.assertEqual(item.stock_ins.get().quantity, Decimal('0.001'))

    def test_manual_overflow_leaves_stock_and_lots_unchanged(self):
        item = self.make(stock_quantity=self.maximum)
        response = self.client.post(
            reverse('inventory:stock_in', args=[item.pk]),
            {'quantity': '0.001'}, follow=True,
        )
        self.assertContains(response, 'ปริมาณคงเหลือรวมต้องไม่เกิน')
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, self.maximum)
        self.assertEqual(item.revision, 0)
        self.assertFalse(item.stock_ins.exists())
        self.assertEqual(self.client.get(reverse('inventory:list')).status_code, 200)

    def test_quick_scan_can_reach_the_exact_limit(self):
        item = self.make(barcode='555', stock_quantity=self.maximum - 1)
        response = self.client.post(
            reverse('inventory:scan'),
            {'barcode': '555', 'quick_mode': 'on'}, follow=True,
        )
        self.assertEqual(response.status_code, 200)
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, self.maximum)
        self.assertEqual(item.revision, 1)
        self.assertEqual(item.stock_ins.get().quantity, Decimal('1'))

    def test_quick_scan_overflow_leaves_stock_and_lots_unchanged(self):
        item = self.make(barcode='555', stock_quantity=self.maximum)
        response = self.client.post(
            reverse('inventory:scan'),
            {'barcode': '555', 'quick_mode': 'on'}, follow=True,
        )
        self.assertContains(response, 'ปริมาณคงเหลือรวมต้องไม่เกิน')
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, self.maximum)
        self.assertEqual(item.revision, 0)
        self.assertFalse(item.stock_ins.exists())

    def test_later_receipt_cannot_exceed_a_limit_reached_by_another_receipt(self):
        item = self.make(stock_quantity=self.maximum - Decimal('0.001'))
        url = reverse('inventory:stock_in', args=[item.pk])
        self.client.post(url, {'quantity': '0.001'})
        response = self.client.post(url, {'quantity': '0.001'}, follow=True)
        self.assertContains(response, 'ปริมาณคงเหลือรวมต้องไม่เกิน')
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, self.maximum)
        self.assertEqual(item.revision, 1)
        self.assertEqual(item.stock_ins.count(), 1)

    def test_lot_failure_rolls_back_stock_and_revision(self):
        item = self.make()
        with patch.object(
            StockIn.objects, 'create', side_effect=RuntimeError('lot failed'),
        ):
            with self.assertRaisesMessage(RuntimeError, 'lot failed'):
                _add_stock(self.shop_a, item.pk, Decimal('3'), self.owner)
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('5'))
        self.assertEqual(item.revision, 0)
        self.assertFalse(item.stock_ins.exists())


class TenantIsolationTests(InventoryTestBase):
    def test_other_restaurant_cannot_see_or_touch(self):
        item = self.make()
        self.client.force_login(self.owner_b)
        self.assertNotContains(self.client.get(reverse('inventory:list')), item.name)
        for name in ('detail', 'update', 'delete'):
            resp = self.client.get(reverse(f'inventory:{name}', args=[item.pk]))
            self.assertEqual(resp.status_code, 404, name)
        resp = self.client.post(reverse('inventory:stock_in', args=[item.pk]),
                                {'quantity': '3'})
        self.assertEqual(resp.status_code, 404)
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('5'))

    def test_scan_does_not_find_other_restaurants_barcode(self):
        self.make(barcode='999')
        self.client.force_login(self.owner_b)
        resp = self.client.post(reverse('inventory:scan'),
                                {'barcode': '999', 'quick_mode': 'on'})
        self.assertIn('not_found=999', resp.url)
        self.assertEqual(StockIn.objects.count(), 0)


class StockInTests(InventoryTestBase):
    def test_stock_in_adds_and_creates_lot(self):
        item = self.make()
        self.client.force_login(self.staff)
        resp = self.client.post(reverse('inventory:stock_in', args=[item.pk]),
                                {'quantity': '3'}, follow=True)
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('8'))
        lot = item.stock_ins.get()
        self.assertEqual(lot.received_by, self.staff)
        self.assertContains(resp, 'ข้าวสาร: 5 → 8 กก.')

    def test_stock_in_zero_or_negative_rejected(self):
        item = self.make()
        self.client.force_login(self.owner)
        for bad in ('0', '-2', ''):
            self.client.post(reverse('inventory:stock_in', args=[item.pk]),
                             {'quantity': bad})
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('5'))
        self.assertFalse(StockIn.objects.exists())

    def test_stock_in_past_expiry_rejected(self):
        item = self.make()
        self.client.force_login(self.owner)
        past = (timezone.localdate() - timedelta(days=1)).isoformat()
        self.client.post(reverse('inventory:stock_in', args=[item.pk]),
                         {'quantity': '2', 'expiry_date': past})
        self.assertFalse(StockIn.objects.exists())

    def test_row_form_next_redirect_is_safe(self):
        item = self.make()
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('inventory:stock_in', args=[item.pk]),
                                {'quantity': '1', 'next': 'https://evil.example/'})
        self.assertEqual(resp.url, reverse('inventory:detail', args=[item.pk]))
        resp = self.client.post(reverse('inventory:stock_in', args=[item.pk]),
                                {'quantity': '1', 'next': '/inventory/?q=x'})
        self.assertEqual(resp.url, '/inventory/?q=x')

    def test_decimal_quantity(self):
        item = self.make(unit='kg', stock_quantity=Decimal('1.5'))
        self.client.force_login(self.owner)
        self.client.post(reverse('inventory:stock_in', args=[item.pk]),
                         {'quantity': '0.25'})
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('1.75'))


class ScanTests(InventoryTestBase):
    def test_unknown_barcode_does_not_crash(self):
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('inventory:scan'),
                                {'barcode': 'nope'}, follow=True)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'ไม่พบวัตถุดิบ')
        self.assertContains(resp, 'barcode=nope')

    def test_normal_mode_goes_to_detail(self):
        item = self.make(barcode='555')
        self.client.force_login(self.owner)
        resp = self.client.post(reverse('inventory:scan'),
                                {'barcode': ' 555 '})
        self.assertEqual(
            resp.url, reverse('inventory:detail', args=[item.pk]) + '#stock-in')
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('5'))

    def test_quick_mode_adds_each_scan(self):
        item = self.make(barcode='555')
        self.client.force_login(self.owner)
        data = {'barcode': '555', 'quick_mode': 'on'}
        self.client.post(reverse('inventory:scan'), data)
        resp = self.client.post(reverse('inventory:scan'), data, follow=True)
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('7'))
        self.assertEqual(item.stock_ins.count(), 2)
        self.assertContains(resp, 'ข้าวสาร: 6 → 7 กก.')

    def test_generated_barcode_is_scannable(self):
        item = self.make()
        self.assertTrue(item.barcode.startswith('ING-'))
        self.client.force_login(self.owner)
        self.client.post(reverse('inventory:scan'),
                         {'barcode': item.barcode, 'quick_mode': 'on'})
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('6'))

    def test_quick_mode_ignores_client_quantity_and_adds_one(self):
        item = self.make(barcode='555')
        self.client.force_login(self.owner)
        self.client.post(reverse('inventory:scan'),
                         {'barcode': '555', 'quantity': '99', 'quick_mode': 'on'})
        item.refresh_from_db()
        self.assertEqual(item.stock_quantity, Decimal('6'))

    def test_quick_mode_preference_is_remembered(self):
        self.make(barcode='555')
        self.client.force_login(self.owner)
        self.client.post(reverse('inventory:scan'),
                         {'barcode': '555', 'quick_mode': 'on'})
        resp = self.client.get(reverse('inventory:list'))
        self.assertContains(resp, 'checked')


class DeleteAndListTests(InventoryTestBase):
    def test_staff_cannot_delete(self):
        item = self.make()
        self.client.force_login(self.staff)
        self.client.post(reverse('inventory:delete', args=[item.pk]))
        self.assertTrue(Ingredient.objects.filter(pk=item.pk).exists())

    def test_owner_can_delete_with_confirmation(self):
        item = self.make()
        self.client.force_login(self.owner)
        page = self.client.get(reverse('inventory:delete', args=[item.pk]))
        self.assertContains(page, 'ยืนยันการลบ')
        self.assertTrue(Ingredient.objects.filter(pk=item.pk).exists())
        self.client.post(reverse('inventory:delete', args=[item.pk]))
        self.assertFalse(Ingredient.objects.filter(pk=item.pk).exists())

    def test_search_and_expiry_badges(self):
        a = self.make('ข้าวสาร')
        self.make('น้ำตาล')
        today = timezone.localdate()
        StockIn.objects.create(restaurant=self.shop_a, ingredient=a,
                               quantity=1, remaining_quantity=1,
                               expiry_date=today + timedelta(days=3))
        self.client.force_login(self.owner)
        resp = self.client.get(reverse('inventory:list'), {'q': 'ข้าว'})
        self.assertContains(resp, 'ข้าวสาร')
        self.assertNotContains(resp, 'น้ำตาล')
        self.assertContains(resp, 'chip chip-warn')

    def test_expired_lot_with_no_remaining_is_ignored(self):
        a = self.make('ข้าวสาร')
        StockIn.objects.create(
            restaurant=self.shop_a, ingredient=a, quantity=1, remaining_quantity=0,
            expiry_date=timezone.localdate() - timedelta(days=5))
        self.client.force_login(self.owner)
        self.assertNotContains(self.client.get(reverse('inventory:list')), 'หมดอายุแล้ว')

    def test_pagination(self):
        for i in range(25):
            self.make(f'item{i:02d}')
        self.client.force_login(self.owner)
        self.assertEqual(len(self.client.get(reverse('inventory:list')).context['page']), 20)
        self.assertEqual(
            len(self.client.get(reverse('inventory:list'), {'page': 2}).context['page']), 5)
