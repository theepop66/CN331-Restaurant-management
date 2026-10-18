# US-03 local ticket index

The approved specification and six tickets are saved locally only.

- [Active local tracker and dependency graph](../../.scratch/us-03/README.md)
- [Approved local specification](../../.scratch/us-03/spec.md)
- [01 — Owner-only access](../../.scratch/us-03/issues/01-owner-only-access.md)
- [02 — Positive ingredient prices](../../.scratch/us-03/issues/02-positive-ingredient-prices.md)
- [03 — Draft menu management](../../.scratch/us-03/issues/03-draft-menu-management.md)
- [04 — Recipe builder and costs](../../.scratch/us-03/issues/04-recipe-builder-and-costs.md)
- [05 — Deleted ingredient repair](../../.scratch/us-03/issues/05-deleted-ingredient-repair.md)
- [06 — Availability and POS contract](../../.scratch/us-03/issues/06-menu-availability-and-pos-contract.md)

Implementation complete: all six local tickets are done. Original dependency order: Remaining direct edges: 03 waits for 01; 04 waits
for 02 and 03; 05 waits for 04; 06 waits for 05.

The user approved the product design, testing interfaces and ticket breakdown.
The canonical ticket files use the local template and done status.
Reference copies in the documentation ticket folder match the local tickets.
Implementation and independent review are complete; 94 tests were discovered, the optional browser check passed separately, and total coverage is 93.56%.

The spec and six GitHub issues created earlier (9-15) were closed at the user's
explicit request. Original parent issue 4 remains open and unchanged. No further
GitHub publication, labels or native dependencies are part of this local delivery.
The publication record is historical only; it is not the active tracker.
