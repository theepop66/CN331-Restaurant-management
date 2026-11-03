"""Tenant-scoped analytics calculations and optional OpenAI-compatible advice."""

import json
import os
from datetime import timedelta
from decimal import Decimal
from urllib.error import URLError
from urllib.request import Request, urlopen

from django.db.models import Sum
from django.utils import timezone

from inventory.models import Ingredient, StockIn
from menus.models import MenuItem
from orders.models import Order, OrderItem, StockDeduction

from .models import AIInsight


def build_dashboard_data(restaurant):
    """Build summary, per-menu margins, and recent stock movement for one tenant."""
    ingredients = Ingredient.objects.filter(restaurant=restaurant)
    stock_value = sum((item.stock_quantity * item.price for item in ingredients), Decimal('0.00'))

    menu_costs = []
    for menu in MenuItem.objects.filter(restaurant=restaurant).prefetch_related(
        'recipe_items__ingredient'
    ):
        cost = Decimal('0.00')
        missing_cost = False
        for recipe in menu.recipe_items.all():
            if recipe.ingredient_id:
                cost += recipe.quantity_used * recipe.ingredient.price
            else:
                missing_cost = True
        gross_profit = menu.price - cost
        margin = (gross_profit / menu.price * 100) if menu.price else Decimal('0')
        menu_costs.append(
            {
                'menu': menu,
                'cost': cost,
                'gross_profit': gross_profit,
                'margin': margin,
                'missing_cost': missing_cost,
            }
        )

    now = timezone.now()
    cutoff = now - timedelta(days=30)
    previous_cutoff = cutoff - timedelta(days=30)
    sales_qs = Order.objects.filter(restaurant=restaurant, status=Order.Status.COMPLETED)
    sales = sales_qs.filter(created_at__gte=cutoff, created_at__lte=now).aggregate(
        total=Sum('total_amount')
    )['total'] or Decimal('0.00')
    previous_sales = sales_qs.filter(
        created_at__gte=previous_cutoff, created_at__lt=cutoff
    ).aggregate(total=Sum('total_amount'))['total'] or Decimal('0.00')
    sales_change_percent = (
        (sales - previous_sales) / previous_sales * 100 if previous_sales else None
    )
    sold = (
        OrderItem.objects.filter(
            order__restaurant=restaurant,
            order__status=Order.Status.COMPLETED,
            order__created_at__gte=cutoff,
            order__created_at__lte=now,
            menu_item__isnull=False,
        )
        .values('menu_item_id', 'name_snapshot')
        .annotate(quantity=Sum('quantity'), revenue=Sum('line_total'))
        .order_by('-quantity', '-revenue')
    )
    best_menu = None
    for costing in sorted(menu_costs, key=lambda row: row['gross_profit'], reverse=True):
        if costing['gross_profit'] > 0:
            best_menu = {
                'name': costing['menu'].name,
                'profit': costing['gross_profit'],
                'quantity': next(
                    (row['quantity'] for row in sold if row['menu_item_id'] == costing['menu'].pk),
                    0,
                ),
            }
            break

    recent_movements = list(
        StockDeduction.objects.filter(
            order_item__order__restaurant=restaurant,
            order_item__order__status=Order.Status.COMPLETED,
        ).select_related('ingredient', 'lot', 'order_item__order')[:25]
    )
    recent_receipts = list(
        StockIn.objects.filter(restaurant=restaurant)
        .select_related('ingredient')
        .order_by('-received_at')[:15]
    )
    low_stock = [item for item in ingredients if item.stock_quantity <= item.par_level]
    restock_suggestions = [
        {
            'ingredient': item,
            'quantity': max(item.par_level * 2 - item.stock_quantity, Decimal('0')),
            'unit': item.unit,
        }
        for item in low_stock
        if item.par_level > 0
    ]
    expiring_lots = list(
        StockIn.objects.filter(
            restaurant=restaurant,
            remaining_quantity__gt=0,
            expiry_date__isnull=False,
            expiry_date__lte=timezone.localdate() + timedelta(days=7),
        )
        .select_related('ingredient')
        .order_by('expiry_date')[:20]
    )
    return {
        'stock_value': stock_value,
        'sales_30d': sales,
        'sales_previous_30d': previous_sales,
        'sales_change_percent': sales_change_percent,
        'menu_costs': menu_costs,
        'best_menu': best_menu,
        'recent_movements': recent_movements,
        'recent_receipts': recent_receipts,
        'low_stock': low_stock,
        'restock_suggestions': restock_suggestions,
        'expiring_lots': expiring_lots,
        'top_sellers': list(sold[:5]),
    }


