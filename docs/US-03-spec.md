## Problem Statement

Restaurant owners cannot reliably connect a dish's selling price to the ingredients and quantities needed to prepare it. Without a recipe Bill of Materials (BOM), current ingredient cost is unclear and the Mini-POS has no trustworthy quantities to use for stock deduction. Menus also need a safe lifecycle: incomplete or broken recipes must not become sellable, and ingredient changes must not silently alter recipe meaning.

US-03 must provide this behavior using the existing Restaurant, CustomUser, Ingredient and stock-lot domain. Owners must only access their own restaurant's data. The approved product scope makes the entire platform owner-only, including Mini-POS.

## Solution

Provide an owner-only menu and recipe workflow in the existing Django and Bootstrap application. Owners save draft menus, build recipes from their restaurant's ingredients, inspect current ingredient costs, and explicitly activate complete menus for sale. Menus can be made inactive without removing records needed by sales.

Quantities are recorded per serving in each ingredient's stored unit. Ingredient deletion makes all affected menus inactive and leaves visible missing-ingredient rows until repaired. Edits are validated and saved together, and outdated forms cannot overwrite newer changes. The menus module exposes saved quantities, current costs and sellability to Mini-POS and reporting; checkout remains responsible for stock deduction.

## User Stories

1. As a restaurant owner, I want to access business screens using my authenticated owner account, so that restaurant management remains restricted to owners.
2. As a restaurant owner, I want my restaurant to be determined from my account, so that submitted data cannot redirect changes into another restaurant.
3. As a restaurant owner, I want other restaurants' menus and recipes to be inaccessible, so that my business data remains private.
4. As a restaurant owner, I want a clear response when my account has no restaurant, so that I understand why management is unavailable.
5. As a restaurant owner, I want to list my menus and their availability, so that I can manage what my restaurant sells.
6. As a restaurant owner, I want to create a menu with a name and positive selling price, so that a dish has a clear identity and price.
7. As a restaurant owner, I want to save a menu before completing its recipe, so that I can finish preparation later.
8. As a restaurant owner, I want new menus to start inactive, so that unfinished dishes cannot be sold accidentally.
9. As a restaurant owner, I want duplicate menu names to be rejected despite capitalization or extra spaces, so that dishes remain distinguishable.
10. As a restaurant owner, I want another restaurant to be able to reuse a menu name, so that uniqueness does not cross restaurant boundaries.
11. As a restaurant owner, I want to edit a menu's name and selling price, so that its details stay current.
12. As a restaurant owner, I want to identify menus with incomplete or broken recipes, so that I know which ones need attention.
13. As a restaurant owner, I want to select recipe ingredients from my own restaurant, so that dishes use the correct inventory.
14. As a restaurant owner, I want multiple ingredients in a recipe, so that the BOM represents the dish accurately.
15. As a restaurant owner, I want quantities recorded per serving, so that sales can scale requirements consistently.
16. As a restaurant owner, I want the stored ingredient unit displayed beside each quantity, so that I enter the intended measurement.
17. As a restaurant owner, I want quantities accepted to three decimal places, so that recipes match inventory precision.
18. As a restaurant owner, I want nonpositive or excessively precise quantities rejected, so that requirements cannot become invalid or silently rounded.
19. As a restaurant owner, I want duplicate ingredients in a recipe rejected, so that quantities are unambiguous.
20. As a restaurant owner, I want to add, edit and remove ingredient rows, so that I can maintain recipes as dishes change.
21. As a restaurant owner, I want clear validation errors without losing my entries, so that I can correct a recipe efficiently.
22. As a restaurant owner, I want a failed save to preserve the previous recipe, so that an invalid edit cannot partially change a dish.
23. As a restaurant owner, I want recipe editing to leave stock quantities unchanged, so that only inventory and sales workflows affect stock.
24. As a restaurant owner, I want ingredient unit prices to be positive, so that calculated ingredient costs do not use zero or negative prices.
25. As a restaurant owner, I want each recipe line's current ingredient cost displayed, so that I can understand the total.
26. As a restaurant owner, I want total current ingredient cost per serving displayed, so that I can compare it with the selling price.
27. As a restaurant owner, I want a positive ingredient price change reflected when the recipe cost is recalculated, so that estimates stay current.
28. As a restaurant owner, I want a warning when ingredient cost exceeds selling price, so that I can review the dish while retaining the ability to offer promotions.
29. As a restaurant owner, I want to explicitly activate a valid menu, so that I control when it becomes available for sale.
30. As a restaurant owner, I want activation blocked for an empty, invalid or broken recipe, so that incomplete dishes cannot reach checkout.
31. As a restaurant owner, I want to deactivate a menu without deleting its record, so that prior sales can retain their reference.
32. As a restaurant owner, I want referenced ingredient units protected from changes, so that existing quantities cannot silently change meaning.
33. As a restaurant owner, I want deleting an ingredient to deactivate every affected menu, so that no broken dish remains available.
34. As a restaurant owner, I want deleted ingredients to remain visibly identified in recipes, so that missing requirements are not silently hidden.
35. As a restaurant owner, I want a broken recipe's cost marked incomplete, so that a partial sum is not mistaken for its full cost.
36. As a restaurant owner, I want to replace or explicitly remove a missing ingredient row, so that I can repair the dish before reactivation.
37. As a restaurant owner, I want a repaired menu to require explicit reactivation, so that repair alone does not resume sales.
38. As a restaurant owner, I want the saved recipe to remain available while I edit, so that unsaved changes do not affect ongoing work.
39. As a restaurant owner, I want valid edits to preserve an active menu's availability, so that routine recipe maintenance does not unexpectedly retire it.
40. As a restaurant owner, I want outdated saves rejected while my submitted values remain visible for comparison, so that another tab cannot silently overwrite newer work.
41. As a restaurant owner using Mini-POS, I want checkout to consume the saved recipe and current sellability rule, so that unavailable or broken menus are rejected server-side.
42. As a restaurant owner reviewing reports, I want reusable current-cost calculations, so that the builder and analytics use the same ingredient arithmetic.

