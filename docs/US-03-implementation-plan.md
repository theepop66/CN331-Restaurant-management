# US-03: Menu Management and Recipe / BOM Builder

Status: implemented and reviewed locally. All six canonical tickets under
.scratch/us-03/ are complete. Final suite: 94 tests, one optional browser test
skipped in that run and passed separately, 93.56% coverage. See US-03-integration.md
for consumer contracts and US-03-review.md for the independent review results.
Previously generated GitHub issues 9-15 were closed at the user's explicit
request; parent issue 4 remains open and unchanged. Implementation made no
external tracker changes and was not pushed.

Source: the project checklist supplied by the user, mapping US-03 to UC-03.
The acceptance criteria below combine that checklist with the user's answers
to grilling questions Q1-Q14. Technical mechanisms remain implementation proposals.

Integration baseline verified from fetched origin/main at 28d80ad: US-01 was
merged in PR #7 and US-02 in PR #8. The current local US-03 branch is named
origin/feature/us-03 and is still at 0398dcf, six commits behind origin/main.
This plan reads those merged models without changing the checked-out code.

## 1. Outcome and scope

A restaurant owner creates a menu item, assigns ingredient quantities per serving,
edits the recipe, and sees its current estimated ingredient cost. The recipe is
available to US-04 for stock deduction and US-06 for cost reporting.

Required core: MenuItem, RecipeItem, menu_create, recipe_builder_view,
menu_form.html, recipe_builder.html, Bootstrap 5, restaurant isolation, tests,
and US-03 / UC-03 traceability.

Agreed supporting features: menu list/editing, current-cost preview, explicit
availability control, missing-ingredient indicators, and stale-edit protection.

## Agreed product decisions (Q1-Q14)

| Decision | Agreed behavior |
| --- | --- |
| Q1: Drafts | A menu can be saved before its recipe is complete; it cannot be sold. |
| Q2: Access | The whole platform is owner-only, including POS. Existing staff roles do not grant access under the agreed product scope. Coordinate platform-wide enforcement with the other feature owners. |
| Q3: Units | Enter quantities in the ingredient's stored unit, with three decimal places; no conversion UI. |
| Q4: Cost | Show line costs and total cost using current ingredient prices; historical reporting remains a separate integration concern. |
| Q5: Removal | Retire a menu by making it inactive; keep its record for sales references. |
| Q6: Activation | New menus start inactive; an owner explicitly activates one only after its recipe is valid. |
| Q7: Unit edits | Block ingredient unit changes while any recipe references it. |
| Q8: Ingredient deletion | Deleting an ingredient makes every affected menu inactive. |
| Q9: Prices | Both menu selling prices and ingredient unit prices must be strictly positive. |
| Q10: Names | Reject duplicate menu names per restaurant, ignoring capitalization and extra spaces. |
| Q11: Missing ingredient | Keep a visible deleted-ingredient row; cost is incomplete and activation is blocked until the owner replaces or explicitly removes it. At least one valid row must remain. |
| Q12: Active recipe edits | POS uses the saved recipe while editing. A valid save replaces it atomically and preserves active status; invalid saves change nothing. |
| Q13: Cost warning | Ingredient cost above selling price gives a warning but does not block saving or activation. |
| Q14: Conflicting edits | Reject stale saves; preserve submitted values for comparison and ask the owner to reload. |

Do not add MenuCategory, a separate Recipe model, image uploads, recipe versions,
batch yields, unit conversion, or automatic stock deduction in the first increment.
The project mentions uploads for Sprint 3; menu images are a later extension if
the team assigns them to US-03.

## 2. Verified dependencies and remaining team agreements

| Concern | Existing implementation on origin/main |
| --- | --- |
| Restaurant | accounts.models.Restaurant; no owner field on Restaurant. |
| User and tenant | accounts.models.CustomUser; restaurant is a nullable FK; role is owner or staff; AUTH_USER_MODEL is accounts.CustomUser. |
| Current restaurant | request.user.restaurant is supported by the actual user model. |
| Ingredient | inventory.models.Ingredient; restaurant, name, unit, price, stock_quantity, revision. |
| Quantity precision | stock_quantity uses max_digits=12, decimal_places=3. |
| Unit price | price uses max_digits=10, decimal_places=2; represents price per Ingredient.unit. |
| Stock lots | inventory.models.StockIn; quantity and remaining_quantity use three decimal places; expiry is stored per lot. |
| Shared UI | main/myproject/templates/base.html and navbar.html; Bootstrap 5 and Thai UI; content, extra_css, and extra_js blocks. |
| Auth routes | accounts:login, accounts:home, accounts:logout; accounts:home is the existing no-restaurant redirect destination. |
| Planned US-03 name | Project settings and URL configuration already contain commented placeholders for menus and /menus/. |

