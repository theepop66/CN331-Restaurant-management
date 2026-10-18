# 03: [US-03] Create and edit private draft menus

**What to build:** An owner can list their restaurant's menus, create a named menu with a positive selling price and edit its details. New menus remain inactive drafts and display that their recipe is incomplete. A stale edit cannot overwrite a newer change. This is a complete usable menu workflow even before the recipe builder is delivered.

**Blocked by:** 01: [US-03] Restrict business screens to restaurant owners

**Status:** done

- [x] The menu record stores its restaurant, name, normalized name, selling price, inactive-by-default availability and revision, with applicable schema constraints.
- [x] Owner-only Bootstrap screens support list/create/edit using the shared Thai layout/navigation and established auth handling.
- [x] Creating a menu saves it inactive with no recipe and offers a clear continuation state; this ticket does not expose activation or hard deletion.
- [x] Blank names and nonpositive selling prices are rejected. Names are compared after trimming/collapsing whitespace and casefolding; duplicates within a restaurant are rejected even when inactive. Other restaurants may reuse the name.
- [x] Restaurant is assigned from the authenticated account. Cross-restaurant GET/POST and forged ownership or availability fields cannot access or alter another restaurant's records or activate a draft.
- [x] Metadata updates compare the expected revision atomically. An outdated or absent token cannot overwrite newer data; entered values remain available for comparison/reload.
- [x] Request tests verify creation, persistence, validation, name normalization, isolation, availability defaults, owner access and two-tab conflict behavior with unchanged state on failure.
- [x] Menu actions and templates carry US-03/UC-03 traceability, and relevant checks pass alongside existing accounts/inventory tests.
