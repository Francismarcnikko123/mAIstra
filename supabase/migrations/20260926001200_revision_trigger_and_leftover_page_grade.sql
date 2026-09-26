-- Follow-ups to the 2026-09-26 code review
-- (docs/reviews/2026-09-26-judge0-integration-code-review.md).
--
-- 1. The #4 edge case: a page given code, a question and a page-level grade
--    directly in the database, with no program rows, kept that old grade
--    after the review saved its programs. save_submission_programs() now
--    clears a leftover page-level grade once the page has programs.
--
-- 2. The security-advisor warning: advance_page_revision() was a SECURITY
--    DEFINER function the browser could call. The page revision now moves
--    from a trigger on submission_programs instead (trigger functions can't
--    be called through the API), and the function is dropped.

-- ── Any program change moves the page revision ──────────────────────────
-- A program inserted, deleted, moved, or given new code or a new question
-- makes a save from an older view of the page's tabs a conflict, whoever
-- wrote it. Changes made by another trigger are skipped:
--   * sync_program_one_with_page (the Details step) runs inside the page's
--     own UPDATE, whose question change already advanced the revision, and
--     that UPDATE must return the page's final revision;
--   * invalidate_grades_for_question advances the pages itself;
--   * rows removed by the page's ON DELETE CASCADE.
-- Grade writes (save_program_grade) don't fire it, so grading never makes
-- the teacher's next save a conflict.
CREATE FUNCTION public.advance_page_revision_on_program_change()
RETURNS trigger
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path = ''
AS $$
BEGIN
  IF pg_trigger_depth() > 1 THEN
    RETURN NULL;
  END IF;

  UPDATE public.submissions
  SET grading_revision = grading_revision + 1
  WHERE id = CASE WHEN TG_OP = 'DELETE' THEN OLD.submission_id ELSE NEW.submission_id END;

  RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.advance_page_revision_on_program_change()
  FROM PUBLIC, anon, authenticated;

CREATE TRIGGER advance_page_revision_on_program_change
AFTER INSERT OR DELETE OR UPDATE OF position, question_id, verified_text
ON public.submission_programs
FOR EACH ROW
EXECUTE FUNCTION public.advance_page_revision_on_program_change();

