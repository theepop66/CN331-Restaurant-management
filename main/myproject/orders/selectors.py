"""[US-04][UC-04] Selector layer for Mini-POS querying and availability checks."""

from dataclasses import dataclass
from decimal import Decimal

from django.shortcuts import get_object_or_404

from accounts.models import Restaurant
from menus.models import MenuItem

from .models import Order


@dataclass(frozen=True)
class PosCard:
    menu_id: int
    name: str
    price: Decimal
    is_orderable: bool
    reason: str  # 'ok', 'out_of_stock', 'incomplete', 'inactive'
    max_servings: int


def get_pos_cards(*, restaurant: Restaurant) -> list[PosCard]:
    """[US-04] Fetch all active menu cards for Mini-POS with live stock availability."""
    menu_items = (
        MenuItem.objects.filter(restaurant=restaurant, is_active=True)
        .prefetch_related('recipe_items__ingredient')
        .order_by('name', 'pk')
    )

    cards: list[PosCard] = []

    for menu in menu_items:
        recipe_items = list(menu.recipe_items.all())

        if not recipe_items or menu.price <= 0:
            cards.append(
                PosCard(
                    menu_id=menu.pk,
                    name=menu.name,
                    price=menu.price,
                    is_orderable=False,
                    reason='incomplete',
                    max_servings=0,
                )
            )
            continue

        is_complete = True
        min_servings: int | None = None

        for item in recipe_items:
            ingredient = item.ingredient
            if (
                ingredient is None
                or ingredient.restaurant_id != restaurant.pk
                or ingredient.price <= 0
                or item.quantity_used <= 0
            ):
                is_complete = False
                break

            servings_possible = int(ingredient.stock_quantity // item.quantity_used)
            if min_servings is None or servings_possible < min_servings:
                min_servings = servings_possible

        if not is_complete:
            cards.append(
                PosCard(
                    menu_id=menu.pk,
                    name=menu.name,
                    price=menu.price,
                    is_orderable=False,
                    reason='incomplete',
                    max_servings=0,
                )
            )
            continue

        max_servings = max(0, min_servings if min_servings is not None else 0)
        is_orderable = max_servings > 0
        reason = 'ok' if is_orderable else 'out_of_stock'

        cards.append(
            PosCard(
                menu_id=menu.pk,
                name=menu.name,
                price=menu.price,
                is_orderable=is_orderable,
                reason=reason,
                max_servings=max_servings,
            )
        )

    return cards


def get_order_detail(*, restaurant: Restaurant, order_id: int) -> Order:
    """[US-04] Retrieve single order with tenant-scoped isolation."""
    return get_object_or_404(
        Order.objects.prefetch_related('items__stock_deductions__ingredient', 'items__menu_item'),
        pk=order_id,
        restaurant=restaurant,
    )
