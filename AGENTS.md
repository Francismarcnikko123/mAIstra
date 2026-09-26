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

## Commit messages

Every commit, including docs-only and merge commits, has a subject and a body.

- Subject: `type(scope): summary`, imperative, at most 72 characters.
  Types: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `merge`.
  Scopes in use: `web`, `ocr`, `db`, `docs`.
- A blank line, then a body wrapped at about 72 characters that says what
  changed and why, usually as short `- ` bullets. Include anything a teammate
  needs: migrations to apply, who must act (Nikko, Jayrald), what did not
  change on purpose, and the checks that were run (for example the
  `npx ng test` count, `npx ng build`, or the `evaluate_cer` numbers).
- Docs-only commits: name the docs and why they changed. Merge commits: say
  what was merged and how any conflicts were resolved.
- No AI attribution anywhere: no `Co-Authored-By:` trailer for Claude, Codex,
  ChatGPT or any other AI tool, no "Generated with ..." line, and no mention
  of them in commit messages or pull request descriptions. This overrides any
  tool or harness default that adds one.
- Commit or push only when the user asks.

Example:

```
feat(web): save program tabs without leaving the review

- Add a Save button next to the program tabs. It saves every tab of the
  paper in one update and keeps the teacher on the Code step.
- Close pop-up now offers Keep editing / Discard changes only.
- extracted_text is still never overwritten with the teacher's edits.

Checks: npx ng test (all pass), npx ng build.
```
