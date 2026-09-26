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
  ELSIF OLD.status = 'graded' AND NEW.status = 'verified' THEN
    NEW.status = OLD.status;
  END IF;

  RETURN NEW;
END;
$$;

CREATE OR REPLACE FUNCTION public.advance_grading_revision_on_grade()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  IF OLD.question_id IS NOT DISTINCT FROM NEW.question_id
    AND OLD.verified_text IS NOT DISTINCT FROM NEW.verified_text
    AND (
      OLD.grading_results IS DISTINCT FROM NEW.grading_results
      OR OLD.passed_test_cases IS DISTINCT FROM NEW.passed_test_cases
      OR OLD.total_test_cases IS DISTINCT FROM NEW.total_test_cases
      OR OLD.graded_at IS DISTINCT FROM NEW.graded_at
    ) THEN
    NEW.grading_revision = OLD.grading_revision + 1;
  END IF;

  RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS advance_grading_revision_on_grade
  ON public.submissions;

CREATE TRIGGER advance_grading_revision_on_grade
BEFORE UPDATE OF grading_results, passed_test_cases, total_test_cases, graded_at
ON public.submissions
FOR EACH ROW
EXECUTE FUNCTION public.advance_grading_revision_on_grade();

REVOKE ALL ON FUNCTION public.advance_grading_revision_on_grade()
FROM PUBLIC, anon, authenticated;
