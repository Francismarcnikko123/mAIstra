# mAIstra — Project Status Audit (2026-09-02)

## Web update — 2026-09-26

Review Code gained a Save button next to the program tabs (every tab, stays on
the step; Cmd/Ctrl+S). The unsaved prompt is Keep editing / Discard changes and
the footer reads "Continue to grading". Branch `feature/program-tabs-save`,
merged into `feature/pre-extraction`; web tests 120/120. See
[TEAM_SYNC.md](TEAM_SYNC.md).

## Integration update — later 2026-09-24

Pushed `feature/pre-extraction` includes `feature/program-tabs` and the optional
auto-extraction worker plus realtime **Extracting… → Needs review** badge. The
phone-photo, server-off and restart catch-up live checks passed. At that
checkpoint OCR tests were 231/231 and web tests 114/114. The 2026-09-02
tables below remain a dated audit, not a re-audit of every team feature.
Nikko owns mobile `question_id` selection/sending; Jayrald owns the cloud
schema/migrations needed for Nikko's complete flow. See [TEAM_SYNC.md](TEAM_SYNC.md).

## Addendum — 2026-09-24

- Web (Nombrado): **program tabs** built on `feature/program-tabs` (pushed, not merged). A paper can hold several programs, each linked to a question and saved in `submissions.answers`. The migration is not yet applied to the cloud, and grading still covers Program 1 only (Jayrald's follow-up). See `web/WEB_CODEBASE_GUIDE.md`.
- Must-have #4 (similarity/duplicates) is no longer "not implemented anywhere": Jayrald's **unmerged** branch `code-similarity/duplicate` (2026-09-05) adds similarity scans plus `assessments` / `assessment_questions(position)`. Not re-audited; merge status is an open question in `TEAM_SYNC.md`.
- Team coordination now lives in `docs/TEAM_SYNC.md` (tracked).

## Addendum — 2026-09-23

- OCR (Nombrado) is waiting for the new bond paper and yellow pad datasets. No code
  work is pending. See `NEXT_STEPS.md`.
- Security: `a448198` replaced the browser's legacy `service_role` key with a
  publishable key. RLS is enabled on `questions` but **not** on `submissions`,
  which still needs policies (Jayrald/Supabase).
- The open items in the table below were not re-audited in this addendum.

## OCR continuation addendum — 2026-09-17

A conservative derivative of the offline association experiment is now integrated
into live full/banded column ordering through `core/continuation.py`. The FastAPI
backend and web app use it through the normal OCR extraction path. It preserves
every retained detection and abstains when its row-preserving safety checks fail;
it does not correct recognized characters or establish a general continuation
classifier. The measured cohort is small and from one writer, and reserved Example
10 remains outside the live column gate. See [session handoff](../ocr_feature/reports/2026-09-14-continuation-session-handoff.md) for the current scope,
evidence and next work; the dated application audit below remains history.

Cross-checked against two source documents: the team's internal task-division
screenshot, and the official professor-approved must-haves PDF
(`mAIstra - Vision-based Handwritten Assessment Grading and Feedback for
Programming Subjects.pdf`). Every status below was verified against the
actual code, not assumed from memory.

## Task Division

| Task | Owner | Spec detail | Codebase evidence | Status |
|---|---|---|---|---|
| Mobile capture → display → confirm save/discard | Diwa | Capture a photo, show it, let user confirm save/discard | `maistra_mobile/lib/screens/capture_screen.dart`: camera capture → quality check (blur threshold 1300 via Laplacian variance, brightness 60–220, lighting spread 50 across quadrants) → Accept/Discard; Accept disabled on failed quality; uploads to Supabase Storage + `submissions` insert (`status: 'pending'`) | ✅ Done |
| Web — input model answer, save to DB as text | Diwa | Input + save model answer; team annotation: "need to check model answer is running" | `maistra_web/src/app/components/question-form/question-form.ts` saves fields via `saveQuestion()`. `runModelAnswer()`/`validateModelAnswer()` exist and call Judge0Service to compile/execute the model answer against test cases, computing `canPublish` — but the Save button (`question-form.html:178`) only checks `isSaving`, and `save()` (`question-form.ts:204`) never checks `canPublish` or whether validation ran | ❌ Not done as stated — the check exists in code but is not enforced before saving |
| OCR extraction → save as text → editable widget | Nombrado (you) | Extract text, save as text, editable widget | Fine-tuned `PP-OCRv6_medium_rec` pipeline, `core/c_code_cleanup.py` (keyword-only auto-fixes), `extracted_text`/`verified_text` columns kept separate (teacher edits never overwrite the raw OCR record), Ace-based editor in the web widget | ✅ Done |
| Judge0 — retrieve, JSON, compile, display output, check output similarity | Tajanlangit | Output-equivalence check only — nothing about scoring source code itself | `judge0_api/main.py` `/api/judge0/grade-submission`: `final_score = logic(50%) + output(40%) + compilation(10%)`. `logic_checker.py`'s `compare_logic()` is a feature checklist (has `main`/`printf`/assignment, matching operators and numeric constants against the model answer); `output_checker.py`'s `compare_output()` is exact-string match after whitespace/colon normalization | ⚠️ Implemented, but exceeds the assigned scope — a full weighted rubric was built where only output-similarity was asked for |

## Official Must-Haves

| # | Must-have (verbatim intent) | Codebase evidence | Status |
|---|---|---|---|
| 1 | Develop question bank of programming problems with model answer and test cases | Storage/retrieval is solid: `question-form.ts` → `saveQuestion()`, `supabase.ts` → `getQuestions()`, each row carries `model_answer` + `test_cases[]`. But nothing guarantees a stored model answer actually runs/passes its own test cases — same underlying gap as the task-division row above (`canPublish` computed, never enforced) | ⚠️ Partial |
| 2 | Apply OCR to extract text from handwritten C code captured via mobile camera (single **or batch** capture) | Extraction pipeline itself is solid. `capture_screen.dart` only calls `_picker.pickImage(source: ImageSource.camera, ...)` once per invocation — no multi-image/batch flow exists anywhere in `maistra_mobile/lib` | ⚠️ Partial — single capture done, batch capture (explicitly named in the spec) missing |
| 3 | Text-correction algorithm (misread chars, misspellings, formatting), manual editing option, save to code repository | `c_code_cleanup.py` (keyword/header auto-fixes), `c_code_suggestions.py` (function-call misspelling flags needing human approval — removed 2026-09-12 from `feature/reading-order-reassembly` as unused on that branch, see `ocr/OCR_REVIEW_SUGGESTION_AB.md`), Ace editor for manual correction, saved to Supabase (`verified_text`) | ✅ Done (as of this 2026-09-02 audit) |
| 4 | Check similarity of submissions in the repository; identify duplicate submissions by code content/structure; flag duplicates; highlight similarity | Searched the full repo — no cross-submission similarity/duplicate-detection logic exists anywhere. The only "similarity" code is (a) the grading rubric's feature-checklist comparing a single submission against *its own question's model answer* (not against other students), and (b) unrelated OCR-dataset-dedup tooling used only for building training data | ❌ Not implemented at all, and **unassigned** — no task-division bullet covers cross-submission duplicate detection |
| 5 | Compute score using rubric: correctness (Judge0 compilation on test cases), logic & structure, syntax, code readability, similarity to model answer | Shipped formula covers 3 concepts under 3 labels: `compilation_score` (correctness), `logic_result["score"]` (partially stands in for both "logic & structure" and "similarity to model answer"), `output_score` (correctness-adjacent). **Syntax** as a distinct scored dimension does not exist. **Code readability** does not exist anywhere in the codebase | ⚠️ Partial — 2 of 5 named axes (syntax, readability) fully missing, and none of the 5 are cleanly separated as distinct scores |
| 6 | Display feedback: similarity, errors, code readability | `submissions-list.ts` populates `submissionTestResults` (per-test-case pass/fail, actual vs. expected output) and `submissionLogicResults` (the feature checklist), both passed into `<app-judge0>` (`submissions-list.html:276-277`) and rendered (pass/fail counts). Errors are genuinely shown. No similarity feedback (since #4 doesn't exist) and no readability feedback (since it isn't computed in #5) | ⚠️ Partial — errors ✅, similarity ❌, readability ❌ |

## Open Items, Prioritized

| Priority | Item | Owner (per task division) |
|---|---|---|
| 1 | Model-answer validation exists but isn't enforced before save | Diwa |
| 2 | Batch capture missing (explicit spec requirement) | Diwa |
| 3 | Duplicate/similarity-across-submissions detection — unbuilt, unassigned | Nobody currently |
| 4 | Syntax scoring — unbuilt, unassigned | Nobody currently |
| 5 | Code-readability scoring — unbuilt, unassigned | Nobody currently |
| 6 | Tajanlangit's rubric exceeds his literal task wording | Tajanlangit (needs team sign-off, not a bug to fix) |

## Bottom line

Fully clean across both documents: OCR extraction/cleanup/editable-widget
work (Nombrado) and mobile capture/quality-gate work (Diwa). Everything else
has at least a partial gap. The most structurally important finding is that
**items 3–5 in the "Open Items" table are must-haves in the approved spec
that were never assigned to anyone** in the team's own task-division
document — that's a planning gap for the team to resolve explicitly, not
something to silently absorb into any one person's existing scope.
