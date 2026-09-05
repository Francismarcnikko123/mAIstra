# Student Code Similarity Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Compare verified C submissions for the same assessment and question across participating block sections, then show optional, evidence-based similarity findings inside Run & grade.

**Architecture:** Supabase stores assessment/roster relationships, verified-code versions, group scan records, and canonical submission-pair results. A separate Python similarity module parses C with Tree-sitter, selects candidate matches with deterministic Winnowing fingerprints, and calculates non-overlapping matching token passages; FastAPI loads and persists the scoped group. Angular assigns submission metadata, starts a scan after a successful verified-code save, and renders summaries plus on-demand side-by-side evidence without coupling similarity to the grade.

**Tech Stack:** PostgreSQL/Supabase migrations and pgTAP, Python 3/FastAPI/Tree-sitter/httpx, Angular 21/TypeScript/Vitest.

**Implementation discipline:** Use `@superpowers:test-driven-development` for
Tasks 2-9 and `@superpowers:verification-before-completion` for Task 10.

---

## Scope and implementation rules

- Work on the existing `code-similarity/duplicate` branch, as requested.
- Preserve all unrelated uncommitted changes. Stage only paths named by the
  current task before each commit.
- `judge0_api/main.py`, `judge0_api/.env.example`, and
  `maistra_web/src/environment.ts` already contain unrelated edits. Review
  their diffs before and after modification and hunk-stage only the similarity
  additions; never stage those whole files into a feature commit.
- The comparison group is exactly `(assessment_id, question_id)`. Do not add
  `block_section_id` to the group filter; different participating sections are
  intentionally compared.
- Compare only persisted `verified_text` from current answers. Exclude raw OCR
  text, unsaved editor content, model answers, and generated Judge0 harnesses.
- Exclude pairs belonging to the same `student_id`, including replacement
  uploads. Use stable IDs; names are display fields only.
- Similarity findings do not affect `final_score`, submission status, grading,
  or the ability to finish review.
- Exact and normalized duplicates are always reported. For the first
  evaluation baseline, use five-token k-grams, a four-k-gram Winnowing window,
  twelve-token minimum matching blocks, and a 60% maximum-side coverage review
  threshold. Keep these named constants and record them with the algorithm
  version so evaluation can change them without rewriting the pipeline.
- Mark non-duplicate programs with fewer than 20 comparable tokens as
  `insufficient_evidence` instead of clearing or flagging them.
- This plan supports trusted/local development. Production use remains blocked
  by the repository's existing authentication, RLS, and exposed service-role
  issues documented in `docs/PROJECT_OVERVIEW_AND_CHANGES.md`; the new API must
  never return groups other than the one resolved from the requested
  submission ID.
- Assessment, section, and student management/import screens are outside this
  feature. The new selectors consume preconfigured rows. Add representative
  local seed records so the complete flow can be exercised.
- Mobile identity selection is deferred until the mobile app has an
  authenticated student or teacher context. Existing uploads remain eligible
  for teacher assignment in the web Details step.

## Milestone 1: Establish trustworthy comparison groups

### Task 1: Record a clean baseline on the current branch

