"""[US-04][UC-04] Service layer for Mini-POS checkout and atomic stock deduction."""

from dataclasses import dataclass
from decimal import Decimal
from typing import Sequence

from django.core.exceptions import ValidationError
from django.db.models import F

from accounts.models import Restaurant
from accounts.transactions import restaurant_transaction
from inventory.models import Ingredient, StockIn
from menus.models import MenuItem
from menus.services import read_menu

from .models import Order, OrderItem, StockDeduction


@dataclass(frozen=True)
class CartLine:
    menu_item_id: int
    quantity: int


class StockInsufficient(ValidationError):
    """Raised when one or more ingredients have insufficient stock."""

    def __init__(self, shortages: dict[int, Decimal] | None = None, message: str = ''):
        self.shortages = shortages or {}
        if not message:
            message = 'วัตถุดิบคงเหลือไม่เพียงพอสำหรับการสั่งซื้อ'
        super().__init__(message)


def checkout_order(
    *,
    restaurant: Restaurant,
    user,
    lines: Sequence[CartLine],
) -> Order:
    """[US-04] Process an order checkout atomically with FEFO stock deduction.

    - Validates cart input and tenant isolation.
    - Aggregates ingredients across all ordered items.
    - Verifies sufficient stock; raises StockInsufficient if any item falls short.
    - Deducts ingredient stock atomically via conditional F() update.
    - Allocates deductions from StockIn lots by FEFO (earliest expiry first).
    - Creates Order, OrderItem, and StockDeduction records.
    """
    if not lines:
        raise ValidationError('ตะกร้าสินค้าว่างเปล่า กรุณาเลือกรายการอาหาร')

    for line in lines:
        if not isinstance(line.quantity, int) or line.quantity <= 0:
            raise ValidationError('จำนวนสั่งซื้อต้องเป็นจำนวนเต็มบวก')

    menu_ids = [line.menu_item_id for line in lines]
    menus_by_id = MenuItem.objects.in_bulk(menu_ids)

    # Validate that all items exist and belong to the same restaurant
    for menu_id in menu_ids:
        menu = menus_by_id.get(menu_id)
        if menu is None or menu.restaurant_id != restaurant.pk:
            raise ValidationError('พบเมนูอาหารที่ไม่ถูกต้องหรือต่างร้าน')

    with restaurant_transaction(restaurant.pk):
        # Read recipes and aggregate ingredient requirements
        total_needed_by_ing: dict[int, Decimal] = {}
        line_requirements: list[tuple[CartLine, MenuItem, dict[int, Decimal]]] = []

        for line in lines:
            menu = menus_by_id[line.menu_item_id]
            snapshot = read_menu(menu, servings=line.quantity, require_sellable=True)
            reqs = snapshot.requirements  # dict[ingredient_id, Decimal]
            line_requirements.append((line, menu, reqs))

            for ing_id, needed_qty in reqs.items():
                total_needed_by_ing[ing_id] = total_needed_by_ing.get(ing_id, Decimal('0')) + needed_qty

        # Verify all ingredients exist and belong to the restaurant
        ingredients_by_id = Ingredient.objects.in_bulk(list(total_needed_by_ing.keys()))
        shortages: dict[int, Decimal] = {}

        for ing_id, total_needed in total_needed_by_ing.items():
            ingredient = ingredients_by_id.get(ing_id)
            if ingredient is None or ingredient.restaurant_id != restaurant.pk:
                raise ValidationError('พบวัตถุดิบที่ไม่ถูกต้องหรือต่างร้าน')
            if ingredient.stock_quantity < total_needed:
                shortages[ing_id] = total_needed - ingredient.stock_quantity

        if shortages:
            raise StockInsufficient(shortages=shortages)

        # Atomic stock deduction on Ingredient (conditional UPDATE to guard against race condition)
        for ing_id, total_needed in total_needed_by_ing.items():
            rows_updated = Ingredient.objects.filter(
                pk=ing_id,
                restaurant_id=restaurant.pk,
                stock_quantity__gte=total_needed,
            ).update(stock_quantity=F('stock_quantity') - total_needed)

            if rows_updated == 0:
                raise StockInsufficient(shortages={ing_id: total_needed})

        # Calculate order total
        total_amount = sum(
            (menu.price * line.quantity for line, menu, _ in line_requirements),
            start=Decimal('0.00'),
        )

        order = Order.objects.create(
            restaurant=restaurant,
            created_by=user if getattr(user, 'is_authenticated', False) else None,
            total_amount=total_amount,
            status=Order.Status.COMPLETED,
        )

        # Create OrderItems and allocate FEFO lots for StockDeduction
        # Pre-fetch available lots for required ingredients:
        lots_by_ing: dict[int, list[StockIn]] = {}
        for ing_id in total_needed_by_ing:
            lots = list(
                StockIn.objects.filter(
                    restaurant_id=restaurant.pk,
                    ingredient_id=ing_id,
                    remaining_quantity__gt=0,
                ).order_by(
                    F('expiry_date').asc(nulls_last=True),
                    'received_at',
                    'id',
                )
            )
            lots_by_ing[ing_id] = lots

        for line, menu, reqs in line_requirements:
            line_total = menu.price * line.quantity
            order_item = OrderItem.objects.create(
                order=order,
                menu_item=menu,
                name_snapshot=menu.name,
                unit_price=menu.price,
                quantity=line.quantity,
                line_total=line_total,
            )

            # Deduct from lots for each ingredient in this order item
            for ing_id, needed_for_item in reqs.items():
                ingredient = ingredients_by_id[ing_id]
                remaining_to_deduct = needed_for_item
                available_lots = lots_by_ing.get(ing_id, [])

                while remaining_to_deduct > 0 and available_lots:
                    current_lot = available_lots[0]
                    deduct_qty = min(remaining_to_deduct, current_lot.remaining_quantity)

                    StockIn.objects.filter(pk=current_lot.pk).update(
                        remaining_quantity=F('remaining_quantity') - deduct_qty,
                    )
                    current_lot.remaining_quantity -= deduct_qty

                    StockDeduction.objects.create(
                        order_item=order_item,
                        ingredient=ingredient,
                        lot=current_lot,
                        quantity=deduct_qty,
                    )

                    remaining_to_deduct -= deduct_qty
                    if current_lot.remaining_quantity <= 0:
                        available_lots.pop(0)

                # If no lot left (e.g. legacy stock without lot), record deduction with lot=None
                if remaining_to_deduct > 0:
                    StockDeduction.objects.create(
                        order_item=order_item,
                        ingredient=ingredient,
                        lot=None,
                        quantity=remaining_to_deduct,
                    )

        return order
