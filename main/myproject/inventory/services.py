"""[UC-02] Write-side business logic for inventory (see ADR 001)."""

from datetime import date
from decimal import Decimal
from typing import Optional

from django.core.exceptions import ValidationError
from django.db import transaction
from django.db.models import F
from django.utils import timezone

from accounts.models import Restaurant

from .models import Ingredient, StockIn

QUICK_SCAN_STEP = Decimal('1')  # โหมดสแกนรัว: บวกครั้งละ 1 ตายตัว (ไม่ต้องให้ผู้ใช้เลือก)


def format_quantity(value) -> str:
    """แสดงทศนิยมแบบสั้น เช่น Decimal('5.000') -> '5'"""
    return format(Decimal(value).normalize(), 'f')


def stock_message(ingredient: Ingredient, old, new) -> str:
    return (
        f'{ingredient.name}: {format_quantity(old)} → {format_quantity(new)} '
        f'{ingredient.get_unit_display()}'
    )


def add_stock(
    restaurant: Restaurant,
    ingredient_id: int,
    quantity: Decimal,
    user,
    expiry_date: Optional[date] = None,
):
    """
    บวกสต็อกและสร้างล็อต (StockIn) ในธุรกรรมเดียว
    คืนค่า (ingredient, ยอดเดิม, ยอดใหม่, ล็อต)
    """
    field = Ingredient._meta.get_field('stock_quantity')
    maximum = Decimal(10) ** (field.max_digits - field.decimal_places) - Decimal(1).scaleb(
        -field.decimal_places
    )
    with transaction.atomic():
        # Check and increment together; SQLite does not support row locks.
        updated = Ingredient.objects.filter(
            pk=ingredient_id,
            restaurant=restaurant,
            stock_quantity__lte=maximum - quantity,
        ).update(
            stock_quantity=F('stock_quantity') + quantity,
            revision=F('revision') + 1,
            updated_at=timezone.now(),
        )
        ingredient = Ingredient.objects.get(
            pk=ingredient_id,
            restaurant=restaurant,
        )
        if not updated:
            raise ValidationError(f'ปริมาณคงเหลือรวมต้องไม่เกิน {format_quantity(maximum)}')
        old = ingredient.stock_quantity - quantity
        lot = StockIn.objects.create(
            restaurant=restaurant,
            ingredient=ingredient,
            quantity=quantity,
            remaining_quantity=quantity,
            expiry_date=expiry_date,
            received_by=user,
        )
    return ingredient, old, ingredient.stock_quantity, lot


def create_ingredient(
    *,
    restaurant: Restaurant,
    ingredient: Ingredient,
    user,
    expiry_date: Optional[date] = None,
) -> Ingredient:
    """บันทึกวัตถุดิบใหม่ (ยังไม่ save) ถ้ามีปริมาณเริ่มต้นจะสร้างล็อตแรกให้ ในธุรกรรมเดียว."""
    with transaction.atomic():
        ingredient.restaurant = restaurant
        initial_qty = ingredient.stock_quantity
        ingredient.save()
        if initial_qty > 0:
            StockIn.objects.create(
                restaurant=restaurant,
                ingredient=ingredient,
                quantity=initial_qty,
                remaining_quantity=initial_qty,
                expiry_date=expiry_date,
                received_by=user,
            )
    return ingredient
