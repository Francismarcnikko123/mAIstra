-- Fix for review finding #9
-- (docs/reviews/2026-09-26-judge0-integration-code-review.md).
--
-- save_submission_programs() matched the saved tabs to rows by position. The
-- web drops blank tabs, so clearing tab 2 sent Program 3 as position 2: that
-- row's question and code changed (its grade was wiped) and position 3 was
-- deleted, so the unchanged Program 3 lost its grade. Reordering tabs did the
-- same.
--
-- Now Programs 2+ are matched to their rows by question (unique per page): a
-- row whose question is still wanted keeps its id and grade and only moves to
-- its new position; it loses its grade only when its code changes (the
-- invalidate_program_grade trigger). Program 1 is still the row at position 1,
-- which follows the page's question (sync_program_one_with_page).

-- ── Positions can move within one statement ─────────────────────────────
-- A non-deferrable unique constraint is checked row by row, so two tabs could
-- not swap positions in one UPDATE. DEFERRABLE INITIALLY IMMEDIATE checks it
-- at the end of each statement instead; it is still checked before the next
-- statement runs. It is no longer usable as an ON CONFLICT arbiter; nothing
-- uses it as one after this migration.
ALTER TABLE public.submission_programs
  DROP CONSTRAINT submission_programs_position_key,
  ADD CONSTRAINT submission_programs_position_key UNIQUE (submission_id, position)
    DEFERRABLE INITIALLY IMMEDIATE;

-- The invoker-rights save function now moves rows. The UPDATE policy already
-- keeps position between 1 and 50, as for inserts; the browser could already
-- delete and re-insert a program at any position, so this adds nothing new.
GRANT UPDATE (position) ON TABLE public.submission_programs TO anon, authenticated;

-- Same as in 20260926000700 (revision guard, Program 1 mirrored to the page,
-- page revision advanced whenever a program row is inserted, changed, moved or
-- deleted), except for how the tabs are matched to rows:
--   * Program 1 is the row at position 1.
--   * Programs 2+ take the row (other than Program 1's) with the same
--     question, wherever it is; a program whose question is new takes the
--     row already on its tab if no other program took that row (its question
--     changes, so its grade is cleared).
--   * Rows left unmatched are deleted when they sit on a tab that was sent
--     (the tab was emptied, or its program replaced), and, with
--     p_replace_all, wherever they are. With p_replace_all = false, rows
--     beyond the tabs sent are left alone unless a sent program took them.
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
  v_changed bigint := 0;
  v_rows bigint;
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
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  v_changed := v_changed + v_rows;

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
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  v_changed := v_changed + v_rows;

  INSERT INTO public.submission_programs (submission_id, position, question_id, verified_text)
  SELECT p_submission_id, plan.position, plan.question_id, plan.verified_text
  FROM jsonb_to_recordset(v_plan)
    AS plan(id uuid, position smallint, question_id uuid, verified_text text)
  WHERE plan.id IS NULL;
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  v_changed := v_changed + v_rows;

  IF v_changed > 0 THEN
    v_revision := public.advance_page_revision(p_submission_id);
  END IF;

  PERFORM public.sync_page_graded_status(p_submission_id);

  RETURN v_revision;
END;
$$;

REVOKE ALL ON FUNCTION public.save_submission_programs(uuid, bigint, jsonb, text, boolean)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.save_submission_programs(uuid, bigint, jsonb, text, boolean)
  TO anon, authenticated;
