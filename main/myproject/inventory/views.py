from datetime import timedelta
from decimal import Decimal
from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.db import transaction
from django.db.models import F, Min, Q
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import restaurant_owner_required as restaurant_required
from accounts.models import CustomUser

from .forms import IngredientForm, ScanForm, StockInForm
from .models import Ingredient, StockIn

PAGE_SIZE = 20
QUICK_SCAN_STEP = Decimal('1')  # โหมดสแกนรัว: บวกครั้งละ 1 ตายตัว (ไม่ต้องให้ผู้ใช้เลือก)
EXPIRING_SOON_DAYS = 7


def _fmt(value):
    """แสดงทศนิยมแบบสั้น เช่น Decimal('5.000') -> '5'"""
    return format(Decimal(value).normalize(), 'f')


def _safe_next(request, default):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
        target, allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return default


def _add_stock(restaurant, ingredient_id, quantity, user, expiry_date=None):
    """
    บวกสต็อกและสร้างล็อต (StockIn) ในธุรกรรมเดียว
    คืนค่า (ingredient, ยอดเดิม, ยอดใหม่, ล็อต)
    """
    field = Ingredient._meta.get_field('stock_quantity')
    maximum = (
        Decimal(10) ** (field.max_digits - field.decimal_places)
        - Decimal(1).scaleb(-field.decimal_places)
    )
    with transaction.atomic():
        # Check and increment together; SQLite does not support row locks.
        updated = Ingredient.objects.filter(
            pk=ingredient_id, restaurant=restaurant,
            stock_quantity__lte=maximum - quantity,
        ).update(
            stock_quantity=F('stock_quantity') + quantity,
            revision=F('revision') + 1, updated_at=timezone.now(),
        )
        ingredient = Ingredient.objects.get(
            pk=ingredient_id, restaurant=restaurant,
        )
        if not updated:
            raise ValidationError(
                f'ปริมาณคงเหลือรวมต้องไม่เกิน {_fmt(maximum)}'
            )
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


def _stock_message(ingredient, old, new):
    return (
        f'{ingredient.name}: {_fmt(old)} → {_fmt(new)} '
        f'{ingredient.get_unit_display()}'
    )


@restaurant_required
def ingredient_list(request, restaurant):
    """[UC-02] รายการวัตถุดิบของร้าน + ค้นหา + สแกน + รับเข้าในแถว."""
    base = (
        Ingredient.objects.filter(restaurant=restaurant)
        .annotate(
            nearest_expiry=Min(
                'stock_ins__expiry_date',
                filter=Q(stock_ins__remaining_quantity__gt=0),
            )
        )
        .order_by('name', 'pk')
    )
    qs = base
    q = request.GET.get('q', '').strip()
    if q:
        qs = qs.filter(Q(name__icontains=q) | Q(barcode__icontains=q))

    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page'))
    today = timezone.localdate()
    soon = today + timedelta(days=EXPIRING_SOON_DAYS)
    for item in page:
        expiry = item.nearest_expiry
        item.expiry_state = (
            'expired' if expiry and expiry < today
            else 'soon' if expiry and expiry <= soon
            else ''
        )

    stats = {'total': 0, 'out': 0, 'soon': 0, 'expired': 0}
    for stock, expiry in base.values_list('stock_quantity', 'nearest_expiry'):
        stats['total'] += 1
        stats['out'] += stock <= 0
        if expiry and expiry < today:
            stats['expired'] += 1
        elif expiry and expiry <= soon:
            stats['soon'] += 1

    scan_form = ScanForm(initial={
        'quick_mode': request.session.get('quick_scan', False),
    })
    not_found = request.GET.get('not_found', '').strip()
    return render(request, 'inventory/list.html', {
        'page': page,
        'stats': stats,
        'q': q,
        'scan_form': scan_form,
        'not_found': not_found,
        'not_found_query': urlencode({'barcode': not_found}),
        'expiring_days': EXPIRING_SOON_DAYS,
    })


@restaurant_required
def ingredient_create(request, restaurant):
    """[UC-02] เพิ่มวัตถุดิบ (ถ้ามีปริมาณเริ่มต้น จะสร้างล็อตแรกให้)."""
    if request.method == 'POST':
        form = IngredientForm(request.POST, restaurant=restaurant)
        if form.is_valid():
            with transaction.atomic():
                ingredient = form.save(commit=False)
                ingredient.restaurant = restaurant
                initial_qty = ingredient.stock_quantity
                ingredient.save()
                if initial_qty > 0:
                    StockIn.objects.create(
                        restaurant=restaurant,
                        ingredient=ingredient,
                        quantity=initial_qty,
                        remaining_quantity=initial_qty,
                        expiry_date=form.cleaned_data.get('expiry_date'),
                        received_by=request.user,
                    )
            messages.success(request, f'✅ เพิ่มวัตถุดิบ "{ingredient.name}" เรียบร้อยแล้ว')
            return redirect('inventory:detail', pk=ingredient.pk)
    else:
        form = IngredientForm(
            restaurant=restaurant,
            initial={'barcode': request.GET.get('barcode', '').strip()},
        )
    return render(request, 'inventory/form.html', {
        'form': form,
        'title': 'เพิ่มวัตถุดิบ',
        'names': _names(restaurant),
    })


