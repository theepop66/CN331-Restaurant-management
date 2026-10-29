"""[US-04][UC-04] Models for Mini-POS Order, OrderItem, and StockDeduction."""

from decimal import Decimal

from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models


class Order(models.Model):
    """[US-04] Represents a completed sale in Mini-POS."""

    class Status(models.TextChoices):
        COMPLETED = 'completed', 'สำเร็จ'
        CANCELLED = 'cancelled', 'ยกเลิก'

    restaurant = models.ForeignKey(
        'accounts.Restaurant',
        on_delete=models.CASCADE,
        related_name='orders',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_orders',
    )
    created_at = models.DateTimeField('เวลาสั่งซื้อ', auto_now_add=True)
    total_amount = models.DecimalField(
        'ยอดรวม (บาท)',
        max_digits=12,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    status = models.CharField(
        'สถานะ',
        max_length=20,
        choices=Status.choices,
        default=Status.COMPLETED,
    )

    class Meta:
        ordering = ['-created_at', '-id']

    def __str__(self):
        return f'Order #{self.pk} ({self.get_status_display()}) - {self.total_amount} ฿'


class OrderItem(models.Model):
    """[US-04] Snapshot of each menu item ordered."""

    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items',
    )
    menu_item = models.ForeignKey(
        'menus.MenuItem',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='order_items',
    )
    name_snapshot = models.CharField('ชื่อเมนู (ขณะสั่ง)', max_length=150)
    unit_price = models.DecimalField(
        'ราคาต่อหน่วย (บาท)',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )
    quantity = models.PositiveIntegerField(
        'จำนวน',
        validators=[MinValueValidator(1)],
    )
    line_total = models.DecimalField(
        'ยอดรวมรายการ (บาท)',
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        return f'{self.name_snapshot} x {self.quantity}'


class StockDeduction(models.Model):
    """[US-04] Audit record tracking each lot deduction for an order item."""

    order_item = models.ForeignKey(
        OrderItem,
        on_delete=models.CASCADE,
        related_name='stock_deductions',
    )
    ingredient = models.ForeignKey(
        'inventory.Ingredient',
        on_delete=models.PROTECT,
        related_name='stock_deductions',
    )
    lot = models.ForeignKey(
        'inventory.StockIn',
        on_delete=models.PROTECT,
        null=True,
        blank=True,
        related_name='stock_deductions',
    )
    quantity = models.DecimalField(
        'ปริมาณที่ตัด',
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )

    class Meta:
        ordering = ['id']

    def __str__(self):
        lot_info = f'Lot #{self.lot_id}' if self.lot_id else 'No Lot'
        return f'{self.ingredient.name} -{self.quantity} ({lot_info})'
