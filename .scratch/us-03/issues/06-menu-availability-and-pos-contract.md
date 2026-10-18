# 06: [US-03] Activate valid menus for owner POS

**What to build:** An owner explicitly marks a complete menu available for sale or makes it inactive without deleting it. The same sellability rule is available to owner Mini-POS, while reporting can still read complete inactive recipes. A valid recipe edit preserves availability, and deletion/repair cannot accidentally resume sales. Deliver the menus contract now without implementing checkout or waiting for US-04.

**Blocked by:** 05: [US-03] Repair recipes after ingredient deletion

**Status:** in-review

- [ ] An owner-facing availability control shows active/inactive state and uses an authenticated, restaurant-scoped, CSRF-protected state-changing request. New and merely completed recipes remain inactive by default.
- [ ] Server-side activation requires at least one valid row, no missing ingredients, correct restaurant links and positive prices/quantities. Direct forged requests cannot bypass the rule.
- [ ] Deactivation retains menu/recipe records. A repaired recipe stays inactive until the owner explicitly activates it. No owner-facing hard-delete action is introduced.
- [ ] Availability changes use the shared menu revision; outdated or missing tokens cannot overwrite another change and provide entered/current values for comparison where applicable.
- [ ] While an active recipe is being edited, readers see the previous saved recipe until a successful atomic save. A valid edit preserves active status; a failed edit changes nothing.
- [ ] The public menus read interface exposes sellability, scaled ingredient requirements and current cost. Inactive, empty or broken menus are rejected for sale; complete inactive recipes remain readable for planning and reporting.
- [ ] A cost-above-selling-price warning does not block activation. Referenced units, positive prices and missing-row rules remain enforced.
- [ ] Contract/request tests prove explicit activation, all invalid activation cases, inactive retirement, valid/failed active edits, stale changes and the complete deletion → inactive → repair → explicit activation journey. Tests use real domain records and no stock mutation.
- [ ] Document the US-04 consumer contract: owner-only access; recheck sellability against the consistent saved recipe inside checkout; own stock sufficiency, atomic stock/lot deductions and history. Actual checkout implementation is outside this ticket and is not a blocker.
- [ ] Demonstrate the full owner menu workflow; include US-03/UC-03 traceability and relevant passing checks. Contribute to the project's coverage above 80%; the overall target remains shared across the team.