Use a menus app and /menus/ routes to follow the shared project's convention.
Use foreign keys to accounts.Restaurant and inventory.Ingredient. Resolve owners
using CustomUser.Role.OWNER, not restaurant.owner. Reject staff access to the owner
management screens and handle authenticated users without a restaurant.

| Collaborator | Agreement needed |
| --- | --- |
| US-01 | Carry the owner's platform-wide owner-only decision into shared auth; reuse user.restaurant and role; redirect a user without a restaurant to accounts:home. |
| US-02 | Use Ingredient.price and stock_quantity; integrate positive price validation, referenced-unit protection, and atomic ingredient deletion/menu deactivation. |
| US-04 | Owner-only POS; use active, valid menus; read per-serving quantities; own stock mutations and transactions; do not cache sellability across a sale commit. |
| US-06 | Reuse the current-cost calculation; distinguish current estimates from historical sale costs. |
| Shared UI owner | Extend existing base.html, follow Thai labels and theme, and add a menus navigation link. |

Use the team's real shared models. Do not create a second Restaurant or Ingredient
inside the menus app. Before implementation, bring the US-03 branch up to the
verified origin/main baseline, preserving the planning file and any user work.
Shared model locations are now known; no cherry-picking of already-merged feature
commits is needed. Temporary test data is appropriate; duplicate production
models are not.

Agreed unit contract: quantity_used and Ingredient.price both refer to Ingredient.unit.
For example, if rice uses kg, 200 g is entered as 0.200 kg. Show this unit next to
the input and explain it in the UI. Changing an ingredient's unit after it is used
in recipes is blocked. Unit conversion is outside this increment.

## 3. Data model

| Model | Fields | Validation / relationships |
| --- | --- | --- |
| MenuItem | restaurant FK, name, normalized_name, price, is_active, revision | Required normalized name; Decimal price > 0; inactive by default; normalized_name unique per restaurant; server assigns tenant and revision. |
| RecipeItem | menu_item FK, nullable ingredient FK, quantity_used, ingredient_name_snapshot, ingredient_unit_snapshot | Decimal quantity > 0; one live row per menu/ingredient pair; linked ingredient belongs to menu's restaurant; snapshots label a deleted-ingredient placeholder. |

Proposed precision: menu price uses max_digits=10, decimal_places=2;
quantity_used uses max_digits=12, decimal_places=3, minimum 0.001 to match the
existing inventory and lot quantities. Reject excess precision rather than
silently rounding a stock requirement. If quantities smaller than 0.001 of the
stored unit are needed, agree a smaller base unit or a shared precision change
with US-02/04 first. Use Decimal arithmetic for intermediate cost calculations.

Add database check constraints for positive menu price and quantity, unique
constraints on (restaurant, normalized_name) and (menu_item, ingredient).
Use one normalization rule (trim/collapse whitespace and casefold) for menu names
and persist its result on every supported write path. Enforce cross-restaurant relations
in model validation and the supported write paths; a normal database check
constraint cannot compare fields on the linked Ingredient row.

Implementation proposal for the agreed deletion behavior: RecipeItem.menu_item
uses CASCADE, and RecipeItem.ingredient uses SET_NULL. Snapshot ingredient name
and unit when assigning/replacing the ingredient; preserve those labels when the
ingredient is deleted. A null ingredient is an explicit missing row, not a blank
extra form and not a zero-cost ingredient. Menu management offers deactivation
instead of hard deletion. Future order references must preserve menu history.

Coordinated inventory changes required by the agreed behavior:

- ingredient_delete must identify affected menus, preserve row labels, mark all
  affected menus inactive, increment their revisions, and delete the ingredient
  within one transaction. No temporary state may expose an active broken recipe.
  Apply the same invariant to any enabled alternate deletion path; a view-only
  fix is insufficient. If deletion fails, roll back all related changes.
- IngredientForm currently permits unit edits. Reject a unit change for an
  ingredient referenced by RecipeItem, including alternate enabled edit paths;
  a recipe must not silently change meaning when kg becomes g. Keep ordinary
  positive price changes supported and verify they update the current-cost estimate.
- Ingredient.price currently allows zero and defaults to zero. Require an explicit
  price > 0 in creation/editing and model/database validation. Inspect existing
  zero-price records before adding the constraint: report records needing owner
  correction rather than inventing prices. Update affected tests and fixtures.

