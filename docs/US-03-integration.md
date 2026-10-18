# US-03 integration and verification

The owner menu workflow is available at `/menus/`. Create a menu, save its
per-serving recipe, then explicitly open it for sale. Deactivate it to retire it;
menu management never deletes historical menu identities.

## Shared models and consumer interface

`menus.MenuItem` belongs to `accounts.Restaurant`. `menus.RecipeItem` uses
`inventory.Ingredient`, whose current unit price is `price` and whose stock is
`stock_quantity`. Quantities use the ingredient's stored unit with three decimal
places. There is no conversion or stock deduction in US-03.

`menus.services.read_menu(menu, servings=1, require_sellable=False)` reads a fresh
saved recipe and returns a `MenuSnapshot`:

- `lines`: ingredient identity, label/unit, quantity per serving, scaled requirement,
  current unit price and cost per serving for that line.
- `cost_per_serving`: a Decimal or None when the recipe is incomplete.
- `requirements`: ingredient IDs mapped to scaled Decimal quantities; raises
  ValidationError for an incomplete recipe.
- `is_sellable`: explicitly active and complete with a positive menu price.
- `exceeds_price`: a nonblocking current-ingredient-cost warning.
- `revision`: saved menu/recipe/availability revision.

The caller must first fetch the menu through its authenticated restaurant scope.
Reports may read complete inactive menus. POS must pass `require_sellable=True`.
For a sale, hold `accounts.transactions.restaurant_transaction(restaurant.pk)`
around the fresh menu read, stock sufficiency checks and stock writes. This is the
same restaurant write lock used by recipe edits, ingredient unit changes and
ingredient deletion. US-04 owns actual checkout, lot allocation, inventory
revision updates and immutable historical sale/movement records.

The restaurant write lock uses a no-change update of the Restaurant name. This
acquires a write lock on SQLite and a row lock on PostgreSQL, avoiding reliance on
SQLite's unsupported `select_for_update`. Recipes never update ingredient stock,
inventory revisions or stock-lot balances.

Ingredient deletion preserves name/unit labels on missing recipe rows, marks all
affected menus inactive and advances their revisions in the same transaction.
The signal covers model/queryset and enabled administrative deletion paths.
Repairs do not reactivate a menu. A signed unit snapshot prevents an old recipe
form from interpreting newly changed ingredient units as the displayed old unit.

## Database upgrade

Run Django migrations before starting the app. The inventory price migration
checks existing prices first. If any are zero or negative it lists their IDs and
stops, without inventing prices. Correct those records to legitimate positive
unit prices in the previous version, then retry migration. Zero stock is valid.

## Checks

Install `main/requirements-dev.txt` for the local checks. From the repository root:

```powershell
venv\Scripts\python -m mypy --config-file mypy.ini
venv\Scripts\python -m ruff check main/myproject/menus
cd main/myproject
../../venv/Scripts/python manage.py check
../../venv/Scripts/python manage.py makemigrations --check --dry-run
../../venv/Scripts/python -m coverage run --rcfile=../../.coveragerc manage.py test
../../venv/Scripts/python -m coverage report --rcfile=../../.coveragerc
```

The optional real-browser test runs dynamic add/remove controls, saved costs,
activation, duplicate rejection and a 390px mobile layout. Set
`RUN_BROWSER_TESTS=1` and optionally `BROWSER_EXECUTABLE` to an installed
Edge/Chrome executable before running `manage.py test menus.tests.test_browser`.
Otherwise install Playwright Chromium. Normal tests skip this optional check.

The local CI definition performs checks and enforces total coverage above 80%.
It has not been pushed or executed on GitHub as part of this local-only work.

## Traceability

| Local ticket | Implementation | Main behavior tests |
| --- | --- | --- |
| 01 Owner access | accounts decorators, owner home and inventory/admin access | accounts OwnerAccessTests, InventoryAdminAccessTests |
| 02 Positive ingredient prices | Inventory validation, database constraint and migration guard | IngredientPriceTests, PriceMigrationTests |
| 03 Draft menu management | MenuItem, metadata forms and menu views | DraftMenuTests |
| 04 Recipe builder and costs | RecipeItem, formset, atomic writes, read_menu, unit guards and dynamic controls | RecipeBuilderTests, RecipeBrowserTests |
| 05 Ingredient deletion/repair | Ingredient transaction handling, pre-delete signal and missing-row editor | MenuLifecycleTests |
| 06 Availability/POS contract | Availability view and shared sellability/read interface | MenuLifecycleTests |

Each menu view and template carries US-03/UC-03 traceability. The source spec and
numbered tickets remain in the local tracker; no external ticket action is needed.