## Implementation Decisions

- Use the existing accounts and inventory modules and add the menus module already anticipated by the project. Reuse Restaurant, CustomUser and Ingredient; do not duplicate their models.
- Use the authenticated CustomUser's restaurant and owner role. Public registration/login remain accessible, but authenticated business screens do not grant access to the existing staff role. Coordinate that owner-only rule across existing business screens; future Mini-POS must follow it.
- Keep the server-rendered Django and Bootstrap approach, existing Thai labels, shared navigation and shared layout.
- MenuItem contains its restaurant, name, normalized name, positive selling price, availability flag and revision. New records start inactive. Menu removal is deactivation rather than owner-facing hard deletion.
- Trim and collapse whitespace and casefold menu names consistently. Persist the normalized value and enforce uniqueness per restaurant, including inactive menus. Different restaurants may reuse the same name.
- RecipeItem connects a menu to an ingredient and positive quantity used per serving. Retain ingredient name and unit snapshots to label a row after its ingredient is deleted. The ingredient relationship becomes null on deletion; the row remains explicitly broken until repaired.
- Menu prices have two decimal places. Recipe quantities have three decimal places and a minimum of 0.001 in the stored unit, matching existing inventory quantities. Use Decimal arithmetic and reject extra precision rather than silently rounding a requirement.
- Require a positive Ingredient.price in owner forms, supported writes and database validation. Remove the implicit zero-price creation behavior. Inspect existing zero-price records before enforcing the constraint; require legitimate owner corrections rather than fabricating prices. Zero stock remains valid and is distinct from zero price.
- Enforce positive menu prices and quantities, restaurant/name uniqueness and one live ingredient row per menu/ingredient pair with database constraints where applicable. Enforce cross-restaurant relationships in supported write interfaces and validation.
- Create the menu first, save it inactive and continue to the recipe builder. The saved draft may have no recipe. Saving a completed recipe does not activate it automatically.
- Use an inline formset for recipe rows with server-side validation. Show stored units, ingredient choices scoped to the current restaurant, row errors and form-wide errors. Preserve entered values on failure. Browser scripting may add/remove rows but does not own validation or authorization.
- A recipe save requires at least one valid retained row. Missing ingredients must be replaced or explicitly removed. Reject duplicate ingredients and forged menu, ingredient or existing-row identities, including identities from another menu in the same restaurant.
- Validate every proposed row and save additions, changes and removals in one transaction. Failed validation or persistence changes neither the saved recipe nor availability.
- Calculate each line using quantity used multiplied by current Ingredient.price and sum without intermediate currency rounding. Round only the displayed money total consistently. Refresh the computed preview from current saved data when the page is rendered or a save succeeds; do not persist it as a historical cost.
- If any ingredient is missing, or the recipe is empty, report an incomplete cost instead of a partial or misleading zero total. Ingredient cost exceeding selling price produces a nonblocking warning.
- Explicit availability changes use an owner-authorized state-changing request. Activation requires a nonempty valid recipe, no missing ingredients, correct restaurant links and positive prices and quantities. Deactivation preserves the recipe.
- Ingredient unit edits are rejected while any recipe references that ingredient, including inactive menus. Ordinary positive price changes remain supported and feed subsequent current-cost calculations.
- Ingredient deletion identifies every affected menu, retains identifying row labels, deactivates those menus, advances their revisions and removes the ingredient in one transaction. Apply the invariant to every enabled deletion path, including bulk or administrative paths. A failure rolls everything back.
- Replacing or explicitly removing missing rows repairs the recipe only when at least one valid row remains and every remaining row is valid. Repair leaves the menu inactive until explicit activation.
- Saved recipe data remains authoritative while an owner edits. A valid save replaces it atomically and preserves an active menu's status. No incomplete intermediate version is exposed to consumers.
- Use a shared MenuItem revision for metadata, recipe and availability changes. A stale or absent expected revision cannot bypass conflict protection. Reject the save without side effects, preserve submitted values for comparison and offer a reload of the current version. Ingredient deletion also invalidates affected open editors.
- Coordinate recipe commits with ingredient updates and deletion so an ingredient change between validation and commit cannot install an invalid recipe or silently change its unit meaning.
- Expose a small public menus read interface for per-serving or scaled ingredient requirements, current ingredient cost and sellability. Complete inactive recipes may still be inspected for requirements and cost; sales require active and valid menus. No new HTTP API is required.
- US-04 owns checkout, stock sufficiency, atomic deductions, lot allocation and stock-movement history. It must recheck sellability and consume a consistent saved recipe in the sale transaction, while respecting existing inventory revisions. US-03 recipe edits do not write Ingredient.stock_quantity, inventory revisions or lot remaining quantities.
- US-06 reuses current cost arithmetic. Current estimates must not be described as historical sale costs, and recipe edits must not rewrite past sales or movements.
- Require login, owner access, restaurant-scoped object lookups, explicit editable fields, CSRF protection and escaped template output. Enforce those rules server-side, including forged state-changing requests.
- Preserve the protected-main workflow, linked US-03 issues/PRs, passing CI and at least one peer approval. Trace owner views and templates back to US-03 and UC-03.

