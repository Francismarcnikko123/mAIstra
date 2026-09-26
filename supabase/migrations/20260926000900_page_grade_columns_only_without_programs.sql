-- Fix for review finding #4
-- (docs/reviews/2026-09-26-judge0-integration-code-review.md).
--
-- Since 20260926000600 a page's programs are graded on their
-- submission_programs rows by save_program_grade(), and the page becomes
-- 'graded' once every program is. The page row's own grade columns were never
-- updated on that path, so a 'graded' page could show no grade, or the older
-- grade that 20260926000600 copied into Program 1 but also left on the page.
--
-- Decision: the page row's grade columns are used only for pages that have no
-- submission_programs rows (the legacy save_submission_grade() path). For a
-- page with programs they stay empty. save_program_grade() is deliberately
-- NOT changed to write them: that would advance the page's grading_revision
-- (advance_grading_revision_on_grade) and make the teacher's next save of the
-- tabs report a conflict.

-- ── Existing data: clear the page-level grade of pages with programs ─────
-- One-time. advance_grading_revision_on_grade advances these pages'
-- grading_revision, so a review opened before this migration saves as a
-- conflict once and is re-read. Only rows that still hold a grade are touched.
UPDATE public.submissions AS page
SET
  grading_results = '[]'::jsonb,
  passed_test_cases = NULL,
  total_test_cases = NULL,
  graded_at = NULL
WHERE EXISTS (
    SELECT 1 FROM public.submission_programs AS program
    WHERE program.submission_id = page.id
  )
  AND (
    page.grading_results IS DISTINCT FROM '[]'::jsonb
    OR page.passed_test_cases IS NOT NULL
    OR page.total_test_cases IS NOT NULL
    OR page.graded_at IS NOT NULL
  );

-- ── The legacy page-level save refuses pages with programs ──────────────
-- Same as in 20260924000000, plus: nothing is written and NULL is returned
-- when the page has any submission_programs row; those pages are graded per
-- program through save_program_grade(). A program row added concurrently is
-- caught by the grading_revision check: save_submission_programs() advances
-- the page's revision whenever it inserts one.
CREATE OR REPLACE FUNCTION public.save_submission_grade(
  p_submission_id uuid,
  p_grading_revision bigint,
  p_question_id uuid,
  p_graded_code text,
  p_grading_results jsonb
)
RETURNS bigint
LANGUAGE sql
SECURITY INVOKER
SET search_path = ''
AS $$
  UPDATE public.submissions
  SET
    grading_results = p_grading_results,
    passed_test_cases = (
      SELECT count(*)::integer
      FROM jsonb_array_elements(p_grading_results) AS result
      WHERE (result ->> 'passed')::boolean
    ),
    total_test_cases = jsonb_array_length(p_grading_results),
    graded_at = now(),
    status = 'graded'
  WHERE id = p_submission_id
    AND grading_revision = p_grading_revision
    AND question_id = p_question_id
    AND verified_text = p_graded_code
    AND NOT EXISTS (
      SELECT 1 FROM public.submission_programs AS program
      WHERE program.submission_id = p_submission_id
    )
  RETURNING grading_revision;
$$;

REVOKE ALL ON FUNCTION public.save_submission_grade(uuid, bigint, uuid, text, jsonb)
FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.save_submission_grade(uuid, bigint, uuid, text, jsonb)
TO anon, authenticated;

-- ── What the page-level grade columns mean now ──────────────────────────
COMMENT ON COLUMN public.submissions.grading_results IS
  'Page-level grade, used only for pages without submission_programs rows (written by save_submission_grade()). Empty for pages with programs: per-program grades live on submission_programs.';
COMMENT ON COLUMN public.submissions.passed_test_cases IS
  'Page-level grade, used only for pages without submission_programs rows (written by save_submission_grade()). NULL for pages with programs: per-program grades live on submission_programs.';
COMMENT ON COLUMN public.submissions.total_test_cases IS
  'Page-level grade, used only for pages without submission_programs rows (written by save_submission_grade()). NULL for pages with programs: per-program grades live on submission_programs.';
COMMENT ON COLUMN public.submissions.graded_at IS
  'Page-level grade time, used only for pages without submission_programs rows (written by save_submission_grade()). NULL for pages with programs: per-program grades live on submission_programs.';
