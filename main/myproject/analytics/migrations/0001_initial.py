from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):
    initial = True
    dependencies = [
        ('accounts', '0001_initial'),
    ]
    operations = [
        migrations.CreateModel(
            name='AIInsight',
            fields=[
                ('id', models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('content', models.TextField()),
                ('provider', models.CharField(default='rules', max_length=40)),
                ('generated_at', models.DateTimeField(auto_now_add=True)),
                ('restaurant', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, related_name='ai_insights', to='accounts.restaurant')),
            ],
            options={'ordering': ['-generated_at', '-pk']},
        ),
    ]
