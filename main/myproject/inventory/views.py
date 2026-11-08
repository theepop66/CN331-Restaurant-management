"""[UC-02] Inventory HTTP layer: parse request, call services/selectors, render."""

from urllib.parse import urlencode

from django.contrib import messages
from django.core.exceptions import ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from accounts.decorators import restaurant_owner_required as restaurant_required
from accounts.models import CustomUser

from . import selectors, services
from .forms import IngredientForm, ScanForm, StockInForm
from .models import Ingredient

PAGE_SIZE = 20


def _safe_next(request, default):
    target = request.POST.get('next') or request.GET.get('next')
    if target and url_has_allowed_host_and_scheme(
        target,
        allowed_hosts={request.get_host()},
        require_https=request.is_secure(),
    ):
        return target
    return default


@restaurant_required
def ingredient_list(request, restaurant):
    """[UC-02] รายการวัตถุดิบของร้าน + ค้นหา + สแกน + รับเข้าในแถว."""
    q = request.GET.get('q', '').strip()
    qs = selectors.search_ingredients(restaurant=restaurant, query=q)

    page = Paginator(qs, PAGE_SIZE).get_page(request.GET.get('page'))
    selectors.annotate_expiry_state(page)

    scan_form = ScanForm(
        initial={
            'quick_mode': request.session.get('quick_scan', False),
        }
    )
    not_found = request.GET.get('not_found', '').strip()
    return render(
        request,
        'inventory/list.html',
        {
            'page': page,
            'stats': selectors.inventory_stats(restaurant=restaurant),
            'q': q,
            'scan_form': scan_form,
            'not_found': not_found,
            'not_found_query': urlencode({'barcode': not_found}),
            'expiring_days': selectors.EXPIRING_SOON_DAYS,
        },
    )


@restaurant_required
def ingredient_create(request, restaurant):
    """[UC-02] เพิ่มวัตถุดิบ (ถ้ามีปริมาณเริ่มต้น จะสร้างล็อตแรกให้)."""
    if request.method == 'POST':
        form = IngredientForm(request.POST, restaurant=restaurant)
        if form.is_valid():
            ingredient = services.create_ingredient(
                restaurant=restaurant,
                ingredient=form.save(commit=False),
                user=request.user,
                expiry_date=form.cleaned_data.get('expiry_date'),
            )
            messages.success(request, f'✅ เพิ่มวัตถุดิบ "{ingredient.name}" เรียบร้อยแล้ว')
            return redirect('inventory:detail', pk=ingredient.pk)
    else:
        form = IngredientForm(
            restaurant=restaurant,
            initial={'barcode': request.GET.get('barcode', '').strip()},
        )
    return render(
        request,
        'inventory/form.html',
        {
            'form': form,
            'title': 'เพิ่มวัตถุดิบ',
            'names': selectors.ingredient_names(restaurant=restaurant),
        },
    )


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
    return render(
        request,
        'inventory/form.html',
        {
            'form': form,
            'title': f'แก้ไข: {ingredient.name}',
            'ingredient': ingredient,
            'names': selectors.ingredient_names(restaurant=restaurant),
        },
    )


@restaurant_required
def ingredient_detail(request, restaurant, pk):
    """[UC-02] รายละเอียดวัตถุดิบ + ล็อตที่รับเข้า + ฟอร์มรับเข้า."""
    ingredient = get_object_or_404(Ingredient, pk=pk, restaurant=restaurant)
    return render(
        request,
        'inventory/detail.html',
        {
            'ingredient': ingredient,
            'lots': selectors.get_ingredient_lots(ingredient=ingredient),
            'stock_in_form': StockInForm(),
            'can_delete': request.user.role == CustomUser.Role.OWNER,
        },
    )


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
    return render(
        request,
        'inventory/confirm_delete.html',
        {
            'ingredient': ingredient,
            'lot_count': ingredient.stock_ins.count(),
        },
    )


@require_POST
@restaurant_required
def stock_in(request, restaurant, pk):
    """[UC-02] รับเข้าสต็อก: บวกเพิ่มจากยอดเดิม + สร้างล็อต."""
    ingredient = get_object_or_404(Ingredient, pk=pk, restaurant=restaurant)
    back = _safe_next(request, reverse('inventory:detail', args=[ingredient.pk]))
    form = StockInForm(request.POST)
    if form.is_valid():
        try:
            ingredient, old, new, lot = services.add_stock(
                restaurant,
                ingredient.pk,
                form.cleaned_data['quantity'],
                request.user,
                form.cleaned_data.get('expiry_date'),
            )
        except ValidationError as error:
            for text in error.messages:
                messages.error(request, f'{ingredient.name}: {text}')
        else:
            summary = services.stock_message(ingredient, old, new)
            messages.success(request, f'📥 รับเข้า {summary} (ล็อต {lot.lot_code})')
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

    ingredient = selectors.find_by_barcode(restaurant=restaurant, barcode=barcode)
    if ingredient is None:
        return redirect(f"{reverse('inventory:list')}?{urlencode({'not_found': barcode})}")

    if quick:
        try:
            ingredient, old, new, lot = services.add_stock(
                restaurant,
                ingredient.pk,
                services.QUICK_SCAN_STEP,
                request.user,
            )
        except ValidationError as error:
            for text in error.messages:
                messages.error(request, f'{ingredient.name}: {text}')
        else:
            messages.success(request, f'➕ {services.stock_message(ingredient, old, new)}')
        return redirect('inventory:list')

    return redirect(f"{reverse('inventory:detail', args=[ingredient.pk])}#stock-in")
