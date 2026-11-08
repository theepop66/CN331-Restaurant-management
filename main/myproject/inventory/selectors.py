"""[UC-02] Read-side queries for inventory (see ADR 001: View -> Service -> Selector)."""

from datetime import date, timedelta
from typing import Optional

from django.db.models import Min, Q, QuerySet
from django.utils import timezone

from accounts.models import Restaurant

from .models import Ingredient, StockIn

EXPIRING_SOON_DAYS = 7


def expiry_state(expiry: Optional[date], today: date) -> str:
    """'expired' | 'soon' | '' สำหรับวันหมดอายุหนึ่งค่า (None = ไม่มีวันหมดอายุ)."""
    if expiry and expiry < today:
        return 'expired'
    if expiry and expiry <= today + timedelta(days=EXPIRING_SOON_DAYS):
        return 'soon'
    return ''


def ingredient_queryset(*, restaurant: Restaurant) -> QuerySet[Ingredient]:
    """วัตถุดิบทั้งหมดของร้าน พร้อม nearest_expiry (หมดอายุเร็วสุดในล็อตที่ยังเหลือ).

    ใช้ annotate (aggregate ใน SQL เดียว) จึงไม่เกิด N+1 ตอนแสดงทุกแถวในหน้ารายการ
    """
    return (
        Ingredient.objects.filter(restaurant=restaurant)
        .annotate(
            nearest_expiry=Min(
                'stock_ins__expiry_date',
                filter=Q(stock_ins__remaining_quantity__gt=0),
            )
        )
        .order_by('name', 'pk')
    )


def search_ingredients(*, restaurant: Restaurant, query: str = '') -> QuerySet[Ingredient]:
    """ค้นหาด้วยชื่อหรือบาร์โค้ด (ว่าง = ทั้งหมด)."""
    qs = ingredient_queryset(restaurant=restaurant)
    query = query.strip()
    if query:
        qs = qs.filter(Q(name__icontains=query) | Q(barcode__icontains=query))
    return qs


def inventory_stats(*, restaurant: Restaurant) -> dict[str, int]:
    """สรุปทั้งร้าน (ไม่ขึ้นกับคำค้น): total / out / soon / expired."""
    today = timezone.localdate()
    stats = {'total': 0, 'out': 0, 'soon': 0, 'expired': 0}
    rows = ingredient_queryset(restaurant=restaurant).values_list(
        'stock_quantity', 'nearest_expiry'
    )
    for stock, expiry in rows:
        stats['total'] += 1
        stats['out'] += stock <= 0
        state = expiry_state(expiry, today)
        if state:
            stats[state] += 1
    return stats


def annotate_expiry_state(items) -> None:
    """ใส่ item.expiry_state ให้แต่ละ Ingredient ที่มี nearest_expiry (แก้ในที่)."""
    today = timezone.localdate()
    for item in items:
        item.expiry_state = expiry_state(item.nearest_expiry, today)


def get_ingredient_lots(*, ingredient: Ingredient) -> list[StockIn]:
    """ล็อตที่รับเข้าของวัตถุดิบ พร้อม lot.expiry_state (โหลด received_by ในคำสั่งเดียว)."""
    today = timezone.localdate()
    lots = list(ingredient.stock_ins.select_related('received_by'))
    for lot in lots:
        lot.expiry_state = expiry_state(lot.expiry_date, today)
    return lots


def find_by_barcode(*, restaurant: Restaurant, barcode: str) -> Optional[Ingredient]:
    return Ingredient.objects.filter(restaurant=restaurant, barcode=barcode).first()


def ingredient_names(*, restaurant: Restaurant):
    return Ingredient.objects.filter(restaurant=restaurant).values_list('name', flat=True)
