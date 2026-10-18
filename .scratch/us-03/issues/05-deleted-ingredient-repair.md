# 05: [US-03] Repair recipes after ingredient deletion

**What to build:** When an owner deletes an ingredient, every affected menu becomes inactive and its recipe retains a visibly identified missing-ingredient row. The owner can inspect the problem and replace or explicitly remove missing rows to repair the recipe. A broken recipe never displays a misleading full cost. This completes deletion safety before sellable menus are introduced.

**Blocked by:** 04: [US-03] Build recipes with current ingredient costs

**Status:** in-review

- [ ] The existing owner ingredient-deletion workflow identifies all affected menus and deletes the ingredient, retains recipe labels, deactivates those menus and advances their revisions atomically.
- [ ] Every enabled alternate deletion path preserves the same invariant, including bulk/admin paths if enabled. A failed operation rolls back deletion and every related change.
- [ ] Affected recipe rows remain identifiable by ingredient name, stored unit and quantity and are clearly marked missing. Never silently remove them or count them as zero-cost ingredients.
- [ ] Broken recipes show incomplete cost and cannot produce valid sale requirements. Unaffected menus and other restaurants remain unchanged.
- [ ] The builder permits same-restaurant replacement or explicit row removal. A valid repair leaves at least one valid row and resolves every missing ingredient; normal duplicate, quantity and ownership rules still apply.
- [ ] Repair does not reactivate the menu. Owners see that explicit activation will be necessary after repair.
- [ ] A recipe editor opened before ingredient deletion cannot save over the new broken state using an old revision, restore deleted identities or silently reactivate a menu. Preserve submitted values for comparison.
- [ ] Request and transaction tests cover one ingredient shared by multiple menus, unaffected records, retained labels, failed-deletion rollback, missing-row repair, last-row rejection, stale editors, tenant isolation and all enabled deletion paths.
- [ ] Inventory/recipe messages and changed behavior are traceable to US-03/UC-03 and retain existing inventory regression coverage.
