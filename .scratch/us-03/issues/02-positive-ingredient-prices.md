# 02: [US-03] Require positive ingredient unit prices

**What to build:** When an owner creates or edits an ingredient, its unit price must be greater than zero. Show clear errors for missing, zero or negative prices while preserving the entered data and saved inventory. Valid positive price changes remain supported, providing reliable inputs for the recipe cost builder.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] Inventory creation/editing requires an explicit positive unit price; blank, zero and negative values receive readable errors with no partial write.
- [x] Model validation and a database constraint enforce positive ingredient prices for supported alternate write paths; the implicit zero-price creation default is removed.
- [x] Existing zero-price data is inspected before constraint enforcement. Report records needing legitimate owner correction rather than silently inventing prices or deleting records.
- [x] Positive edits still honor inventory's existing revision checks and cannot overwrite a receipt or another edit.
- [x] Zero stock remains valid. A price-only change leaves stock quantity and lot remaining quantities unchanged and adds no stock receipt; existing inventory revision behavior is preserved.
- [x] Request and integrity tests cover invalid prices, valid positive changes, unchanged state on rejection, legitimate zero stock and existing-data constraint readiness. Adjust affected fixtures without weakening their original assertions.
- [x] UI labels/errors, migrations and changed behavior are traceable to the positive-price decision in US-03/UC-03; coordinate with US-02.
