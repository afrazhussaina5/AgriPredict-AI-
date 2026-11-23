# Repository-level tests

**Status:** reserved — empty on purpose.

This folder is the home for **end-to-end (E2E) and cross-application integration
tests** that exercise the frontend and the backend together (Phase 16 of the
implementation plan).

- Backend unit/integration tests live in [`apps/api/tests`](../apps/api/tests).
- Frontend unit tests live next to the source in [`apps/web/src`](../apps/web/src).

Nothing is fabricated here: when E2E tooling is added, it will run against a
real local backend with labelled test fixtures only.
