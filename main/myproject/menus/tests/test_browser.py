"""[US-03] Optional real-browser verification of the owner recipe workflow.

Run with RUN_BROWSER_TESTS=1. Install Playwright and use a local Edge/Chrome
through BROWSER_EXECUTABLE, or install Playwright Chromium separately.
"""

import os
from unittest import skipUnless

from django.conf import settings
from django.contrib.staticfiles.testing import StaticLiveServerTestCase

from accounts.models import CustomUser, Restaurant
from inventory.models import Ingredient


@skipUnless(os.environ.get('RUN_BROWSER_TESTS') == '1', 'Optional browser check')
class RecipeBrowserTests(StaticLiveServerTestCase):
    def test_dynamic_rows_save_activation_and_mobile_layout(self):
        from playwright.sync_api import sync_playwright

        restaurant = Restaurant.objects.create(name='ร้านทดสอบหน้าจอ')
        owner = CustomUser.objects.create_user('browser-owner', restaurant=restaurant)
        rice = Ingredient.objects.create(
            restaurant=restaurant,
            name='ข้าวสาร',
            unit='kg',
            price=40,
        )
        egg = Ingredient.objects.create(
            restaurant=restaurant,
            name='ไข่',
            unit='egg',
            price=5,
        )
        self.client.force_login(owner)
        with sync_playwright() as playwright:
            launch = {'headless': True}
            executable = os.environ.get('BROWSER_EXECUTABLE')
            if executable:
                launch['executable_path'] = executable
            browser = playwright.chromium.launch(**launch)
            page = browser.new_page(viewport={'width': 1365, 'height': 950})
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.context.add_cookies(
                [
                    {
                        'name': settings.SESSION_COOKIE_NAME,
                        'value': self.client.cookies[settings.SESSION_COOKIE_NAME].value,
                        'url': self.live_server_url,
                    }
                ]
            )
            page.goto(f'{self.live_server_url}/menus/new/')
            page.get_by_label('ชื่อเมนู').fill('ข้าวผัดไข่')
            page.get_by_label('ราคาขาย (บาท)').fill('50')
            page.get_by_role('button', name='บันทึกและเพิ่มสูตรอาหาร').click()
            page.wait_for_url('**/recipe/')
            page.locator('#id_items-0-ingredient').select_option(str(rice.pk))
            page.locator('#id_items-0-quantity_used').fill('0.200')
            page.get_by_role('button', name='+ เพิ่มวัตถุดิบ').click()
            page.locator('#id_items-1-ingredient').select_option(str(egg.pk))
            page.locator('#id_items-1-quantity_used').fill('1')
            page.get_by_role('button', name='บันทึกสูตรอาหาร', exact=True).click()
            page.wait_for_load_state('networkidle')
            self.assertIn('฿13.00', page.locator('main').inner_text())
            page.get_by_role('button', name='เปิดขายเมนูนี้').click()
            page.wait_for_load_state('networkidle')
            self.assertTrue(page.get_by_role('button', name='ปิดขายเมนูนี้').is_visible())

            # An invalid duplicate keeps the entered row visible; removing it
            # through the dynamic button submits Django's deletion marker.
            page.locator('#id_items-2-ingredient').select_option(str(rice.pk))
            page.locator('#id_items-2-quantity_used').fill('0.1')
            page.get_by_role('button', name='บันทึกสูตรอาหาร', exact=True).click()
            page.wait_for_load_state('networkidle')
            self.assertIn('ไม่ซ้ำ', page.locator('main').inner_text())
            page.locator('.recipe-row').nth(2).get_by_role('button', name='ลบ', exact=True).click()
            page.get_by_role('button', name='บันทึกสูตรอาหาร', exact=True).click()
            page.wait_for_load_state('networkidle')
            self.assertIn('฿13.00', page.locator('main').inner_text())
            page.set_viewport_size({'width': 390, 'height': 844})
            self.assertLessEqual(page.evaluate('document.documentElement.scrollWidth'), 390)
            self.assertTrue(
                page.get_by_role('button', name='บันทึกสูตรอาหาร', exact=True).is_visible()
            )
            self.assertEqual(errors, [])
            screenshot = os.environ.get('BROWSER_SCREENSHOT')
            if screenshot:
                page.screenshot(path=screenshot, full_page=True)
            browser.close()