**Files:**
- Inspect: `judge0_api/tests_logic_checker.py`
- Inspect: `judge0_api/tests_judge0_api.py`
- Inspect: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`
- Inspect: `supabase/tests/schema_contract.test.sql`

**Step 1: Record the existing dirty paths**

Run: `git status --short`

Expected: the previously existing Judge0, Angular, environment, migration, and
test changes are listed. Save this output in the task notes and do not stage
those paths unless a later task explicitly modifies the same file.

**Step 2: Run the current Python tests**

Run from `judge0_api`: `python -m pytest tests_logic_checker.py tests_judge0_api.py -q`

Expected: PASS. If it fails, record the exact baseline failure and stop before
changing Python behavior.

**Step 3: Run the current Angular checks**

Run from `maistra_web`: `npx tsc --noEmit`

Run from `maistra_web`: `npm test -- --watch=false`

Run from `maistra_web`: `npm run build -- --configuration development`

Expected: PASS on Windows. If the repository's documented native-package or
Node type problem appears, record it verbatim and run the narrow Vitest files
used by later tasks after fixing only feature-related failures.

**Step 4: Run the current database contract test**

Run from repository root: `supabase test db`

Expected: the existing five pgTAP assertions pass when local Supabase is
running. If Docker/Supabase is unavailable, preserve that limitation and run
the migration verification as soon as the service is available.

No commit is created for this task.

### Task 2: Add assessment, roster, and versioned submission schema

**Files:**
- Create: `supabase/migrations/20260905010000_add_assessment_roster_similarity_schema.sql`
- Modify: `supabase/tests/schema_contract.test.sql`
- Modify: `supabase/seed.sql`

**Step 1: Write failing pgTAP schema tests**

Increase the plan count and add assertions for these contracts:

```sql
select has_table('public', 'assessments');
select has_table('public', 'block_sections');
select has_table('public', 'students');
select has_table('public', 'assessment_questions');
select has_table('public', 'assessment_roster');
select has_column('public', 'submissions', 'assessment_id');
select has_column('public', 'submissions', 'student_id');
select has_column('public', 'submissions', 'block_section_id');
select has_column('public', 'submissions', 'verified_version');
select has_column('public', 'submissions', 'is_current');
select has_table('public', 'similarity_scans');
select has_table('public', 'similarity_matches');
```

Also query `pg_constraint` and `pg_indexes` to verify:

- `(assessment_id, question_id)` references `assessment_questions`.
- `(assessment_id, student_id, block_section_id)` references
  `assessment_roster`.
- a partial unique index allows only one current submission for a non-null
  `(assessment_id, question_id, student_id)`.
- the scan lookup index begins with `(assessment_id, question_id)`.

**Step 2: Run the database test to verify it fails**

Run: `supabase test db`

Expected: FAIL because the new tables and columns do not exist.

**Step 3: Create the migration**

Implement these minimum relationships:

```sql
create table public.assessments (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  status text not null default 'draft'
    check (status in ('draft', 'active', 'closed')),
  starts_at timestamptz,
  created_at timestamptz not null default now()
);

create table public.block_sections (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  created_at timestamptz not null default now()
);

create table public.students (
  id uuid primary key default gen_random_uuid(),
  student_number text not null unique,
  display_name text not null,
  created_at timestamptz not null default now()
);

create table public.assessment_questions (
  assessment_id uuid not null references public.assessments(id) on delete cascade,
  question_id uuid not null references public.questions(id) on delete restrict,
  starter_code text not null default '',
  position integer not null default 1 check (position > 0),
  updated_at timestamptz not null default now(),
  primary key (assessment_id, question_id)
);

create table public.assessment_roster (
  assessment_id uuid not null references public.assessments(id) on delete cascade,
  student_id uuid not null references public.students(id) on delete restrict,
  block_section_id uuid not null references public.block_sections(id) on delete restrict,
  primary key (assessment_id, student_id),
  unique (assessment_id, student_id, block_section_id)
);
```

Add nullable `assessment_id`, `student_id`, and `block_section_id` columns to
`submissions` so existing records remain reviewable. Add `verified_version
integer not null default 0` and `is_current boolean not null default true`.
Add both composite foreign keys and this index:

```sql
create unique index submissions_one_current_answer_idx
  on public.submissions (assessment_id, question_id, student_id)
  where is_current
    and assessment_id is not null
    and question_id is not null
    and student_id is not null;