@restaurant_required
def ingredient_update(request, restaurant, pk):
    """[UC-02] แก้ไขวัตถุดิบ (แก้ยอดสต็อกตรงนี้ = ปรับยอด ไม่นับเป็นรับเข้า)."""
    ingredient = get_object_or_404(Ingredient, pk=pk, restaurant=restaurant)
    if request.method == 'POST':
        form = IngredientForm(request.POST, instance=ingredient, restaurant=restaurant)
        if form.is_valid():
            try:
                saved = ingredient.save_if_current(form.cleaned_data['expected_revision'])
            except ValidationError as error:
                form.add_error(None, error.messages)
            else:
                if saved:
                    messages.success(request, f'✅ บันทึกการแก้ไข "{ingredient.name}" แล้ว')
                    return redirect('inventory:detail', pk=ingredient.pk)
                form.add_error(
                    None,
                    'วัตถุดิบนี้มีการเปลี่ยนแปลงแล้ว กรุณาโหลดหน้าใหม่ก่อนบันทึก',
                )
    else:
        form = IngredientForm(instance=ingredient, restaurant=restaurant)
    return render(request, 'inventory/form.html', {
        'form': form,
        'title': f'แก้ไข: {ingredient.name}',
        'ingredient': ingredient,
        'names': _names(restaurant),
    })


@restaurant_required
def ingredient_detail(request, restaurant, pk):
    """[UC-02] รายละเอียดวัตถุดิบ + ล็อตที่รับเข้า + ฟอร์มรับเข้า."""
    ingredient = get_object_or_404(Ingredient, pk=pk, restaurant=restaurant)
    today = timezone.localdate()
    soon = today + timedelta(days=EXPIRING_SOON_DAYS)
    lots = list(ingredient.stock_ins.select_related('received_by'))
    for lot in lots:
        lot.expiry_state = (
            'expired' if lot.expiry_date and lot.expiry_date < today
            else 'soon' if lot.expiry_date and lot.expiry_date <= soon
            else ''
        )
    return render(request, 'inventory/detail.html', {
        'ingredient': ingredient,
        'lots': lots,
        'stock_in_form': StockInForm(),
        'can_delete': request.user.role == CustomUser.Role.OWNER,
    })


@restaurant_required
def ingredient_delete(request, restaurant, pk):
    """[UC-02] ลบวัตถุดิบ (เฉพาะเจ้าของร้าน) พร้อมหน้ายืนยัน."""
    ingredient = get_object_or_404(Ingredient, pk=pk, restaurant=restaurant)
    if request.user.role != CustomUser.Role.OWNER:
        messages.error(request, 'เฉพาะเจ้าของร้านเท่านั้นที่ลบวัตถุดิบได้')
        return redirect('inventory:detail', pk=ingredient.pk)

    if request.method == 'POST':
        name = ingredient.name
        ingredient.delete()
        messages.success(request, f'🗑️ ลบวัตถุดิบ "{name}" แล้ว')
        return redirect('inventory:list')
    return render(request, 'inventory/confirm_delete.html', {
        'ingredient': ingredient,
        'lot_count': ingredient.stock_ins.count(),
    })


@require_POST
@restaurant_required
def stock_in(request, restaurant, pk):
    """[UC-02] รับเข้าสต็อก: บวกเพิ่มจากยอดเดิม + สร้างล็อต."""
    ingredient = get_object_or_404(Ingredient, pk=pk, restaurant=restaurant)
    back = _safe_next(request, reverse('inventory:detail', args=[ingredient.pk]))
    form = StockInForm(request.POST)
    if form.is_valid():
        try:
            ingredient, old, new, lot = _add_stock(
                restaurant, ingredient.pk, form.cleaned_data['quantity'],
                request.user, form.cleaned_data.get('expiry_date'),
            )
        except ValidationError as error:
            for text in error.messages:
                messages.error(request, f'{ingredient.name}: {text}')
        else:
            messages.success(
                request,
                f'📥 รับเข้า {_stock_message(ingredient, old, new)} (ล็อต {lot.lot_code})',
            )
    else:
        for errors in form.errors.values():
            for error_text in errors:
                messages.error(request, f'{ingredient.name}: {error_text}')
    return redirect(back)


@require_POST
@restaurant_required
def scan(request, restaurant):
    """
    [UC-02] สแกน/พิมพ์บาร์โค้ด.

    - เจอ + โหมดสแกนรัว: บวกสต็อกทันทีครั้งละ 1 (QUICK_SCAN_STEP)
    - เจอ + โหมดปกติ: ไปหน้ารายละเอียดเพื่อกรอกจำนวนรับเข้า
    - ไม่เจอ: กลับหน้ารายการพร้อมปุ่ม "เพิ่มวัตถุดิบใหม่ด้วยบาร์โค้ดนี้"
    """
    form = ScanForm(request.POST)
    request.session['quick_scan'] = bool(request.POST.get('quick_mode'))
    if not form.is_valid():
        for errors in form.errors.values():
            for error in errors:
                messages.error(request, error)
        return redirect('inventory:list')

    barcode = form.cleaned_data['barcode']
    quick = form.cleaned_data['quick_mode']

    ingredient = Ingredient.objects.filter(
        restaurant=restaurant, barcode=barcode,
    ).first()
    if ingredient is None:
        return redirect(f"{reverse('inventory:list')}?{urlencode({'not_found': barcode})}")

    if quick:
        try:
            ingredient, old, new, lot = _add_stock(
                restaurant, ingredient.pk, QUICK_SCAN_STEP, request.user,
            )
        except ValidationError as error:
            for text in error.messages:
                messages.error(request, f'{ingredient.name}: {text}')
        else:
            messages.success(request, f'➕ {_stock_message(ingredient, old, new)}')
        return redirect('inventory:list')

    return redirect(f"{reverse('inventory:detail', args=[ingredient.pk])}#stock-in")


def _names(restaurant):
    return Ingredient.objects.filter(restaurant=restaurant).values_list('name', flat=True)
