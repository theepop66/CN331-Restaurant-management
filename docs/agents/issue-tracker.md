# Issue tracker

Use local Markdown files. The user's latest instruction supersedes the earlier
GitHub publication approval: save the US-03 spec and tickets locally only.

Canonical feature folder: .scratch/us-03/
Specification: .scratch/us-03/spec.md
Tickets: one file per ticket under .scratch/us-03/issues/, numbered 01 through 06
in dependency order. The feature README is the local index.

Each ticket declares What to build, Blocked by, Status: ready-for-agent and its
acceptance criteria. Blocking edges use local ticket numbers and titles, not
GitHub issue identifiers. Start only tickets whose blockers are complete.

Do not create, edit, close, label or link external issues unless the user
explicitly authorizes a new external action. Do not treat the earlier publication
approval as authorization after the local-only instruction.

Historical cleanup: the user explicitly requested closure of the spec and six
issues created before the local-only instruction. Generated GitHub issues 9-15
were closed; the original US-03 parent issue 4 remains open and unchanged.

PRs as a request surface: off.

This records the local tracker choice. It does not configure unrelated domain
documentation or other triage workflows.
