# mAIstra project instructions

## Required project context

Before making architectural, data-flow, or submission-workflow changes, read:

- `docs/PROJECT_OVERVIEW_AND_CHANGES.md`
- `docs/setup/JUDGE0_UBUNTU_DOCKER_SETUP.md` when working on Judge0 deployment or connectivity
- `docs/setup/SUPABASE_LOCAL_SETUP.md` when working on local Supabase
- `docs/setup/SUPABASE_CLOUD_LOCAL_SWITCHING.md` when changing Supabase environments

## Project decisions

- Keep submission review inside the existing `SubmissionsListComponent` unless the user explicitly requests additional visual components.
- Preserve original OCR output separately from teacher-edited and verified text.
- Keep save-generation, timer, and component-destruction protections.
- Keep Judge0 results associated with their submission IDs.
- Keep function-question execution helpers that generate the temporary `main()` test harness.
- Require a selected question and verified student code before grading.
- Never expose Supabase service-role keys or other server secrets in browser or mobile code.
- Preserve unrelated user changes in the working tree.

## Verification expectations

After changing Angular application code:

- Run the application TypeScript check.
- Run Angular template compilation when available.
- Run focused tests for the changed behavior.
- If native Node dependencies were installed on another operating system, report that limitation instead of rewriting dependencies without permission.

## Documentation expectations

When behavior, architecture, setup, or security requirements change:

- Update `docs/PROJECT_OVERVIEW_AND_CHANGES.md`.
- Update the relevant guide under `docs/setup/`.
- Keep `README.md` links accurate.