def _rules_based_insights(data):
    suggestions = []
    if data['low_stock']:
        items = ', '.join(
            f"{row['ingredient'].name}: สั่งประมาณ {row['quantity']} {row['ingredient'].unit}"
            for row in data['restock_suggestions'][:5]
        )
        if items:
            message_prefix = 'ถึงจุดสั่งซื้อแล้ว ควรสั่งโดยเร็วเพื่อเติมถึง 2 เท่าของจุดเตือน: '
            suggestions.append(f'{message_prefix}{items}')
        unset = [item.name for item in data['low_stock'] if item.par_level <= 0]
        if unset:
            names = ', '.join(unset[:5])
            suggestions.append('กำหนดจุดสั่งซื้อซ้ำสำหรับวัตถุดิบที่ยังไม่ตั้งค่า: ' f'{names}')
    if data['expiring_lots']:
        lots = ', '.join(
            f'{lot.ingredient.name} ({lot.expiry_date:%d/%m})' for lot in data['expiring_lots'][:5]
        )
        suggestions.append(f'วางแผนใช้ล็อตที่ใกล้หมดอายุก่อน: {lots}')
    if data['best_menu']:
        item = data['best_menu']
        suggestions.append(
            f"เมนูขายดีใน 30 วัน: {item['name']} ({item['quantity']} จาน) "
            f"กำไรขั้นต้นตามสูตรปัจจุบันประมาณ {item['profit']:.2f} บาท"
        )
    if data['sales_change_percent'] is not None:
        direction = 'เพิ่มขึ้น' if data['sales_change_percent'] >= 0 else 'ลดลง'
        suggestions.append(
            f"ยอดขาย 30 วัน {direction} {abs(data['sales_change_percent']):.1f}% "
            'เมื่อเทียบกับ 30 วันก่อนหน้า'
        )
    if not suggestions:
        suggestions.append('ยังไม่มีสัญญาณเร่งด่วนจากข้อมูลสต็อกและยอดขายปัจจุบัน')
    return '\n'.join(suggestions)


def get_ai_insights(restaurant, data):
    """Use configured OpenAI-compatible API; safely fall back to local heuristics."""
    api_key = os.environ.get('OPENAI_API_KEY')
    if not api_key:
        return _rules_based_insights(data), 'rules'

    cached = AIInsight.objects.filter(restaurant=restaurant, provider='openai').first()
    if cached and cached.generated_at >= timezone.now() - timedelta(hours=6):
        return cached.content, 'openai'

    payload = {
        'model': os.environ.get('OPENAI_MODEL', 'gpt-4o-mini'),
        'messages': [
            {
                'role': 'system',
                'content': (
                    'You are a restaurant inventory and margin advisor. Use only supplied '
                    'data, clearly label estimates, give concise actionable Thai advice, '
                    'and never invent quantities or sales trends.'
                ),
            },
            {
                'role': 'user',
                'content': json.dumps(
                    {
                        'sales_last_30_days': str(data['sales_30d']),
                        'sales_previous_30_days': str(data['sales_previous_30d']),
                        'sales_change_percent': (
                            str(data['sales_change_percent'])
                            if data['sales_change_percent'] is not None
                            else None
                        ),
                        'top_sellers': [
                            {
                                'name': x['name_snapshot'],
                                'quantity': x['quantity'],
                                'revenue': str(x['revenue']),
                            }
                            for x in data['top_sellers']
                        ],
                        'reorder_now': [
                            {
                                'ingredient': row['ingredient'].name,
                                'stock': str(row['ingredient'].stock_quantity),
                                'par_level': str(row['ingredient'].par_level),
                                'suggested_order_quantity': str(row['quantity']),
                                'unit': row['ingredient'].unit,
                            }
                            for row in data['restock_suggestions']
                        ],
                        'reorder_point_not_set': [
                            item.name for item in data['low_stock'] if item.par_level <= 0
                        ],
                        'expiring_lots': [
                            {
                                'ingredient': x.ingredient.name,
                                'remaining': str(x.remaining_quantity),
                                'expiry': x.expiry_date.isoformat(),
                            }
                            for x in data['expiring_lots']
                        ],
                        'menu_margins': [
                            {
                                'name': x['menu'].name,
                                'cost': str(x['cost']),
                                'price': str(x['menu'].price),
                                'margin_percent': str(x['margin']),
                            }
                            for x in data['menu_costs']
                        ],
                    },
                    ensure_ascii=False,
                ),
            },
        ],
        'temperature': 0.2,
    }
    request = Request(
        os.environ.get('OPENAI_API_URL', 'https://api.openai.com/v1/chat/completions'),
        data=json.dumps(payload).encode('utf-8'),
        headers={'Authorization': f'Bearer {api_key}', 'Content-Type': 'application/json'},
        method='POST',
    )
    try:
        with urlopen(request, timeout=8) as response:
            body = json.loads(response.read().decode('utf-8'))
        content = body['choices'][0]['message']['content'].strip()
        if not content:
            raise ValueError('AI returned an empty response')
        insight = AIInsight.objects.create(
            restaurant=restaurant, content=content, provider='openai'
        )
        # Keep only a small history per restaurant.
        old_ids = list(
            AIInsight.objects.filter(restaurant=restaurant)
            .exclude(pk=insight.pk)
            .values_list('pk', flat=True)[3:]
        )
        AIInsight.objects.filter(pk__in=old_ids).delete()
        return content, 'openai'
    except (URLError, TimeoutError, ValueError, KeyError, IndexError, json.JSONDecodeError):
        return _rules_based_insights(data), 'rules'
