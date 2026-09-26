# Merge Nombrado's latest pre-extraction; restore `AGENTS.md` and `ocr_feature/` (2026-09-26)

> **Owner:** Nikko. **Please review:** Nombrado (his code), Jayrald (FYI).
> Follows [the first v2 merge](2026-09-26-merge-pre-extraction-and-judge0.md), which used `feature/pre-extraction` as of 2026-09-24 (`d9df182`).

## Why

After v2 was pushed, Nombrado pointed out three problems:

1. `AGENTS.md` was deleted. It came from Jayrald's `7de2372` on `judge0-integration` and was carried over by the merge.
2. `ocr_feature/main.py` was changed. Jayrald's `876880c` (CORS origins) was kept during the merge, and his `ocr_feature/tests/test_api.py` came with it. `ocr_feature/` is Nombrado's.
3. Nikko's `TEAM_SYNC.md` section wasn't updated, and v2 lacked Nombrado's 2026-09-26 work and handoff: 9 commits on `feature/pre-extraction` pushed after the first merge.

## What

- **Merged `origin/feature/pre-extraction` at `0f87354`**: the Save button next to the program tabs (Cmd/Ctrl+S, stays on Step 2), the footer label "Continue to grading", "Save and close" removed from the close prompt, the "Program 1 saved" label fix, the `submission_programs` proposal, the updated `AGENTS.md` and the team handoff.
- **`AGENTS.md` restored** from Nombrado's branch.
- **`ocr_feature/` identical to `feature/pre-extraction`**: his `main.py` (`allow_origins=["*"]`, `allow_credentials=False`), and `tests/test_api.py` removed. Checked with `git diff origin/feature/pre-extraction -- ocr_feature` (empty).
- **`TEAM_SYNC.md`, Nikko's section:** Nombrado's To-dos answered and ticked, status updated to v2, changes in others' code listed, requests added.

## Conflicts resolved, following Nombrado's handoff (section 6)

| File | Resolution |
|---|---|
| `AGENTS.md` | Nombrado's version (restored) |
| `submissions-list.ts` | After saving Details: Jayrald's stricter step check with the `detectChanges()` fix ("keep either copy") |
| `submissions-list.html` | Nombrado's Save area next to the tabs; the old save message under the editor removed |
| `submissions-list.css` | Jayrald's split stylesheet; Nombrado's removal of the old `.save-status` rules applied to `submissions-list.review.css` |
| `submissions-list.spec.ts` | Jayrald's test setup plus Nombrado's "step 3 is rendered" check |
| `PROJECT_OVERVIEW_AND_CHANGES.md` | Both sections kept |

## Changes in Nombrado's code (need his OK)

- **`saveStatusLabel()`** now also covers Jayrald's revision guard: a refused save shows "Changed by someone else. Save again to keep yours" (before, it showed "✓ All programs saved"), and code typed during a save shows "New changes need to be saved". The error style applies to the conflict too.
- **`code-editor.ts`** keeps Jayrald's `readOnly` input on top of Nombrado's version, because Jayrald's `judge0.html` binds `[readOnly]` and the build fails without it.
- **Test** "Cmd/Ctrl+S ignores a running save" fakes the running save with `isSaving` (Jayrald replaced `savingId` with per-paper tracking); the Save test expects the revision argument before the programs.

## Verification

- Web: 289/289 tests (one new test for the conflict label), TypeScript clean, `ng build` passes (warning: review stylesheet 0.6 kB over its warning budget).
- OCR: `test_main`, `test_auto_extract`, `test_c_code_cleanup` pass.
- Mobile: no mobile files changed in this merge.
- `ocr_feature/` identical to Nombrado's branch.

## Open

- **Not pushed:** Nombrado asked to wait (he is still working and a push could conflict); Jayrald is working on the schema.
- Nombrado's OK on the two changes above.
