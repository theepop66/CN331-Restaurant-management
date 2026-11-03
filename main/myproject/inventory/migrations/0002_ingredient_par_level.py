from decimal import Decimal

from django.core.validators import MinValueValidator
from django.db import migrations, models


class Migration(migrations.Migration):
    dependencies = [
        ('inventory', '0001_initial'),
    ]

    operations = [
        migrations.AddField(
            model_name='ingredient',
            name='par_level',
            field=models.DecimalField(
                decimal_places=3,
                default=Decimal('0'),
                help_text='แจ้งเตือนเมื่อคงเหลือถึงหรือต่ำกว่าค่านี้; 0 คือยังไม่กำหนด',
                max_digits=12,
                validators=[MinValueValidator(Decimal('0'))],
                verbose_name='จุดแจ้งเตือนสั่งซื้อซ้ำ',
            ),
        ),
    ]
