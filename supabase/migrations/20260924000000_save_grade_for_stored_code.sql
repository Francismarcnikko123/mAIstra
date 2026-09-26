-- A grade must be computed from exactly the code stored in Supabase. The web
-- client sends the code it graded, and the grade is written only while that
-- code, the assigned question and the grading revision all still match the
-- row. It is a function so the (possibly long) source travels in the request
-- body rather than in a URL filter.
--
-- SECURITY INVOKER keeps the caller's column grants and RLS policies in force,
-- and the existing triggers still advance grading_revision on the write.
-- Returns the new grading_revision, or NULL when nothing matched.
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
  RETURNING grading_revision;
$$;

REVOKE ALL ON FUNCTION public.save_submission_grade(uuid, bigint, uuid, text, jsonb)
FROM PUBLIC;

GRANT EXECUTE ON FUNCTION public.save_submission_grade(uuid, bigint, uuid, text, jsonb)
TO anon, authenticated;
