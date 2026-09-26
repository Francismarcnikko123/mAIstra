-- Review 2026-09-26, finding #7 (docs/reviews/2026-09-26-judge0-integration-code-review.md).
--
-- The browser may update can_publish (20260926000400_allow_question_updates),
-- and the mobile app only offers questions with can_publish = true. A saved
-- change to a question's model answer, test cases or type has not been
-- validated, so it clears can_publish here instead of trusting the client to
-- send false. It is cleared even when the same update sends true: the server
-- can't tell whether the new test cases were run. Marking a question
-- validated is its own update that changes only can_publish, after the
-- content is saved. Updates that leave those three columns as they are (a
-- rename, a new question text) keep can_publish as it is.
CREATE OR REPLACE FUNCTION public.reset_can_publish_on_question_edit()
RETURNS trigger
LANGUAGE plpgsql
SET search_path = ''
AS $$
BEGIN
  IF OLD.model_answer IS DISTINCT FROM NEW.model_answer
    OR OLD.test_cases IS DISTINCT FROM NEW.test_cases
    OR OLD.question_type IS DISTINCT FROM NEW.question_type THEN
    NEW.can_publish = false;
  END IF;
  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.reset_can_publish_on_question_edit()
  FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS reset_can_publish_on_question_edit
  ON public.questions;

-- No column list: the values are compared, so the reset holds however the
-- columns came to change.
CREATE TRIGGER reset_can_publish_on_question_edit
BEFORE UPDATE
ON public.questions
FOR EACH ROW
EXECUTE FUNCTION public.reset_can_publish_on_question_edit();
