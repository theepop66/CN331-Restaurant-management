# 01: [US-03] Restrict business screens to restaurant owners

**What to build:** An authenticated restaurant owner can use the existing business screens for their restaurant. Anonymous users must sign in, authenticated nonowners receive a clear refusal, and accounts without a restaurant receive the established redirect. This supplies one reusable access rule for the menus workflow and carries the approved owner-only scope into existing business screens. Public registration and login keep working.

**Blocked by:** None (can start immediately)

**Status:** done

- [x] An owner assigned to a restaurant can reach existing home and inventory business screens and perform permitted inventory actions.
- [x] Anonymous business requests require sign-in; authenticated staff cannot view or mutate business records, including through direct URLs and forged requests.
- [x] An authenticated user without a restaurant receives a safe explanation/redirect without data disclosure or a redirect loop.
- [x] Shared access handling uses the authenticated account's role and restaurant; submitted restaurant identifiers cannot grant access.
- [x] Existing restaurant isolation, CSRF protection and public authentication flows remain intact. No role migration or staff workflow is introduced.
- [x] The owner interface displays appropriate navigation/messages. Existing tests expecting staff business access are updated to match the approved scope.
- [x] Request-level tests exercise owner, anonymous, staff, no-restaurant and cross-restaurant cases, including unchanged state after denied writes.
- [x] Added or changed owner-facing behavior is traceable to US-03/UC-03, while existing feature references are preserved. Coordinate shared auth changes with US-01/02 and the owner-only POS contract with US-04 without changing their parent issues.
