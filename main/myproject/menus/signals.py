"""Deletion safety applies to model, queryset, cascade and enabled admin paths."""

from django.db.models import F
from django.db.models.signals import pre_delete
from django.dispatch import receiver

from accounts.transactions import restaurant_transaction
from inventory.models import Ingredient

from .models import MenuItem, RecipeItem


@receiver(pre_delete, sender=Ingredient, dispatch_uid='menus.ingredient_deleted')
def preserve_missing_ingredient(sender, instance, using, **kwargs):
    """[US-03][UC-03] Keep labels and deactivate all affected menus atomically."""
    with restaurant_transaction(instance.restaurant_id):
        rows = RecipeItem.objects.using(using).filter(ingredient_id=instance.pk)
        menu_ids = list(rows.values_list('menu_item_id', flat=True))
        rows.update(
            ingredient_name_snapshot=instance.name,
            ingredient_unit_snapshot=instance.unit,
        )
        MenuItem.objects.using(using).filter(pk__in=menu_ids).update(
            is_active=False,
            revision=F('revision') + 1,
        )
