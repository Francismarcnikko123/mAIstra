-- Fix for review finding #5
-- (docs/reviews/2026-09-26-judge0-integration-code-review.md).
--
-- Editing a question's test cases or type clears the grades of every program
-- linked to it, but the page row was only touched when the page itself used
-- the question (submissions.question_id) or was 'graded'. The web listens for
-- realtime UPDATEs on submissions only, so a cleared Program 2+ grade on a
-- page that wasn't 'graded' stayed on screen until a full reload.
--
-- Now every page with a program linked to the question has its
-- grading_revision advanced once. That always fires a realtime UPDATE, and a
-- review opened before the edit gets a conflict on its next save, which is
-- right because the grading inputs changed.

-- Same as in 20260926000600, except the last statement: besides moving
-- 'graded' pages back to 'verified', it advances the revision of every page
-- with a linked program. Pages whose own question_id is the edited question
-- are skipped there: the first statement has already advanced them by one
-- (and already moved them off 'graded'), so they are not advanced twice.
-- The trigger invalidate_grades_on_question_change from 20260926000400 is
-- unchanged and keeps calling this function.
CREATE OR REPLACE FUNCTION public.invalidate_grades_for_question()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  UPDATE public.submissions
  SET
    grading_revision = grading_revision + 1,
    grading_results = '[]'::jsonb,
    passed_test_cases = NULL,
    total_test_cases = NULL,
    graded_at = NULL,
    status = CASE
      WHEN status <> 'graded' THEN status
      WHEN verified_text IS NOT NULL THEN 'verified'
      WHEN extracted_text IS NOT NULL THEN 'extracted'
      ELSE 'pending'
    END
  WHERE question_id = NEW.id;

  UPDATE public.submission_programs
  SET
    grading_revision = grading_revision + 1,
    grading_results = '[]'::jsonb,
    passed_test_cases = NULL,
    total_test_cases = NULL,
    graded_at = NULL
  WHERE question_id = NEW.id;

  -- Once per page, however many of its programs use the question.
  UPDATE public.submissions
  SET
    grading_revision = grading_revision + 1,
    status = CASE WHEN status = 'graded' THEN 'verified' ELSE status END
  WHERE question_id IS DISTINCT FROM NEW.id
    AND id IN (
      SELECT submission_id FROM public.submission_programs
      WHERE question_id = NEW.id
    );

  RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.invalidate_grades_for_question()
  FROM PUBLIC, anon, authenticated;
