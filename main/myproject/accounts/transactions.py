"""Serialize recipe and ingredient writes within a restaurant."""

from contextlib import contextmanager

from django.db import transaction
from django.db.models import F

from .models import Restaurant


@contextmanager
def restaurant_transaction(restaurant_id):
    """[US-03] A real UPDATE also acquires SQLite's write lock.

    PostgreSQL serializes on this restaurant row. Acquire this lock before
    reading ingredients for a recipe write, unit edit or ingredient deletion.
    The name is unchanged; no stock or inventory revision is touched.
    """
    with transaction.atomic():
        Restaurant.objects.filter(pk=restaurant_id).update(name=F('name'))
        yield