```

Add a trigger that increments `verified_version` only when `verified_text`
changes using `IS DISTINCT FROM`. An initial non-null verified value becomes
version 1. Backfill existing non-null verified text to version 1 before enabling
the trigger. Metadata-only saves must not change the version.

Create `similarity_scans` with group IDs, `status` (`checking`, `complete`, or
`failed`), `algorithm_version`, `cohort_fingerprint`, compared/skipped counts,
error text, and timestamps. Create `similarity_matches` with the scan ID,
canonical lower/higher submission IDs, both verified versions, match type,
matched-token count, separate coverage values, and JSONB source ranges. Enforce
`lower_submission_id < higher_submission_id` and one pair per scan.

Add indexes for latest group scans and both submission columns in match rows.
Enable RLS on every new table and grant only the roles already used by the
project. Do not add broad `USING (true)` policies for similarity data.

**Step 4: Add deterministic local seed records**

Add one active assessment, two block sections, three students, one
assessment-question assignment, and roster membership across both sections.
Use fixed UUIDs and `ON CONFLICT DO NOTHING` so repeated local resets are stable.
Do not rewrite existing seed submissions.

**Step 5: Apply and verify the migration**

Run: `supabase db reset`

Run: `supabase test db`

Expected: all pgTAP assertions pass, existing migrations still apply, and the
seed loads without a uniqueness or foreign-key error.

**Step 6: Commit the schema slice**

```bash
git add supabase/migrations/20260905010000_add_assessment_roster_similarity_schema.sql supabase/tests/schema_contract.test.sql supabase/seed.sql
git commit -m "feat(db): add assessment groups for similarity checks"
```

### Task 3: Add typed Supabase context operations to Angular

**Files:**
- Create: `maistra_web/src/app/models/submission.models.ts`
- Modify: `maistra_web/src/app/services/supabase.ts:1-98`
- Modify: `maistra_web/src/app/services/supabase.spec.ts`

**Step 1: Write failing service tests**

Add tests that require:

- `getSubmissionContextOptions()` to load active assessments, assessment
  questions, assessment roster entries with student and section display data.
- `getSubmissions()` to select the new IDs and nested display relationships.
- `updateSubmissionDetails()` to persist topic, assessment, question, student,
  and block section in one update.
- a Supabase error from any operation to be returned or thrown consistently.

Use an object payload in the save assertion:

```ts
expect(update).toHaveBeenCalledWith({
  topic: 'Loops',
  assessment_id: 'assessment-1',
  question_id: 'question-1',
  student_id: 'student-1',
  block_section_id: 'section-b',
});
```

**Step 2: Run the focused tests to verify they fail**

Run from `maistra_web`:
`npx vitest run src/app/services/supabase.spec.ts`

Expected: FAIL because the typed models and context method do not exist and the
current details update accepts positional topic/question arguments.

**Step 3: Define shared TypeScript models**

Export `Assessment`, `BlockSection`, `Student`, `AssessmentQuestion`,
`AssessmentRosterEntry`, `SubmissionQuestion`, and `Submission` interfaces.
The submission model must include:

```ts
assessment_id?: string;
student_id?: string;
block_section_id?: string;
verified_version: number;
is_current: boolean;
```

Keep Supabase's possible one-to-one object-or-array join shape explicit rather
than casting it away.

**Step 4: Implement scoped option loading and detail updates**

Load active assessments for new assignments, but allow the web review to
resolve an already-linked closed assessment by ID. Query assignment
and roster tables by selected assessment when possible rather than loading an
unbounded global roster.

Replace positional `updateSubmissionDetails()` parameters with:

```ts
async updateSubmissionDetails(
  id: string,
  details: {
    topic: string;
    assessment_id: string;
    question_id: string;
    student_id: string;
    block_section_id: string;
  },
): Promise<void>
```

**Step 5: Run focused tests and type checking**

Run: `npx vitest run src/app/services/supabase.spec.ts`

Run: `npx tsc --noEmit`

Expected: PASS.

**Step 6: Commit the Angular data slice**

```bash
git add maistra_web/src/app/models/submission.models.ts maistra_web/src/app/services/supabase.ts maistra_web/src/app/services/supabase.spec.ts
git commit -m "feat(web): load assessment and roster context"
```

### Task 4: Require comparison metadata in the web Details step

**Files:**
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts:17-293`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.html:105-187`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.css:326-490`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts:16-75,485-555`

**Step 1: Write failing component tests**

Add focused tests for:

- Details cannot continue until assessment, question, student, and block
  section are selected.
- changing assessment clears a question/student/section that is not valid in
  the new assessment.
- question choices come from `assessment_questions` for the selected
  assessment.
- student choices come from the selected assessment and block section roster.
- saving passes the five-field object to `updateSubmissionDetails()`.
- opening a legacy submission exposes a clear `Missing comparison details`
  state instead of silently choosing the first option.
- changing any group identity clears grading and similarity state.

**Step 2: Run the focused test to verify it fails**

Run: `npx vitest run src/app/components/submissions-list/submissions-list.spec.ts`

Expected: FAIL on missing fields, filters, and updated service call.

**Step 3: Implement component state and filtering**

Move the local submission interfaces to the shared model file. Add selected
assessment, section, and student IDs plus loaded option collections. Implement
pure helpers:

```ts
getAvailableQuestions(assessmentId: string): SubmissionQuestion[]
getAvailableSections(assessmentId: string): BlockSection[]
getAvailableStudents(assessmentId: string, sectionId: string): Student[]
hasCompleteComparisonContext(): boolean
```

Call `loadSubmissionContextOptions()` during initialization. Preserve existing
save-generation timers and component-destruction guards.

**Step 4: Add Details selectors**

Order the fields as Assessment, Block section, Student, Question, then Topic.
Show a field-specific message for every missing selection. Display assessment
and section in the review header after assignment. Keep all markup inside the
existing `SubmissionsListComponent`.

**Step 5: Persist and reflect all IDs**

Make `continueFromDetails()` require `hasCompleteComparisonContext()`. After a
successful save, update both the list record and `selectedSubmission`, refresh
display relationships, clear obsolete run/similarity results, show the existing
saved confirmation, and enter Review code.

**Step 6: Run focused tests and the Angular build**

Run: `npx vitest run src/app/components/submissions-list/submissions-list.spec.ts`

Run: `npx tsc --noEmit`

Run: `npm run build -- --configuration development`

Expected: PASS, including Angular template compilation.

**Step 7: Commit the Details workflow**

```bash
git add maistra_web/src/app/components/submissions-list/submissions-list.ts maistra_web/src/app/components/submissions-list/submissions-list.html maistra_web/src/app/components/submissions-list/submissions-list.css maistra_web/src/app/components/submissions-list/submissions-list.spec.ts
git commit -m "feat(web): assign submission comparison groups"
```

## Milestone 2: Detect, persist, and review code similarity

### Task 5: Implement C token normalization and starter-code exclusion

**Files:**
- Create: `judge0_api/similarity_checker.py`
- Create: `judge0_api/tests_similarity_checker.py`
- Reuse: `judge0_api/logic_checker.py`

**Step 1: Write failing tokenization tests**

Cover:

- comments and formatting do not change comparable tokens;
- string and number literals are preserved;
- local variables and parameters receive stable per-scope placeholders;
- function names, type names, operators, and library calls remain meaningful;
- source start/end points are retained for every token;
- starter-code passages are excluded without removing identical tokens that
  occur elsewhere in student logic;
- parse errors are returned as analysis metadata rather than hidden.

Example assertion:

```python
left = normalize_c_code("int add(int first, int second) { return first + second; }")
right = normalize_c_code("int add(int x, int y) { return x + y; }")
assert [token.value for token in left.tokens] == [token.value for token in right.tokens]
```

**Step 2: Run the focused tests to verify they fail**

Run from `judge0_api`:
`python -m pytest tests_similarity_checker.py -q`

Expected: FAIL because `similarity_checker.py` does not exist.

**Step 3: Implement typed normalized tokens**

Reuse `C_PARSER`, `node_text()`, and tree walking helpers from
`logic_checker.py`; do not create another C language instance. Define frozen
dataclasses for `SourcePoint`, `SourceRange`, `NormalizedToken`, and
`NormalizedProgram`. Walk leaf tokens, skip comments and preprocessor include
directives, retain punctuation/operators, and bind declared local/parameter
identifiers to deterministic placeholders within each function scope.

**Step 4: Implement base-code exclusion**

Normalize `starter_code`, find its non-overlapping token blocks in each student
program, and mark those token indices excluded. Build comparison segments from
the remaining contiguous tokens so fingerprints and highlights never cross an
excluded starter passage.

**Step 5: Run focused and existing parser tests**

Run:
`python -m pytest tests_similarity_checker.py tests_logic_checker.py -q`

Expected: PASS; existing grading logic remains unchanged.

**Step 6: Commit normalization**

```bash
git add judge0_api/similarity_checker.py judge0_api/tests_similarity_checker.py judge0_api/logic_checker.py
git commit -m "feat(similarity): normalize verified C submissions"
```

### Task 6: Add deterministic Winnowing and matching evidence

**Files:**
- Modify: `judge0_api/similarity_checker.py`
- Modify: `judge0_api/tests_similarity_checker.py`
- Create: `judge0_api/tests/fixtures/similarity/README.md`
- Create: `judge0_api/tests/fixtures/similarity/exact_a.c`
- Create: `judge0_api/tests/fixtures/similarity/exact_b.c`
- Create: `judge0_api/tests/fixtures/similarity/renamed_a.c`
- Create: `judge0_api/tests/fixtures/similarity/renamed_b.c`
- Create: `judge0_api/tests/fixtures/similarity/independent_a.c`
- Create: `judge0_api/tests/fixtures/similarity/independent_b.c`
- Create: `judge0_api/tests/fixtures/similarity/starter.c`

**Step 1: Write failing fingerprint and comparison tests**

Assert:

- exact text returns `exact_duplicate` with 100% coverage;
- comment/format-only changes return `normalized_duplicate`;
- consistent local renaming produces the same normalized sequence;
- stable hashes and selected fingerprints are identical across Python runs;
- fingerprint windows choose the rightmost minimum when minima tie;
- matching blocks do not overlap or double-count tokens;
- a copied block produces separate left/right coverage and valid source ranges;
- different literals reduce the matching evidence;
- starter-only overlap produces no flagged result;
- unrelated correct answers remain below the review threshold;
- short non-duplicates return `insufficient_evidence`;
- parser errors return `partial_analysis`, never `no_match`.

**Step 2: Run the tests to verify they fail**

Run: `python -m pytest tests_similarity_checker.py -q`

Expected: FAIL on missing fingerprint and pair-comparison functions.

**Step 3: Implement Winnowing candidates**

Use a stable digest such as `hashlib.blake2b(..., digest_size=8)` for each
five-token k-gram. Select the rightmost minimum from every four-hash window and
deduplicate identical `(hash, token_index)` selections. Never use Python's
process-randomized `hash()`.

**Step 4: Implement passage matching and classification**

Use `difflib.SequenceMatcher(autojunk=False)` on normalized token values after
candidate selection. Keep non-overlapping blocks of at least 12 tokens,
calculate the union of covered token indices, and map each block back to both
original source ranges. Return:

```python
{
    "match_type": "similar_code",
    "review_recommended": True,
    "matched_token_count": 28,
    "left_coverage": 0.70,
    "right_coverage": 0.62,
    "left_ranges": [...],
    "right_ranges": [...],
    "analysis_state": "complete",
}
```

Classify a pair for review when it is an exact/normalized duplicate or when
`max(left_coverage, right_coverage) >= 0.60` with at least 12 matched tokens.
The score is overlap coverage, never a probability of cheating.

**Step 5: Run the fixture evaluation**

Run: `python -m pytest tests_similarity_checker.py -q`

Expected: PASS for the labeled exact, renamed, starter, and independent
fixtures. If an independent fixture flags, tune named constants and document
the revised values in the fixture README before continuing.

**Step 6: Commit the detector**

```bash
git add judge0_api/similarity_checker.py judge0_api/tests_similarity_checker.py judge0_api/tests/fixtures/similarity
git commit -m "feat(similarity): detect matching C token passages"
```

### Task 7: Add scoped scan persistence and FastAPI routes

**Files:**
- Create: `judge0_api/similarity_repository.py`
- Create: `judge0_api/similarity_service.py`
- Create: `judge0_api/routers/similarity.py`
- Create: `judge0_api/tests_similarity_service.py`
- Create: `judge0_api/tests_similarity_api.py`
- Modify: `judge0_api/main.py:1-50`
- Modify: `judge0_api/requirements.txt`
- Modify: `judge0_api/.env.example`

**Step 1: Write failing orchestration tests with a fake repository**

Test that the service:

- resolves group IDs from the requested submission;
- rejects missing assessment/question/student metadata with HTTP 409 semantics;
- loads current verified/graded answers only for the resolved group;
- includes different sections but excludes same-student pairs;
- processes each unordered pair once;
- stores a complete scan even when no pair crosses the review threshold;
- hashes sorted `submission_id:verified_version` values plus starter-code and
  algorithm version into a cohort fingerprint;
- reports a saved scan as `outdated` when that fingerprint changes;
- marks a stale `checking` scan unavailable after a defined timeout;
- stores failure state without blocking grading.

**Step 2: Run service tests to verify they fail**

Run:
`python -m pytest tests_similarity_service.py tests_similarity_api.py -q`

Expected: FAIL because the repository, service, and routes do not exist.

**Step 3: Implement a repository protocol and Postgres adapter**

Add `psycopg[binary]>=3.2,<4` to requirements and `DATABASE_URL` to
`.env.example`. Keep SQL parameterized. The repository must offer operations
equivalent to:

```python
get_submission_scope(submission_id)
get_group_inputs(assessment_id, question_id)
get_starter_code(assessment_id, question_id)
create_checking_scan(...)
complete_scan(scan_id, matches, counts, fingerprint)
fail_scan(scan_id, message)
get_latest_scan(assessment_id, question_id)
get_match_detail(scan_id, lower_submission_id, higher_submission_id)
```

Write all match rows and the `complete` transition in one transaction. Store
canonical UUID order for every pair. Do not persist raw OCR text.

**Step 4: Implement group scanning**

Set `ALGORITHM_VERSION = "c-tree-sitter-winnowing-v1"`. Prepare each eligible
program once, compare all distinct-student unordered pairs, and persist every
exact/normalized duplicate plus similar pairs crossing the review threshold.
Track skipped pairs from missing code, same student, insufficient evidence, and
partial parsing separately in response metadata.

Before completing, reload the group and recompute the fingerprint. If it
changed, mark the attempt failed/outdated and require a retry; do not publish a
current-looking scan for obsolete inputs.

**Step 5: Implement API routes**

Mount a separate router at `/api/similarity`:

```text
POST /api/similarity/submissions/{submission_id}/scan
GET  /api/similarity/submissions/{submission_id}
GET  /api/similarity/submissions/{submission_id}/matches/{peer_submission_id}
```

The POST resolves the group from `submission_id`; it never accepts arbitrary
assessment/question IDs or browser-supplied code. GET returns one of
`missing_metadata`, `not_checked`, `checking`, `complete`, `outdated`, or
`unavailable`. Match details include both verified code strings and the stored
source ranges only after confirming that both IDs belong to the resolved group
and latest scan.

Return 503 with a clear configuration message when `DATABASE_URL` is absent.
Keep Judge0 endpoints and `compare_logic()` untouched.

**Step 6: Run backend tests**

Run:
`python -m pytest tests_logic_checker.py tests_judge0_api.py tests_similarity_checker.py tests_similarity_service.py tests_similarity_api.py -q`

Expected: PASS.

**Step 7: Commit the backend scan API**

Stage the new files and `requirements.txt` normally. Hunk-stage only the new
similarity-router lines from `main.py` and the new database line from
`.env.example`, then inspect `git diff --cached` before committing:

```bash
git add judge0_api/similarity_repository.py judge0_api/similarity_service.py judge0_api/routers/similarity.py judge0_api/tests_similarity_service.py judge0_api/tests_similarity_api.py judge0_api/requirements.txt
git add -p judge0_api/main.py judge0_api/.env.example
git diff --cached
git commit -m "feat(api): scan scoped submission groups for similarity"
```

### Task 8: Trigger and track similarity checks in Angular

**Files:**
- Create: `maistra_web/src/app/services/similarity.service.ts`
- Create: `maistra_web/src/app/services/similarity.service.spec.ts`
- Modify: `maistra_web/src/environment.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts:69-102,208-260,324-370,443-460,653-686`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`

