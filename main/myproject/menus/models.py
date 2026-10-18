"""[US-03][UC-03] Menu lifecycle and per-serving bill of materials."""

from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator
from django.db import models


def normalize_name(name):
    return ' '.join(name.split())


class MenuItem(models.Model):
    restaurant = models.ForeignKey('accounts.Restaurant', on_delete=models.CASCADE)
    name = models.CharField('ชื่อเมนู', max_length=150)
    normalized_name = models.CharField(max_length=300, editable=False)
    price = models.DecimalField(
        'ราคาขาย (บาท)',
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
    )
    is_active = models.BooleanField('พร้อมขาย', default=False)
    revision = models.PositiveBigIntegerField(default=0, editable=False)

    class Meta:
        ordering = ['name', 'pk']
        constraints = [
            models.CheckConstraint(condition=models.Q(price__gt=0), name='menu_price_positive'),
            models.UniqueConstraint(
                fields=['restaurant', 'normalized_name'],
                name='menu_name_per_restaurant',
            ),
        ]

    def clean(self):
        self.name = normalize_name(self.name)
        self.normalized_name = self.name.casefold()
        if not self.name:
            raise ValidationError({'name': 'กรุณากรอกชื่อเมนู'})

    def save(self, *args, **kwargs):
        self.clean()
        if kwargs.get('update_fields') and 'name' in kwargs['update_fields']:
            kwargs['update_fields'] = set(kwargs['update_fields']) | {'normalized_name'}
        super().save(*args, **kwargs)

    def __str__(self):
        return self.name


class RecipeItem(models.Model):
    menu_item = models.ForeignKey(MenuItem, on_delete=models.CASCADE, related_name='recipe_items')
    ingredient = models.ForeignKey(
        'inventory.Ingredient',
        on_delete=models.SET_NULL,
        null=True,
        related_name='recipe_items',
    )
    quantity_used = models.DecimalField(
        'ปริมาณต่อจาน',
        max_digits=12,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
    )
    ingredient_name_snapshot = models.CharField(max_length=150)
    ingredient_unit_snapshot = models.CharField(max_length=10)

    class Meta:
        ordering = ['pk']
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_used__gt=0),
                name='recipe_quantity_positive',
            ),
            models.UniqueConstraint(
                fields=['menu_item', 'ingredient'],
                name='recipe_ingredient_once',
            ),
        ]

    def clean(self):
        if self.ingredient_id:
            if self.ingredient.restaurant_id != self.menu_item.restaurant_id:
                raise ValidationError({'ingredient': 'วัตถุดิบต้องเป็นของร้านเดียวกับเมนู'})
            self.ingredient_name_snapshot = self.ingredient.name
            self.ingredient_unit_snapshot = self.ingredient.unit

    def save(self, *args, **kwargs):
        self.clean()
        self.full_clean()
        super().save(*args, **kwargs)