-- ── save_submission_programs(): same as 20260926001100, except the page
-- revision comes from the trigger above and a leftover page-level grade is
-- cleared ────────────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION public.save_submission_programs(
  p_submission_id uuid,
  p_grading_revision bigint,
  p_programs jsonb,
  p_extracted_text text DEFAULT NULL,
  p_replace_all boolean DEFAULT true
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_revision bigint;
  v_page_question uuid;
  v_first jsonb;
  -- p_programs normalised to [{position, question_id, verified_text, keep}];
  -- keep is false for an entry without code or without a question.
  v_wanted jsonb;
  -- Every program kept by this save: [{id, position, question_id,
  -- verified_text}], id null for a new row.
  v_plan jsonb;
BEGIN
  IF jsonb_typeof(p_programs) IS DISTINCT FROM 'array'
    OR jsonb_array_length(p_programs) = 0 THEN
    RAISE EXCEPTION 'p_programs must be a non-empty array'
      USING ERRCODE = '22023';
  END IF;
  v_first := p_programs -> 0;

  -- The page row, with Program 1 mirrored for the list and the OCR export.
  -- A new question here moves Program 1's row to it (sync_program_one_with_page).
  UPDATE public.submissions
  SET
    verified_text = v_first ->> 'verified_text',
    -- Program 1's question is chosen on the Details step; never clear it here.
    question_id = coalesce(nullif(v_first ->> 'question_id', '')::uuid, question_id),
    extracted_text = coalesce(p_extracted_text, extracted_text),
    status = 'verified',
    verified_at = now()
  WHERE id = p_submission_id
    AND grading_revision = p_grading_revision
  RETURNING grading_revision, question_id INTO v_revision, v_page_question;

  IF v_revision IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT jsonb_agg(jsonb_build_object(
    'position', normalised.position,
    'question_id', normalised.question_id,
    'verified_text', normalised.verified_text,
    'keep', btrim(coalesce(normalised.verified_text, '')) <> ''
      AND normalised.question_id IS NOT NULL
  ))
  INTO v_wanted
  FROM (
    SELECT
      entry.ordinality AS position,
      CASE
        WHEN entry.ordinality = 1
          THEN coalesce(nullif(entry.value ->> 'question_id', '')::uuid, v_page_question)
        ELSE nullif(entry.value ->> 'question_id', '')::uuid
      END AS question_id,
      entry.value ->> 'verified_text' AS verified_text
    FROM jsonb_array_elements(p_programs) WITH ORDINALITY AS entry
  ) AS normalised;

  -- Match each kept program to the row it continues, if any.
  WITH wanted AS (
    SELECT *
    FROM jsonb_to_recordset(v_wanted)
      AS wanted(position smallint, question_id uuid, verified_text text, keep boolean)
    WHERE wanted.keep
  ),
  existing AS (
    SELECT program.id, program.position, program.question_id
    FROM public.submission_programs AS program
    WHERE program.submission_id = p_submission_id
  ),
  -- Programs 2+ by question. Each row and each program is used at most once
  -- (a question sent twice is left to submission_programs_question_key).
  by_question AS (
    SELECT DISTINCT ON (pair.position) pair.position, pair.id
    FROM (
      SELECT DISTINCT ON (existing.id) wanted.position, existing.id
      FROM wanted
      JOIN existing ON existing.question_id = wanted.question_id
      WHERE wanted.position > 1
        AND existing.position > 1
      ORDER BY existing.id, wanted.position
    ) AS pair
    ORDER BY pair.position, pair.id
  ),
  -- Program 1, and Programs 2+ with a new question, by tab.
  by_position AS (
    SELECT wanted.position, existing.id
    FROM wanted
    JOIN existing ON existing.position = wanted.position
    WHERE wanted.position = 1
      OR (
        NOT EXISTS (SELECT 1 FROM by_question WHERE by_question.position = wanted.position)
        AND NOT EXISTS (SELECT 1 FROM by_question WHERE by_question.id = existing.id)
      )
  )
  SELECT coalesce(jsonb_agg(jsonb_build_object(
    'id', coalesce(by_question.id, by_position.id),
    'position', wanted.position,
    'question_id', wanted.question_id,
    'verified_text', wanted.verified_text
  )), '[]'::jsonb)
  INTO v_plan
  FROM wanted
  LEFT JOIN by_question ON by_question.position = wanted.position
  LEFT JOIN by_position ON by_position.position = wanted.position;

  -- Rows no kept program continues: those on a tab that was sent and, with
  -- p_replace_all, all of them. Deleted first so their positions are free.
  DELETE FROM public.submission_programs AS program
  WHERE program.submission_id = p_submission_id
    AND NOT EXISTS (
      SELECT 1
      FROM jsonb_to_recordset(v_plan) AS plan(id uuid)
      WHERE plan.id = program.id
    )
    AND (p_replace_all OR program.position <= jsonb_array_length(p_programs));

  -- Matched rows move to their tab and take the sent code and question, in
  -- one statement (positions are checked at its end). The trigger clears a
  -- grade only when the code or question changed; a pure move keeps it.
  UPDATE public.submission_programs AS program
  SET
    position = plan.position,
    question_id = plan.question_id,
    verified_text = plan.verified_text
  FROM jsonb_to_recordset(v_plan)
    AS plan(id uuid, position smallint, question_id uuid, verified_text text)
  WHERE program.id = plan.id
    AND (
      program.position IS DISTINCT FROM plan.position
      OR program.question_id IS DISTINCT FROM plan.question_id
      OR program.verified_text IS DISTINCT FROM plan.verified_text
    );

  INSERT INTO public.submission_programs (submission_id, position, question_id, verified_text)
  SELECT p_submission_id, plan.position, plan.question_id, plan.verified_text
  FROM jsonb_to_recordset(v_plan)
    AS plan(id uuid, position smallint, question_id uuid, verified_text text)
  WHERE plan.id IS NULL;

  -- A page with programs keeps no page-level grade (20260926000900); clear
  -- one left from before it had programs. The grade trigger advances the
  -- page revision.
  UPDATE public.submissions AS page
  SET
    grading_results = '[]'::jsonb,
    passed_test_cases = NULL,
    total_test_cases = NULL,
    graded_at = NULL
  WHERE page.id = p_submission_id
    AND EXISTS (
      SELECT 1 FROM public.submission_programs AS program
      WHERE program.submission_id = p_submission_id
    )
    AND (
      page.grading_results <> '[]'::jsonb
      OR page.passed_test_cases IS NOT NULL
      OR page.total_test_cases IS NOT NULL
      OR page.graded_at IS NOT NULL
    );

  PERFORM public.sync_page_graded_status(p_submission_id);

  -- Program changes advanced the page revision through
  -- advance_page_revision_on_program_change; return the final value.
  SELECT page.grading_revision INTO v_revision
  FROM public.submissions AS page
  WHERE page.id = p_submission_id;

  RETURN v_revision;
END;
$$;

REVOKE ALL ON FUNCTION public.save_submission_programs(uuid, bigint, jsonb, text, boolean)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.save_submission_programs(uuid, bigint, jsonb, text, boolean)
  TO anon, authenticated;

-- Nothing calls it any more.
DROP FUNCTION public.advance_page_revision(uuid);