## Testing Decisions

- Proposed primary seam: the owner-facing Django request/response interface, exercised using Django's test client with the real test database. Verify rendered errors and statuses, redirects, persisted state and absence of forbidden side effects. No HTTP JSON layer or generic repository abstraction is needed.
- Proposed secondary seam: the same small public menus read interface that POS and reporting will call. Direct contract tests are justified because those consumers are not yet implemented. Check returned quantities, current costs and sellability without testing internal helper calls.
- A good test describes externally meaningful behavior and fails when a user or consumer contract is broken. Avoid assertions tied to internal function decomposition, exact ORM call order, HTML formatting trivia or a duplicated implementation formula.
- Test menus, changed accounts access and inventory integration, including forged GET/POST identifiers, anonymous users, staff users, users without restaurants and two independent restaurants. Reject access before leaking another restaurant's object existence.
- Test normalized duplicate names, positive menu and ingredient prices, quantity precision, duplicate rows and invalid formsets. Verify correct errors and unchanged persisted data on failure.
- Use known Decimal examples: 0.200 kg rice at 40 THB/kg plus one egg at 5 THB gives 13 THB per serving; three servings require 0.600 kg rice and three eggs. Check price changes, display rounding and a nonblocking cost-above-price warning.
- Test drafts, explicit activation/deactivation, rejection of forged activation for invalid recipes and retention of the active flag after valid edits. A completed inactive recipe must not activate merely because it was saved.
- Test deletion across multiple affected menus, visible retained labels, incomplete cost, blocked activation, replacement/removal repair and explicit reactivation. Verify unrelated menus and other restaurants remain unchanged and a failed deletion rolls back.
- Test referenced-unit changes and enabled alternate write/deletion paths so bypassing the normal screen cannot break recipe invariants. New price validation must not accidentally reject legitimate zero stock or change stock balances.
- Use the existing inventory revision-conflict tests as prior art for two-tab saves. Verify stale metadata, recipe and availability requests, missing revision tokens, ingredient deletion during editing and preservation of submitted comparison values. Exercise concurrent operations at a transaction-capable seam where needed rather than relying only on form checks.
- Use existing inventory tenant fixtures, request tests, ingredient form tests, failed-operation rollback checks and stock/revision regression tests as prior art. Do not inherit their staff-access behavior where it conflicts with the approved owner-only scope.
- Reopening a recipe verifies persistence; a focused browser check verifies dynamic add/remove controls and responsive Bootstrap layouts. Recipe edits must leave ingredient stock, stock revisions and lot balances unchanged.
- Each behavior ticket includes its own tests and traceability. Contribute to project coverage above 80%, aiming for at least 85% on the changed module without treating module coverage as proof of overall project coverage. Actual checkout integration tests join US-04 when its implementation is available; menu contract tests do not wait for checkout.
- The user approved the primary and secondary testing seams and the six-ticket breakdown before authorizing publication.

