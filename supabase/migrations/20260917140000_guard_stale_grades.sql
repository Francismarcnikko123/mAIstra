ALTER TABLE public.submissions
  ADD COLUMN IF NOT EXISTS grading_revision bigint DEFAULT 0 NOT NULL;

CREATE OR REPLACE FUNCTION public.invalidate_submission_grade()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  IF OLD.question_id IS DISTINCT FROM NEW.question_id
    OR OLD.verified_text IS DISTINCT FROM NEW.verified_text THEN
    NEW.grading_revision = OLD.grading_revision + 1;
    NEW.grading_results = '[]'::jsonb;
    NEW.passed_test_cases = NULL;
    NEW.total_test_cases = NULL;
    NEW.graded_at = NULL;

    IF NEW.status = 'graded' THEN
      NEW.status = CASE
        WHEN NEW.verified_text IS NOT NULL THEN 'verified'
        WHEN NEW.extracted_text IS NOT NULL THEN 'extracted'
        ELSE 'pending'
      END;
    END IF;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS invalidate_submission_grade_on_input_change
  ON public.submissions;

CREATE TRIGGER invalidate_submission_grade_on_input_change
BEFORE UPDATE OF question_id, verified_text
ON public.submissions
FOR EACH ROW
EXECUTE FUNCTION public.invalidate_submission_grade();
