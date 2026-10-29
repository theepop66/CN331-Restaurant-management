"""[US-04][UC-04] Views for Mini-POS sales, live out-of-stock guard, and checkout."""

import json

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.http import HttpResponseNotAllowed
from django.shortcuts import redirect, render

from accounts.decorators import restaurant_owner_required

from .selectors import get_order_detail, get_pos_cards
from .services import CartLine, StockInsufficient, checkout_order


@restaurant_owner_required
def pos_view(request, restaurant):
    """[US-04][UC-04] Render Mini-POS sales screen with live stock availability."""
    cards = get_pos_cards(restaurant=restaurant)
    return render(
        request,
        'orders/pos.html',
        {
            'cards': cards,
            'restaurant': restaurant,
        },
    )


@restaurant_owner_required
def checkout_view(request, restaurant):
    """[US-04][UC-04] Handle POS order checkout with atomic stock deduction."""
    if request.method != 'POST':
        return HttpResponseNotAllowed(['POST'])

    lines: list[CartLine] = []

    # Support cart payload via JSON hidden input or raw form data
    raw_cart = request.POST.get('cart_data', '').strip()
    if raw_cart:
        try:
            parsed = json.loads(raw_cart)
            if isinstance(parsed, list):
                for item in parsed:
                    menu_id = int(item.get('menu_id', 0))
                    qty = int(item.get('quantity', 0))
                    if menu_id > 0 and qty > 0:
                        lines.append(CartLine(menu_item_id=menu_id, quantity=qty))
        except (ValueError, TypeError):
            messages.error(request, 'รูปแบบข้อมูลตะกร้าสินค้าไม่ถูกต้อง')
            return redirect('orders:pos')
    else:
        # Fallback to direct menu_id and quantity fields
        menu_id = request.POST.get('menu_id')
        quantity = request.POST.get('quantity', '1')
        try:
            if menu_id:
                lines.append(CartLine(menu_item_id=int(menu_id), quantity=int(quantity)))
        except (ValueError, TypeError):
            pass

    if not lines:
        messages.error(request, 'กรุณาเลือกรายการอาหารก่อนยืนยันการขาย')
        return redirect('orders:pos')

    try:
        order = checkout_order(
            restaurant=restaurant,
            user=request.user,
            lines=lines,
        )
        messages.success(request, f'บันทึกคำสั่งซื้อ #{order.pk} สำเร็จ')
        return redirect('orders:success', pk=order.pk)
    except StockInsufficient as exc:
        messages.error(request, f'ไม่สามารถขายได้: {exc}')
        return redirect('orders:pos')
    except ValidationError as exc:
        msg = exc.messages[0] if hasattr(exc, 'messages') else str(exc)
        messages.error(request, f'เกิดข้อผิดพลาด: {msg}')
        return redirect('orders:pos')


@restaurant_owner_required
def order_success_view(request, restaurant, pk):
    """[US-04][UC-04] Display order receipt and confirmation."""
    order = get_order_detail(restaurant=restaurant, order_id=pk)
    return render(
        request,
        'orders/order_success.html',
        {
            'order': order,
            'restaurant': restaurant,
        },
    )