## 4. Owner workflow and screens

1. Menu list: show this restaurant's names, prices, active/inactive status, recipe
   completion or missing-ingredient status, and edit links.
2. Create menu: enter name and selling price; save as an incomplete menu and
   redirect to its recipe builder. New menus are inactive. If creation is
   abandoned, the menu stays saved and unavailable to POS.
3. Recipe builder: show menu name/price; rows contain ingredient, ingredient unit,
   quantity per serving, and a remove action. Add another row without losing input.
4. Save recipe: require at least one valid, undeleted row and resolve all missing
   ingredients by replacement or explicit row removal; validate all rows before
   writing. Save additions, edits, and deletions in a single transaction. An invalid
   submission preserves the previously saved recipe and displays entered values.
5. Show line costs and total estimated ingredient cost per serving. If any saved
   ingredient is missing, label the total incomplete rather than showing a
   misleading partial total. Show a nonblocking warning if total exceeds price.
6. Explicitly activate a menu using an "Available for sale" control. Activation
   requires at least one valid row, no missing ingredients, same-restaurant links,
   positive quantities and ingredient prices, and a positive menu price.
   Deactivation preserves all menu and recipe records.

Completion is derived from the saved recipe; is_active records the owner's
explicit availability choice. Saving a complete inactive recipe does not activate
it. A valid edit to an active recipe preserves active status. During editing, the
old saved recipe remains in use until the transaction commits. Validation failure
leaves the old recipe and activation unchanged. US-04 enforces both availability
and recipe validity server-side in its sale transaction.

Protect menu details, recipe saves and availability changes with a shared menu
revision. Compare the submitted revision and claim the update atomically; reject
stale submissions without changes, including deletion of recipe rows. Preserve
submitted values and show the current version for comparison/reload. Ingredient
deletion must also advance affected menu revisions so an old editor cannot
silently reactivate or overwrite the broken recipe. Coordinate current ingredient
validation with concurrent price/unit/deletion changes when committing a save.

Proposed URLs and names:

| URL | View | Template |
| --- | --- | --- |
| /menus/ | menu_list | menus/menu_list.html |
| /menus/new/ | menu_create | menus/menu_form.html |
| /menus/<pk>/edit/ | menu_update | menus/menu_form.html |
| /menus/<pk>/recipe/ | recipe_builder_view | menus/recipe_builder.html |
| /menus/<pk>/availability/ | menu_availability_update (POST) | Control on the list or recipe builder |

Use Django ModelForm for menu data and an inline formset for recipe rows.
Supply the current restaurant to validation and filter every ingredient selector.
Use formset management fields and empty_form for dynamic rows; removal must submit
the appropriate deletion marker. Handle blank extra rows and formset-wide errors.
Core validation and saving must work on the server regardless of JavaScript.

## 5. Business logic and integration

Keep request handling and template rendering in views; keep quantity and costing
rules in the menus module so POS and reports can reuse them.

Small proposed interface:

- ingredient_requirements(menu, servings): return ingredient quantities for a
  positive serving count; reject empty or missing-ingredient recipes; never mutate stock.
- calculate_menu_cost(menu): sum quantity_used * ingredient.price using
  Decimal; return no usable estimate for an incomplete recipe, rather than a
  misleading zero. Display rounding occurs at the currency presentation step.

Include a shared sellability check so POS can reject inactive or invalid menus
at its write interface; simply hiding an unavailable menu in the UI is insufficient.
Cost preview and quantity calculations may read complete inactive recipes.
Both callers must first obtain an authorized menu. Fetch recipe ingredients
together when calculating costs to avoid one query for each row.

Example using kg and pieces: rice 0.200 kg at 40 THB/kg costs 8 THB; egg 1 piece
at 5 THB/piece costs 5 THB. Estimated cost is 13 THB per serving. Three servings
need 0.600 kg rice and 3 eggs. Building or editing this recipe changes no stock.

Cost previews use current ingredient prices and change when those prices change.
Historical cost snapshots belong to the sales/reporting agreement with US-04/06.
Likewise, editing a recipe after an order must not rewrite past stock movements.
US-04 must integrate stock_quantity, StockIn.remaining_quantity and the existing
revision mechanism consistently; US-03 reads ingredient data and changes none of
these fields. Inventory lot allocation and concurrency remain US-04's work.

## 6. Authorization and integrity

