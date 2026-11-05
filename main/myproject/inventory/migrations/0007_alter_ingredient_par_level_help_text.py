from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0006_alter_ingredient_par_level_help_text'),
    ]

    operations = [
        migrations.AlterField(
            model_name='ingredient',
            name='par_level',
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal('0'),
                help_text=(
                    'ระบบจะแจ้งเตือนเมื่อของเหลือถึงจำนวนนี้หรือน้อยกว่า '
                    '(ใส่ 0 เพื่อปิดการแจ้งเตือน)'
                ),
                max_digits=12,
                validators=[MinValueValidator(Decimal('0'))],
                verbose_name='เตือนเมื่อเหลือไม่เกิน',
            ),
        ),
    ]
