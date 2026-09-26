-- Lets the question page edit and re-validate a saved question. Same
-- no-login model as the insert in 20260921000000_lock_down_public_api.sql:
-- validated update, column grants only, still no delete from the API.
-- question_section_items already has its UPDATE grant and policy from
-- 20260926000100_add_question_sections.sql.

DROP POLICY IF EXISTS questions_public_update ON public.questions;

CREATE POLICY questions_public_update
  ON public.questions
  FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (
    question_type = ANY (ARRAY['function'::text, 'program'::text])
    AND length(question_name) BETWEEN 1 AND 200
    AND length(question_text) BETWEEN 1 AND 10000
    AND length(model_answer) BETWEEN 1 AND 50000
    AND jsonb_typeof(test_cases) = 'array'
  );

-- The client must send can_publish = false with any edit to the model
-- answer or test cases that has not passed validation again.
GRANT UPDATE (
  question_name,
  question_text,
  model_answer,
  test_cases,
  question_type,
  can_publish
) ON TABLE public.questions TO anon, authenticated;

-- Grades are computed from a question's test cases and type, so changing
-- either one makes every grade on the linked papers stale. Clear them and
-- advance grading_revision so a grade still being computed against the old
-- test cases is refused by save_submission_grade(). Same reset as
-- invalidate_submission_grade(). Only Program 1 (submissions.question_id)
-- is graded today.
--
-- SECURITY DEFINER because the browser has no UPDATE grant on
-- grading_revision; the function only runs from the trigger below.
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

  RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.invalidate_grades_for_question()
  FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS invalidate_grades_on_question_change
  ON public.questions;

CREATE TRIGGER invalidate_grades_on_question_change
AFTER UPDATE OF test_cases, question_type
ON public.questions
FOR EACH ROW
WHEN (
  OLD.test_cases IS DISTINCT FROM NEW.test_cases
  OR OLD.question_type IS DISTINCT FROM NEW.question_type
)
EXECUTE FUNCTION public.invalidate_grades_for_question();