**Step 1: Write failing API service tests**

Define typed summary/detail models and assert the three methods call the
configured similarity base URL:

```ts
scanSubmission(submissionId: string)
getSubmissionSimilarity(submissionId: string)
getMatchDetail(submissionId: string, peerSubmissionId: string)
```

**Step 2: Run the service test to verify it fails**

Run: `npx vitest run src/app/services/similarity.service.spec.ts`

Expected: FAIL because the service and environment URL do not exist.

**Step 3: Implement the typed API client**

Add `similarityApiUrl: 'http://127.0.0.1:8001/api/similarity'` beside the
existing Judge0 URL. Model separate per-submission coverage and peer display
fields; do not expose a `plagiarismProbability` property.

**Step 4: Write failing component state tests**

Test that:

- successful verified-code save enters Run & grade immediately and starts the
  scan without awaiting it;
- failed code save never starts a scan;
- the scan always uses the submission ID, never editor code;
- scan failure sets `unavailable` but leaves grading and Finish review usable;
- editing code locally marks existing findings outdated;
- saving a newer edit ignores an older scan completion, using a generation
  guard parallel to the existing save guard;
- opening Run & grade loads persisted current state;
- changing assessment/question/student/section clears similarity state.

**Step 5: Implement nonblocking state management**

Inject `SimilarityService`. Maintain state, summary, error, selected peer, and
detail maps keyed by submission ID. Add per-submission scan generations and
destruction checks. After `updateSubmissionText()` succeeds, transition to Run
& grade and call `refreshSimilarity(id, true)` without making scan success a
condition for navigation or grading.

