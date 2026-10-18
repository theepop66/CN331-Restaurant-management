# US-03 implementation review

Fixed point: 28d80ad392a03bc38ed175f7fa039ed169eb4923, the merged accounts and
inventory baseline. Review command: `git diff 28d80ad...HEAD`. Functional commits
reviewed: 478037e (menu/BOM implementation) and 0847e18 (admin isolation fixes).
Final tracker/report updates are documentation only.

The two code-review axes ran independently as read-only reviewers. The approved
local spec and six tickets supplied the requirements. Existing project patterns,
US/UC traceability, CSRF/login rules, PEP 8 and the skill's code-smell baseline
supplied the standards; tool-enforced style was checked separately.

## Standards

No findings. Added menu views include US-03/UC-03 docstrings, templates include
trace comments, POST forms include CSRF tokens, and owner/restaurant authorization
uses shared access rules and scoped lookups. Menu mutations and reusable cost
calculations live outside views. No material actionable code smells were found.

The follow-up review of the admin fixes also found no substantive violations.
The shared admin base removes duplicated authorization behavior; its small
Restaurant-specific scoping branch is justified by that model's tenant identity.

## Spec

The initial review found two verified gaps:

1. **P1 — Account administration bypassed the owner/tenant rule.** Staff-role
   accounts with ordinary Django admin permissions could view/change another
   Restaurant. This violated the approved owner-only business access and tenant
   isolation rules. Fixed with the owner-only admin site and shared scoped
   Restaurant/User administrators.
2. **P2 — Administrative related choices leaked other tenants.** Global restaurant
   filters exposed names, and StockIn's received-by selector exposed foreign
   usernames. Fixed by removing global tenant filters and scoping all relevant
   ingredient, restaurant and received-by choices.

New regression tests reproduce the nonsuperuser permission cases. The follow-up
spec reviewer confirmed both findings resolved and found no newly introduced
substantive issues. No remaining functional gaps or scope creep were identified
in menu lifecycle, formset validation, unit protection, deletion transactions or
the shared POS/reporting read interface.

Summary: Standards — 0 findings; Spec — 2 findings fixed, 0 remaining.

## Final verification

- Full Django suite: 94 tests discovered, 93 passed and one optional browser test
  skipped in the normal run. That browser test passed separately using Edge.
- Overall accounts/inventory/menus statement coverage: **93.56%**; the configured
  project threshold is strictly above 80%.
- Optional browser verification: dynamic add/remove, saved cost, explicit
  activation, duplicate-error recovery and a 390px mobile layout; no page errors.
- Mypy: 27 non-test source files pass basic type checking.
- Ruff checks, Python compilation, JavaScript syntax and Django system checks pass.
- Migration drift check reports no changes. Migrations applied to the local
  development database. A regression test verifies legacy zero-price upgrades
  stop without inventing prices and succeed after legitimate correction.
- All work and ticket updates are local. No push, PR or external tracker change
  was performed as part of implementation. The original local main branch was
  left unchanged; the implementation branch was fast-forwarded to the baseline.

The local CI workflow is provided for future authorized PRs; it has not been
executed remotely. Course-required human peer approval remains part of that
future PR workflow and is not claimed by these automated reviews.
