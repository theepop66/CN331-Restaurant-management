from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models, transaction
from django.db.models import Q
from django.db.models.functions import Lower


class Ingredient(models.Model):
    """
    [UC-02] วัตถุดิบของร้านหนึ่ง ๆ (tenant-scoped).

    ทุก query ต้องกรองด้วย `restaurant=request.user.restaurant` เสมอ
    (ดูรูปแบบเดียวกันใน accounts.models.Restaurant)

    - stock_quantity คือยอดคงเหลือรวมของวัตถุดิบ (US-04 จะตัดยอดตอนขาย)
    - วันหมดอายุไม่ได้เก็บที่นี่ แต่เก็บเป็นรายล็อตใน StockIn
    - barcode เว้นว่างได้ ถ้าว่างระบบสร้างรหัส "ING-000042" ให้
      (เพื่อให้ของที่ไม่มีบาร์โค้ด เช่น ผักสด ก็สแกนได้)
    """

    class Unit(models.TextChoices):
        KG = 'kg', 'กก.'
        G = 'g', 'กรัม'
        L = 'l', 'ลิตร'
        ML = 'ml', 'มล.'
        PIECE = 'piece', 'ชิ้น'
        EGG = 'egg', 'ฟอง'
        BOTTLE = 'bottle', 'ขวด'
        PACK = 'pack', 'แพ็ก'
        BAG = 'bag', 'ถุง'

    GENERATED_BARCODE_PREFIX = 'ING-'

    restaurant = models.ForeignKey(
        'accounts.Restaurant',
        on_delete=models.CASCADE,
        related_name='ingredients',
    )
    name = models.CharField('ชื่อวัตถุดิบ', max_length=150)
    barcode = models.CharField(
        'บาร์โค้ด', max_length=64, blank=True,
        help_text='เว้นว่างได้ ระบบจะสร้างรหัสให้อัตโนมัติ',
    )
    unit = models.CharField('หน่วย', max_length=10, choices=Unit.choices)
    stock_quantity = models.DecimalField(
        'ปริมาณคงเหลือ', max_digits=12, decimal_places=3,
        default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))],
    )
    price = models.DecimalField(
        'ราคาต่อหน่วย', max_digits=10, decimal_places=2,
        default=Decimal('0'), validators=[MinValueValidator(Decimal('0'))],
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['name']
        constraints = [
            # ชื่อไม่ซ้ำในร้านเดียวกัน (ไม่สนตัวพิมพ์เล็ก/ใหญ่)
            models.UniqueConstraint(
                Lower('name'), 'restaurant',
                name='uniq_ingredient_name_per_restaurant',
            ),
            # บาร์โค้ดไม่ซ้ำในร้านเดียวกัน (ยกเว้นค่าว่าง)
            models.UniqueConstraint(
                fields=['restaurant', 'barcode'],
                condition=~Q(barcode=''),
                name='uniq_ingredient_barcode_per_restaurant',
            ),
        ]

    def __str__(self):
        return self.name

    @property
    def initial(self):
        """ตัวอักษรแรกของชื่อ (ข้ามสระนำ เช่น เ แ โ ใ ไ) ใช้ทำป้ายกลม ๆ ในหน้ารายการ"""
        for ch in self.name:
            if ch not in 'เแโใไ':
                return ch
        return self.name[:1]

    def save(self, *args, **kwargs):
        with transaction.atomic():
            super().save(*args, **kwargs)
            if not self.barcode:
                self.barcode = f'{self.GENERATED_BARCODE_PREFIX}{self.pk:06d}'
                super().save(update_fields=['barcode'])


class StockIn(models.Model):
    """
    [UC-02] การรับเข้าสต็อกหนึ่งครั้ง = หนึ่งล็อต.

    เก็บวันหมดอายุเป็นรายล็อต (ไม่บังคับ) พร้อมรหัสล็อตที่ระบบสร้างให้
    เช่น LOT-000123 (ไม่ซ้ำในร้านเดียวกัน)

    remaining_quantity เริ่มต้นเท่ากับ quantity UC-02 ไม่ตัดยอดล็อตเอง
    ให้ UC-04 ตัดแบบเข้าก่อนออกก่อน (FIFO) ภายหลัง
    """

    restaurant = models.ForeignKey(
        'accounts.Restaurant',
        on_delete=models.CASCADE,
        related_name='stock_ins',
    )
    ingredient = models.ForeignKey(
        Ingredient,
        on_delete=models.CASCADE,
        related_name='stock_ins',
    )
    lot_code = models.CharField('รหัสล็อต', max_length=32, blank=True)
    quantity = models.DecimalField(
        'จำนวนที่รับเข้า', max_digits=12, decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    remaining_quantity = models.DecimalField(
        'คงเหลือในล็อต', max_digits=12, decimal_places=3,
    )
    expiry_date = models.DateField('วันหมดอายุ', null=True, blank=True)
    received_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True, blank=True,
        related_name='+',
    )
    received_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-received_at', '-id']
        constraints = [
            models.UniqueConstraint(
                fields=['restaurant', 'lot_code'],
                condition=~Q(lot_code=''),
                name='uniq_stockin_lot_per_restaurant',
            ),
        ]

    def __str__(self):
        return f'{self.lot_code or "LOT"} · {self.ingredient}'

    def save(self, *args, **kwargs):
        if self._state.adding and self.remaining_quantity is None:
            self.remaining_quantity = self.quantity
        with transaction.atomic():
            super().save(*args, **kwargs)
            if not self.lot_code:
                self.lot_code = f'LOT-{self.pk:06d}'
                super().save(update_fields=['lot_code'])
