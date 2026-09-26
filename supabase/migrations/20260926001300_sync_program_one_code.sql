-- Close the Program 1 mirror gap (docs/TEAM_SYNC.md, Jayrald's To do,
-- 2026-09-27, from Nombrado).
--
-- Program 1 is mirrored on the page row as submissions.verified_text /
-- question_id. The browser may still UPDATE submissions.verified_text
-- directly (an older branch, or main, saves code with a plain PATCH), and
-- sync_program_one_with_page (20260926000700) only followed question_id, so
-- Program 1's submission_programs row kept the old code and was graded on it.
--
-- Now Program 1 follows the page's code as well as its question:
--   * question cleared                 -> Program 1 is deleted (as before);
--   * code changed to NULL / blank     -> Program 1 is deleted (it can't be
--                                         graded without code);
--   * Program 1 exists                 -> it takes the new question and, if
--                                         the page's code changed, the new
--                                         code; invalidate_program_grade then
--                                         clears its grade;
--   * no Program 1, question and code  -> Program 1 is created (as before).
-- A question-only change still leaves Program 1's code alone.
--
-- The page revision: the page's own invalidate_submission_grade BEFORE
-- trigger already advances it when question_id or verified_text changes, and
-- advance_page_revision_on_program_change (20260926001200) skips the program
-- writes made here (pg_trigger_depth() > 1), so a plain PATCH still returns
-- the page's final revision. save_submission_programs() is unchanged: its
-- page UPDATE now brings Program 1 in step here, and its own write to
-- position 1 then finds nothing to change.
--
-- The browser's UPDATE grant on submissions.verified_text is kept on
-- purpose: the web's fallback for databases without submission_programs
-- still uses it.

CREATE OR REPLACE FUNCTION public.sync_program_one_with_page()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_code_changed boolean := OLD.verified_text IS DISTINCT FROM NEW.verified_text;
  v_has_code boolean := btrim(coalesce(NEW.verified_text, '')) <> '';
BEGIN
  IF NEW.question_id IS NULL OR (v_code_changed AND NOT v_has_code) THEN
    DELETE FROM public.submission_programs
    WHERE submission_id = NEW.id AND position = 1;
  ELSIF EXISTS (
    SELECT 1 FROM public.submission_programs
    WHERE submission_id = NEW.id AND position = 1
  ) THEN
    UPDATE public.submission_programs
    SET
      question_id = NEW.question_id,
      verified_text = CASE WHEN v_code_changed THEN NEW.verified_text ELSE verified_text END
    WHERE submission_id = NEW.id
      AND position = 1
      AND (
        question_id IS DISTINCT FROM NEW.question_id
        OR (v_code_changed AND verified_text IS DISTINCT FROM NEW.verified_text)
      );
  ELSIF v_has_code THEN
    INSERT INTO public.submission_programs (submission_id, position, question_id, verified_text)
    VALUES (NEW.id, 1, NEW.question_id, NEW.verified_text);
  END IF;

  PERFORM public.sync_page_graded_status(NEW.id);
  RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.sync_program_one_with_page()
  FROM PUBLIC, anon, authenticated;

DROP TRIGGER IF EXISTS sync_program_one_on_question_change ON public.submissions;
DROP TRIGGER IF EXISTS sync_program_one_on_page_change ON public.submissions;

CREATE TRIGGER sync_program_one_on_page_change
AFTER UPDATE OF question_id, verified_text
ON public.submissions
FOR EACH ROW
WHEN (
  OLD.question_id IS DISTINCT FROM NEW.question_id
  OR OLD.verified_text IS DISTINCT FROM NEW.verified_text
)
EXECUTE FUNCTION public.sync_program_one_with_page();
