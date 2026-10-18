"""[US-03] Refuse invented prices when upgrading existing inventory."""

from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase


class PriceMigrationTests(TransactionTestCase):
    def test_legacy_zero_price_requires_owner_correction_before_upgrade(self):
        executor = MigrationExecutor(connection)
        legacy_target = [('inventory', '0002_ingredient_revision')]
        executor.migrate(legacy_target)
        apps = executor.loader.project_state(legacy_target).apps
        restaurant = apps.get_model('accounts', 'Restaurant').objects.create(name='Legacy')
        ingredient = apps.get_model('inventory', 'Ingredient').objects.create(
            restaurant=restaurant,
            name='Legacy rice',
            unit='kg',
            price=0,
        )
        try:
            executor = MigrationExecutor(connection)
            with self.assertRaisesMessage(RuntimeError, 'Correct ingredient unit prices'):
                executor.migrate([('inventory', '0003_positive_ingredient_price')])
            self.assertEqual(apps.get_model('inventory', 'Ingredient').objects.get().price, 0)
        finally:
            apps.get_model('inventory', 'Ingredient').objects.filter(pk=ingredient.pk).update(
                price=40
            )
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())
