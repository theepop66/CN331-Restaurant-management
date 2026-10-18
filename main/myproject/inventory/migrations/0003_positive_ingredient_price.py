"""[US-03] Require real positive prices without inventing legacy costs."""

from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


def require_valid_prices(apps, schema_editor):
    ingredient = apps.get_model('inventory', 'Ingredient')
    invalid_ids = list(ingredient.objects.using(
        schema_editor.connection.alias,
    ).filter(price__lte=0).values_list('pk', flat=True)[:20])
    if invalid_ids:
        raise RuntimeError(
            'Correct ingredient unit prices before migrating; '
            f'nonpositive prices on ingredient IDs: {invalid_ids}. '
            'No replacement prices have been invented.',
        )


class Migration(migrations.Migration):
    dependencies = [('inventory', '0002_ingredient_revision')]

    operations = [
        migrations.RunPython(require_valid_prices, migrations.RunPython.noop),
        migrations.AlterField(
            model_name='ingredient', name='price',
            field=models.DecimalField(
                'ราคาต่อหน่วย', max_digits=10, decimal_places=2,
                validators=[MinValueValidator(Decimal('0.01'))],
            ),
        ),
        migrations.AddConstraint(
            model_name='ingredient',
            constraint=models.CheckConstraint(
                condition=models.Q(price__gt=0),
                name='ingredient_price_positive',
            ),
        ),
    ]
