from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0004_merge_ingredient_inventory'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ingredient',
            name='par_level',
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal('0'),
                help_text=(
                    'ใช้หน่วยเดียวกับวัตถุดิบ ระบบจะแจ้งเตือนเมื่อเหลือเท่านี้หรือน้อยกว่า; '
                    'ใส่ 0 หากยังไม่ตั้งจุดเตือน'
                ),
                max_digits=12,
                validators=[MinValueValidator(Decimal('0'))],
                verbose_name='เตือนเมื่อเหลือไม่เกิน',
            ),
        ),
    ]