- Require authentication and current restaurant ownership for every menu action.
- Resolve restaurant from trusted authenticated context, never a submitted ID.
- Fetch menus through the authorized restaurant queryset; foreign IDs return 404.
- Filter ingredient choices on both GET and POST, and validate restaurant equality.
- Bind recipe edits to the selected menu's rows; reject forged row IDs from
  another menu, including a different menu in the same restaurant.
- Explicitly list editable form fields; restaurant and menu_item are not user-editable.
- Mutations use POST with CSRF protection; keep Django template escaping enabled.
- Apply ownership/tenant validation to any admin or alternate write path the team enables.

## 7. Proposed acceptance criteria and traceability

| ID | Observable behavior | Implementation evidence | Test evidence |
| --- | --- | --- | --- |
| US03-AC01 | Owner creates and edits a menu with valid name and price. | MenuItem; menu_create/menu_update; menu_form.html | Persisted fields; blank name; negative price. |
| US03-AC02 | Owner saves multiple ingredients and per-serving quantities. | RecipeItem; recipe_builder_view; recipe_builder.html | Multiple rows persist with correct values. |
| US03-AC03 | Owner adds, updates, and removes recipe rows. | Recipe formset and save transaction | Reloaded recipe matches intended edits; last-row deletion rejected. |
| US03-AC04 | Invalid or duplicate rows cannot partially change a recipe. | Formset validation; model constraints; transaction | Zero/negative quantity; duplicate ingredient; malformed input; rollback. |
| US03-AC05 | Restaurant data cannot be accessed or linked across restaurants. | Scoped lookups; ingredient validation; ownership checks | Cross-tenant GET and POST; forged ingredient/row/menu IDs; anonymous access. |
| US03-AC06 | Saved recipes expose quantities and current estimated costs. | Reusable quantity/cost functions; cost preview | Decimal calculation; serving scaling; price change; incomplete total; cost-above-price warning without blocking. |
| US03-AC07 | Recipe edits leave ingredient stock and lots unchanged. | Recipe write path | Compare stock_quantity, revision and StockIn.remaining_quantity before/after. |
| US03-AC08 | UI and change history trace back to US-03 / UC-03. | View docstrings; template comments; issues/PRs; this matrix | Review checklist and CI evidence. |
| US03-AC09 | Drafts start inactive; availability is explicit and requires a complete valid recipe. | is_active; availability update; shared sellability check | Valid save does not autoactivate; incomplete/missing recipe cannot activate; inactive menu unavailable to POS. |
| US03-AC10 | Ingredient deletion deactivates every affected menu and retains visible missing rows. | Transactional deletion integration; SET_NULL and snapshot fields | Multiple menus deactivated; unaffected menus unchanged; labels retained; rollback on failure; recipe requires repair. |
| US03-AC11 | Referenced ingredient units cannot change; all prices are positive. | Inventory and menu validation/constraints | Unit change rejected when referenced; unchanged unit/positive price edit accepted; zero and negative prices rejected. |
| US03-AC12 | Duplicate menu names are rejected per restaurant after normalization. | Name normalization; database unique constraint | Case and whitespace variants rejected; other restaurants can reuse a name. |
| US03-AC13 | Valid edits preserve active status and replace recipes together. | Atomic recipe update | Saved recipe used before commit; failed edit leaves availability/recipe unchanged. |
| US03-AC14 | Stale edits cannot overwrite changes. | Shared menu revision; comparison UI | Two-tab menu, recipe and availability conflicts; ingredient deletion invalidates old recipe form; submitted values preserved. |

Cross-story tests cover inactive/incomplete/missing-ingredient sale rejection and
a sale using the saved recipe once US-04 is integrated. Owner-only access is the
agreed platform requirement; coordinate enforcement in existing apps without
adding a staff workflow. Include no-restaurant access and quantity precision tests.

Keep a [US-03][UC-03] reference in each relevant view docstring and a Django
template comment in each relevant template. Traceability maps complete functions
and screens; avoid repetitive comments on every statement.

## 8. File layout proposal

Under main/myproject/menus/:

- models.py and migrations/: MenuItem and RecipeItem.
- forms.py: MenuItemForm, RecipeItemForm, recipe formset validation.
- services.py: shared quantities, costing, sellability, versioned saving, and
  ingredient-deletion integration as needed.
- views.py and urls.py: authenticated, restaurant-scoped owner workflow.
- templates/menus/: menu_list.html, menu_form.html, recipe_builder.html.
- static/menus/recipe_builder.js: add/remove row behavior, if needed.
- tests/: model, form, view, permission, and calculation tests.