When `updateSubmissionCode()` receives text different from saved
`verified_text`, display `outdated` locally. Reopening the modal calls the GET
summary route. Keep the result if the user changes only topic.

**Step 6: Run focused tests and type checking**

Run:
`npx vitest run src/app/services/similarity.service.spec.ts src/app/components/submissions-list/submissions-list.spec.ts`

Run: `npx tsc --noEmit`

Expected: PASS.

**Step 7: Commit the Angular behavior**

Stage the new service and component files normally. Hunk-stage only the
`similarityApiUrl` addition from the already-modified environment file, inspect
the cached diff, and commit:

```bash
git add maistra_web/src/app/services/similarity.service.ts maistra_web/src/app/services/similarity.service.spec.ts maistra_web/src/app/components/submissions-list/submissions-list.ts maistra_web/src/app/components/submissions-list/submissions-list.spec.ts
git add -p maistra_web/src/environment.ts
git diff --cached
git commit -m "feat(web): run similarity checks after code verification"
```

### Task 9: Render the optional similarity panel in Run & grade

**Files:**
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.html:250-283`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.css:401-661`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.ts`
- Modify: `maistra_web/src/app/components/submissions-list/submissions-list.spec.ts`

**Step 1: Write failing rendering/helper tests**

Test UI/helper behavior for:

- missing metadata;
- not checked and Retry action;
- checking without disabling Judge0;
- no other eligible submissions;
- complete with no significant matches;
- partial analysis with compared/skipped counts;
- outdated findings after edits;
- unavailable with Retry;
- match rows showing peer student, block section, match type, and both coverage
  values;
- expanding a match loads detail once and renders escaped source text with only
  stored ranges highlighted;
- optional review never disables Finish review.

**Step 2: Run the focused test to verify it fails**

Run: `npx vitest run src/app/components/submissions-list/submissions-list.spec.ts`

Expected: FAIL because the panel and highlight helpers do not exist.

**Step 3: Add the panel below the grading context and above Judge0**

Use the heading `Code similarity` and explanatory text `Matching code requires
teacher review and does not change the grade.` Provide live status text,
compared/skipped counts, and Retry. Avoid `cheated`, `plagiarized`, probability,
or automatic penalty language.

Each result row shows the peer's name and block section, `Exact duplicate`,
`Same tokens`, or `Similar code`, `Your answer: N%`, `Other answer: N%`, and an
`Inspect match` button. Load the side-by-side detail only when expanded.

**Step 4: Render source-safe highlighted lines**

Convert stored row/column ranges into a view model of plain text fragments and
render with Angular interpolation inside `<pre><code>`. Do not use
`innerHTML`. Label both student names and sections, preserve line numbers, and
keep the original submission-image link available.

**Step 5: Add responsive styles**

Use the existing card borders, color palette, and breakpoints. Display the two
code panes in columns on wide screens and stack them below 800px. Ensure long
lines scroll within each code pane and do not widen the review modal.

**Step 6: Run focused tests and build**

Run: `npx vitest run src/app/components/submissions-list/submissions-list.spec.ts`

Run: `npx tsc --noEmit`

Run: `npm run build -- --configuration development`

Expected: PASS.

**Step 7: Commit the panel**

```bash
git add maistra_web/src/app/components/submissions-list/submissions-list.html maistra_web/src/app/components/submissions-list/submissions-list.css maistra_web/src/app/components/submissions-list/submissions-list.ts maistra_web/src/app/components/submissions-list/submissions-list.spec.ts
git commit -m "feat(web): show optional similarity evidence in grading"
```

### Task 10: Verify the end-to-end behavior and update documentation

**Files:**
- Modify: `docs/PROJECT_OVERVIEW_AND_CHANGES.md`
- Modify: `docs/setup/SUPABASE_LOCAL_SETUP.md`
- Modify: `docs/plans/2026-09-05-student-code-similarity-design.md`

**Step 1: Run the full automated verification**

Run from repository root: `supabase db reset`

Run from repository root: `supabase test db`

Run from `judge0_api`:
`python -m pytest tests_logic_checker.py tests_judge0_api.py tests_similarity_checker.py tests_similarity_service.py tests_similarity_api.py -q`

Run from `maistra_web`: `npx tsc --noEmit`

Run from `maistra_web`: `npm test -- --watch=false`

Run from `maistra_web`: `npm run build -- --configuration development`

Expected: all available checks pass. Report infrastructure limitations rather
than weakening or deleting tests.

**Step 2: Exercise the cross-section/reused-question scenario manually**

Using local seeded data:

1. Create verified submissions for students in Block A and Block B under the
   same assessment/question.
2. Confirm they appear in one similarity scan and labels include each block.
3. Assign the same `question_id` to a second assessment and verify its answers
   never appear in the first assessment's scan.
4. Save an edited verified answer and confirm both sides of its previous match
   become outdated until the new group scan completes.
5. Stop the similarity API, verify grading remains usable and the panel offers
   Retry, restart it, and retry successfully.
6. Confirm exact, normalized, renamed, starter-only, unrelated, short, and
   parser-error samples display the intended classifications and passages.

**Step 3: Inspect database scope and stale-result evidence**

Query the latest scan and match rows. Confirm each pair uses canonical ID
ordering, saved versions match the compared submissions, no same-student pair
exists, and the cohort fingerprint changes after a verified-text edit.

**Step 4: Update project documentation**

Document:

- assessment/question grouping across block sections;
- verified-text-only comparisons and same-student exclusion;
- algorithm version and evaluation constants;
- every panel state and its meaning;
- `DATABASE_URL` setup for the Python service;
- the fact that similarity evidence does not alter grades or establish intent;
- authentication/RLS as a production deployment requirement.

Change the design status to implemented only after all applicable checks and
manual scenarios pass.

**Step 5: Review the final diff for unrelated changes**

Run: `git status --short`

Run: `git diff --check`

Run: `git diff --stat HEAD~10..HEAD`

Expected: no whitespace errors. Confirm every unrelated pre-existing dirty path
still contains the user's original work.

**Step 6: Commit documentation**

```bash
git add docs/PROJECT_OVERVIEW_AND_CHANGES.md docs/setup/SUPABASE_LOCAL_SETUP.md docs/plans/2026-09-05-student-code-similarity-design.md
git commit -m "docs: explain student code similarity workflow"
```

## Completion criteria

- A submission cannot enter Review code without assessment, question, student,
  and block-section identity.
- Existing mobile uploads can be assigned complete comparison metadata in the
  web Details step before verification.
- The backend derives `(assessment_id, question_id)` from a submission ID and
  compares current verified answers across all participating sections.
- The algorithm reports exact, normalized, and substantial token matches with
  separate coverage and accurate source ranges while excluding starter code.
- Reused questions in different assessments never share a scan.
- New or edited verified answers make previous group results outdated and
  regenerate pair results for both students.
- Run & grade shows optional, source-based evidence; grading and Finish review
  remain independent from similarity availability and findings.
- Automated and manual checks listed above pass, or any environmental blocker
  is reported with the exact command and output.