## Out of Scope

- Implementing Mini-POS, orders, payment, stock sufficiency or stock deduction within US-03.
- Staff, customer, kitchen or public browsing workflows; the approved platform is owner-only.
- Historical cost snapshots, full analytics dashboards, sale-history rewriting or recipe version history.
- Separate reusable Recipe entities, nested subrecipes, batch yields, unit conversion or automatic quantity rounding.
- Menu categories, menu images, upload handling and media storage in this increment.
- Margin dashboards, taxes, packaging/labor overhead accounting or preventing deliberately below-ingredient-cost pricing.
- A separate frontend framework, REST API, generic repository architecture or unrelated inventory redesign.
- External issue publication or tracker changes in this local-only workflow; changing or closing parent issues; and starting application implementation as part of specification/ticket delivery.

## Further Notes

- Source parent: [US-03 issue #4](https://github.com/theepop66/CN331-Restaurant-management/issues/4). Its full body and comments were read. The source asks for menu deletion; the owner subsequently approved inactive-menu retirement to preserve references. The parent issue remains unchanged.
- The owner approved all Q1-Q14 decisions and then explicitly approved the consolidated plan. This specification synthesizes those answers; it does not reopen product decisions.
- The [team agreement](https://github.com/theepop66/CN331-Restaurant-management/issues/1) requires acceptance criteria, traceability, CSRF protection, authenticated views, peer review and a clean merge. Story points remain a team estimate; no estimate is fabricated here.
- [US-04 issue #5](https://github.com/theepop66/CN331-Restaurant-management/issues/5) still describes a staff actor. The newer approved owner-only decision is the integration contract for this work; communicate the difference during team review without silently modifying that issue.
- Verified baseline: origin/main at 28d80ad already includes accounts and inventory. Update the implementation branch from the latest main while preserving user work before creating menu migrations.
- The user subsequently selected local files only. Save this specification and six individual behavior tickets in the local tracker; use numbered local blocking edges and the ready-for-agent status. This supersedes the earlier external-publication approval.
- The spec and six GitHub issues created before that instruction were closed at the user's explicit request. The original source parent remains open and unchanged. Those closed issues are historical records, not the active tracker; no additional external action is authorized by this local delivery.