Enable the existing menus placeholders in settings and project URL configuration.
Use app_name = 'menus' for named routes. Extend the existing shared base.html
and add the menu link to the shared navbar.html.

Initial menus migration depends on accounts.0001_initial and the current
inventory leaf migration (currently 0002_ingredient_revision); let Django generate
and verify the actual dependencies. Coordinate inventory deletion, unit-edit and
positive-price changes and their tests with US-02. Avoid importing inventory.views for access
control; it is not a shared auth module and its restaurant_required decorator
does not enforce owner role. Keep a small menus owner-access helper or agree a
shared accounts helper if another module needs the same interface.

## 9. Delivery tasks and pull requests

| Order | Suggested issue title | Deliverable |
| --- | --- | --- |
| 1 | [US-03] Restrict business screens to restaurant owners | Reusable owner access rule; existing business screens deny nonowners; access tests; no blockers. |
| 2 | [US-03] Require positive ingredient unit prices | Inventory create/edit errors, model/database rule and existing-data validation; no blockers. |
| 3 | [US-03] Create and edit private draft menus | Owner-scoped list/create/edit, normalized unique names, positive prices and stale-edit handling; blocked by 1. |
| 4 | [US-03] Build recipes with current ingredient costs | Complete recipe editing, unit protection, Decimal costs, shared quantity reads and conflict tests; blocked by 2 and 3. |
| 5 | [US-03] Repair recipes after ingredient deletion | Atomic deletion/deactivation, visible missing rows, incomplete costs and repair flow; blocked by 4. |
| 6 | [US-03] Activate valid menus for owner POS | Explicit availability, shared sellability interface, inactive-menu retirement and complete POS/reporting read contract; blocked by 5. |

Each ticket is a complete observable behavior with its own validation, UI and
tests. Branch synchronization with the latest main is an implementation
prerequisite, not a separate layer-only ticket. Tickets 1 and 2 may start
independently. Ticket 6 follows deletion handling so active menus cannot ship
without safe behavior when an ingredient disappears.

Sprint 1: contracts, models, owner screens, recipe editor, and isolation.
Sprint 2: integrate POS/reports, verify quantities/costs, and contribute to overall
coverage >80%. Aim for at least 85% on this module for margin; module coverage
alone does not establish the project's overall coverage target.
Sprint 3: exercise production configuration, responsive/accessibility checks,
and the final security/demo pass. Tenant isolation and CSRF start in Sprint 1.

Use the team's protected-main workflow: feature branches under codex/ unless the
team specifies another convention, US-03-linked issues/PRs, passing CI, and at
least one reviewer approval. Preserve the existing user-selected US-03 branch
name unless a rename is requested. Current delivery is local planning/spec/ticket
files only. Do not create branches, external issues or PRs or update application
code as part of this delivery.

## 10. Definition of done and demo

- [ ] Shared contracts agreed; no duplicate tenant/ingredient models.
- [ ] AC01-AC14 confirmed and implemented, including rejection of forged POST data.
- [ ] Database migrations apply; Django checks and relevant tests pass.
- [ ] Existing recipes survive invalid updates; stock remains unchanged.
- [ ] Deleted ingredients leave visible missing rows and deactivate affected menus.
- [ ] Activation, name uniqueness, positive prices, unit protection and stale-edit
      behavior match the interview decisions.
- [ ] Bootstrap 5 screens work on mobile and desktop; errors are readable.
- [ ] Full-project coverage exceeds 80% in the agreed CI workflow.
- [ ] Traceability matrix and view/template references match final code.
- [ ] PR is reviewed and CI passes before merge.
- [ ] Demo: create menu, add rice and egg quantities, save/reopen recipe, show
      cost 13 THB, explicitly activate, reject invalid quantity, and verify another
      restaurant cannot access the recipe. Demonstrate a deleted-ingredient row,
      automatic deactivation and blocked reactivation until repair. With US-04
      integrated, sell three servings and verify
      its stock movements use 0.600 kg rice and 3 eggs.

## Implementation references

Official Django documentation for the proposed mechanisms:

- [Inline formsets](https://docs.djangoproject.com/en/6.0/topics/forms/modelforms/#inline-formsets)
- [Atomic database transactions](https://docs.djangoproject.com/en/6.0/topics/db/transactions/#django.db.transaction.atomic)
- [Database constraints](https://docs.djangoproject.com/en/6.0/ref/models/constraints/)

These references describe the mechanisms; verify the implementation against the
team's installed/pinned Django version before coding.
