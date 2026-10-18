# 04: [US-03] Build recipes with current ingredient costs

**What to build:** From a saved draft menu, an owner adds, edits and removes ingredient rows, enters quantities per serving and sees each saved line's current cost and the total. The recipe uses existing inventory units and never changes stock. Referenced ingredient units are protected so quantities retain their meaning. Menus remain inactive until the separate availability slice is delivered.

**Blocked by:** 02: [US-03] Require positive ingredient unit prices; 03: [US-03] Create and edit private draft menus

**Status:** done

- [x] Recipe rows link a menu and same-restaurant ingredient, retain identifying name/unit snapshots and store positive quantities with three decimal places. The ingredient relationship supports retained missing rows after deletion.
- [x] A Bootstrap recipe builder shows stored units, same-restaurant ingredient choices, add/remove actions and validation errors; row controls work without losing entered values. Server validation is authoritative.
- [x] A successful save retains at least one valid row; duplicate ingredients, zero/negative or over-precise quantities, forged ingredient/menu/row identities and invalid formset data are rejected.
- [x] Save additions, edits and removals together. Validation/persistence failure leaves the previous recipe, menu details and availability unchanged. Saving a complete recipe never autoactivates a menu.
- [x] Recipe saves use the menu's shared expected revision. An outdated/missing revision cannot overwrite a newer recipe, metadata or availability change; submitted values remain available for comparison.
- [x] Show current line costs and total using Decimal arithmetic. The known rice/egg example costs 13 THB per serving; a positive inventory price change appears on recalculation. Display rounding does not change stored quantities or intermediate arithmetic.
- [x] Ingredient cost exceeding selling price shows a clear warning without blocking save. Empty/missing-ingredient recipes show an incomplete estimate rather than a partial total.
- [x] The public menus read interface returns scaled requirements for complete recipes and current cost; three servings of the example require 0.600 kg rice and three eggs. Sales availability is delivered in the later activation ticket.
- [x] Referenced ingredient unit changes are rejected, including for inactive recipes and any enabled alternate edit path. Unchanged units and positive price changes remain supported; commit-time ingredient changes cannot silently corrupt a newly saved recipe.
- [x] Request/read-contract tests cover calculations, add/edit/remove persistence, unit protection, forged IDs, invalid/failed saves, conflicts and unchanged stock quantity, inventory revision and lot balances after recipe edits. Include a browser check of dynamic rows and US-03/UC-03 traceability.
