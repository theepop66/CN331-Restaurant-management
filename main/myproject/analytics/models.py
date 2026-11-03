from django.conf import settings
from django.db import models


class AIInsight(models.Model):
    """Restaurant-scoped record of an AI or rules-based analytics summary."""

    restaurant = models.ForeignKey(
        'accounts.Restaurant', on_delete=models.CASCADE, related_name='ai_insights'
    )
    content = models.TextField()
    provider = models.CharField(max_length=40, default='rules')
    generated_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-generated_at', '-pk']

    def __str__(self):
        return f'{self.restaurant}: {self.provider} insight ({self.generated_at:%Y-%m-%d})'
