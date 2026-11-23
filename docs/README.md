# AgriPredict AI — Documentation Index

| Document | Purpose | Status |
|---|---|---|
| [architecture/milestone_0_discovery.md](architecture/milestone_0_discovery.md) | **Phase 0** — product vision, requirements, ERD, permissions, security posture, phased plan, risks | ✅ Approved |
| [phases/phase_01_foundation.md](phases/phase_01_foundation.md) | **Phase 1** — project foundation, commands, test results, limitations | ⏳ Awaiting review |
| [phases/phase_02_design_system.md](phases/phase_02_design_system.md) | **Phase 2** — design system, app shell, EN/HI/TE localization, state patterns | ⏳ Awaiting review |
| [phases/phase_03_database_backend.md](phases/phase_03_database_backend.md) | **Phase 3** — SQLAlchemy models, Alembic migrations, error handling, isolated test database | ⏳ Awaiting review |
| [phases/phase_04_authentication.md](phases/phase_04_authentication.md) | **Phase 4** — phone OTP, tokens, RBAC, onboarding, auth UI in EN/HI/TE | ⏳ Awaiting review |
| [phases/phase_05_reference_data.md](phases/phase_05_reference_data.md) | **Phase 5** — location and reference data, sourced imports, state→district→mandi cascade | ⏳ Awaiting review |
| [../README.md](../README.md) | Repository overview and quick start | Active |
| [../apps/api/README.md](../apps/api/README.md) | Backend commands and structure | Active |
| [../apps/api/reference_data/README.md](../apps/api/reference_data/README.md) | How to prepare and import a verified reference dataset | Active |
| [../tests/README.md](../tests/README.md) | Purpose of the repository-level (E2E) test folder | Reserved for Phase 16 |

## Conventions

- Each phase writes its own report under `phases/phase_NN_<name>.md`.
- Architecture decisions live under `architecture/`.
- No document ever contains real credentials, connection strings, OTPs, or
  private personal data.
- Data that is simulated or imported is always labelled with its source.
