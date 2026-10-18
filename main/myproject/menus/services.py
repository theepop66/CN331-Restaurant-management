"""[US-03][UC-03] Atomic menu writes and the POS/reporting read interface."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db.models import F

from accounts.transactions import restaurant_transaction
from inventory.models import Ingredient

from .models import MenuItem, RecipeItem, normalize_name


class EditConflict(ValidationError):
    def __init__(self):
        super().__init__('ข้อมูลเปลี่ยนไปแล้ว กรุณาเปรียบเทียบข้อมูลและโหลดหน้าใหม่ก่อนบันทึก')


@dataclass(frozen=True)
class RecipeLine:
    ingredient_id: int | None
    name: str
    unit: str
    quantity_used: Decimal
    required_quantity: Decimal
    unit_price: Decimal | None
    cost: Decimal | None


@dataclass(frozen=True)
class MenuSnapshot:
    name: str
    price: Decimal
    revision: int
    is_active: bool
    lines: tuple[RecipeLine, ...]
    is_complete: bool
    cost_per_serving: Decimal | None

    @property
    def is_sellable(self) -> bool:
        return self.is_active and self.is_complete and self.price > 0

    @property
    def exceeds_price(self) -> bool:
        return self.cost_per_serving is not None and self.cost_per_serving > self.price

    @property
    def requirements(self) -> dict[int, Decimal]:
        if not self.is_complete:
            raise ValidationError('สูตรอาหารยังไม่สมบูรณ์')
        return {
            line.ingredient_id: line.required_quantity
            for line in self.lines
            if line.ingredient_id is not None
        }


def read_menu(menu: MenuItem, servings=1, *, require_sellable=False) -> MenuSnapshot:
    """Read one saved recipe. POS must hold restaurant_transaction until checkout.

    The joined SELECT reads ingredients and menu metadata together. Never use a
    caller's prefetched/stale rows to decide sellability. Inactive complete menus
    remain readable for reports; no stock or stock revision is changed here.
    """
    try:
        count = Decimal(str(servings))
    except InvalidOperation:
        raise ValidationError('จำนวนจานต้องเป็นจำนวนบวก') from None
    if not count.is_finite() or count <= 0:
        raise ValidationError('จำนวนจานต้องเป็นจำนวนบวก')
    rows = list(
        RecipeItem.objects.filter(
            menu_item_id=menu.pk,
            menu_item__restaurant_id=menu.restaurant_id,
        ).select_related('ingredient', 'menu_item')
    )
    current = (
        rows[0].menu_item
        if rows
        else MenuItem.objects.get(
            pk=menu.pk,
            restaurant_id=menu.restaurant_id,
        )
    )
    lines = []
    complete = bool(rows)
    total = Decimal('0')
    for row in rows:
        ingredient = row.ingredient
        valid = (
            ingredient is not None
            and ingredient.restaurant_id == current.restaurant_id
            and ingredient.price > 0
            and row.quantity_used > 0
        )
        complete = complete and valid
        cost = row.quantity_used * ingredient.price if valid else None
        if cost is not None:
            total += cost
        lines.append(
            RecipeLine(
                ingredient_id=row.ingredient_id,
                name=ingredient.name if ingredient else row.ingredient_name_snapshot,
                unit=ingredient.get_unit_display() if ingredient else row.ingredient_unit_snapshot,
                quantity_used=row.quantity_used,
                required_quantity=row.quantity_used * count,
                unit_price=ingredient.price if ingredient else None,
                cost=cost,
            )
        )
    snapshot = MenuSnapshot(
        current.name,
        current.price,
        current.revision,
        current.is_active,
        tuple(lines),
        complete,
        total if complete else None,
    )
    if require_sellable and not snapshot.is_sellable:
        raise ValidationError('เมนูนี้ยังไม่พร้อมขายหรือสูตรอาหารไม่สมบูรณ์')
    return snapshot


def _claim_revision(menu, expected_revision):
    if expected_revision is None or not MenuItem.objects.filter(
        pk=menu.pk,
        restaurant_id=menu.restaurant_id,
        revision=expected_revision,
    ).update(revision=F('revision') + 1):
        raise EditConflict()


def update_menu(menu, expected_revision, *, name, price):
    with restaurant_transaction(menu.restaurant_id):
        _claim_revision(menu, expected_revision)
        name = normalize_name(name)
        MenuItem.objects.filter(pk=menu.pk).update(
            name=name,
            normalized_name=name.casefold(),
            price=price,
        )


def replace_recipe(menu, expected_revision, entries, expected_units):
    with restaurant_transaction(menu.restaurant_id):
        _claim_revision(menu, expected_revision)
        ingredients = Ingredient.objects.in_bulk([entry[0] for entry in entries])
        rows = []
        for ingredient_id, quantity in entries:
            ingredient = ingredients.get(ingredient_id)
            if (
                ingredient is None
                or ingredient.restaurant_id != menu.restaurant_id
                or ingredient.price <= 0
                or expected_units.get(str(ingredient_id)) != ingredient.unit
            ):
                raise ValidationError('วัตถุดิบหรือหน่วยนับเปลี่ยนไป กรุณาโหลดหน้าใหม่')
            row = RecipeItem(
                menu_item=menu,
                ingredient=ingredient,
                quantity_used=quantity,
                ingredient_name_snapshot=ingredient.name,
                ingredient_unit_snapshot=ingredient.unit,
            )
            row.full_clean(validate_unique=False, validate_constraints=False)
            rows.append(row)
        if not rows or len({row.ingredient_id for row in rows}) != len(rows):
            raise ValidationError('ต้องมีวัตถุดิบอย่างน้อยหนึ่งรายการและไม่ซ้ำกัน')
        menu.recipe_items.all().delete()
        RecipeItem.objects.bulk_create(rows)


def set_availability(menu, expected_revision, active):
    with restaurant_transaction(menu.restaurant_id):
        _claim_revision(menu, expected_revision)
        if active and not read_menu(menu).is_complete:
            raise ValidationError('ต้องมีสูตรอาหารที่สมบูรณ์ก่อนเปิดขาย')
        MenuItem.objects.filter(pk=menu.pk).update(is_active=active)
