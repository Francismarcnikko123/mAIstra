-- Fixes for review findings #1 and #2
-- (docs/reviews/2026-09-26-judge0-integration-code-review.md).
--
-- #1: Program 1's question is chosen on the Details step, which updates
-- only submissions.question_id. Program 1's submission_programs row kept the
-- old question and was graded against it. Now a trigger keeps Program 1 in
-- step with the page's question, however it changes.
--
-- #2: save_submission_programs() was guarded only by the page's
-- grading_revision, which didn't move when a save changed Programs 2+ only,
-- so two teachers could overwrite each other's tabs. Now any change to the
-- programs advances the page's revision too.

-- ── #2: advancing the page revision ────────────────────────────────────
-- The browser has no UPDATE grant on grading_revision, so the invoker-rights
-- save function calls this definer-rights helper. Calling it directly only
-- makes the next save by someone holding the old revision report a conflict.
CREATE FUNCTION public.advance_page_revision(p_submission_id uuid)
RETURNS bigint
LANGUAGE sql
SECURITY DEFINER
SET search_path = ''
AS $$
  UPDATE public.submissions
  SET grading_revision = grading_revision + 1
  WHERE id = p_submission_id
  RETURNING grading_revision;
$$;

REVOKE ALL ON FUNCTION public.advance_page_revision(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.advance_page_revision(uuid) TO anon, authenticated;

-- Same as in 20260926000600, plus: when any program row is inserted, changed
-- or deleted, the page's grading_revision advances and the new value is
-- returned, so a save made from an older view of the tabs is refused.
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
  -- p_programs normalised to [{position, question_id, verified_text}].
  v_wanted jsonb;
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
    'position', entry.ordinality,
    'question_id', CASE
      WHEN entry.ordinality = 1
        THEN coalesce(nullif(entry.value ->> 'question_id', '')::uuid, v_page_question)
      ELSE nullif(entry.value ->> 'question_id', '')::uuid
    END,
    'verified_text', entry.value ->> 'verified_text'
  ))
  INTO v_wanted
  FROM jsonb_array_elements(p_programs) WITH ORDINALITY AS entry;

  -- Update in place rather than delete + insert, so only programs whose code
  -- or question changed lose their grade.
  INSERT INTO public.submission_programs AS program
    (submission_id, position, question_id, verified_text)
  SELECT p_submission_id, wanted.position, wanted.question_id, wanted.verified_text
  FROM jsonb_to_recordset(v_wanted)
    AS wanted(position smallint, question_id uuid, verified_text text)
  WHERE btrim(coalesce(wanted.verified_text, '')) <> ''
    AND wanted.question_id IS NOT NULL
  ON CONFLICT (submission_id, position) DO UPDATE
  SET
    question_id = excluded.question_id,
    verified_text = excluded.verified_text
  WHERE program.question_id IS DISTINCT FROM excluded.question_id
    OR program.verified_text IS DISTINCT FROM excluded.verified_text;
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  v_changed := v_changed + v_rows;

  -- Tabs that were emptied, and (with p_replace_all) tabs that were removed.
  DELETE FROM public.submission_programs AS program
  WHERE program.submission_id = p_submission_id
    AND (
      EXISTS (
        SELECT 1
        FROM jsonb_to_recordset(v_wanted)
          AS wanted(position smallint, question_id uuid, verified_text text)
        WHERE wanted.position = program.position
          AND (btrim(coalesce(wanted.verified_text, '')) = '' OR wanted.question_id IS NULL)
      )
      OR (
        p_replace_all
        AND NOT EXISTS (
          SELECT 1
          FROM jsonb_to_recordset(v_wanted)
            AS wanted(position smallint, question_id uuid, verified_text text)
          WHERE wanted.position = program.position
        )
      )
    );
  GET DIAGNOSTICS v_rows = ROW_COUNT;
  v_changed := v_changed + v_rows;

  IF v_changed > 0 THEN
    v_revision := public.advance_page_revision(p_submission_id);
  END IF;

  PERFORM public.sync_page_graded_status(p_submission_id);

  RETURN v_revision;
END;
$$;

-- ── #1: Program 1 follows the page's question ───────────────────────────
-- A new question moves Program 1 to it (the program trigger then clears its
-- grade); a page with saved code but no Program 1 row gets one; clearing the
-- question removes Program 1, which can't be graded without one. One
-- question per paper still holds: taking another program's question fails
-- at commit (submission_programs_question_key).
CREATE FUNCTION public.sync_program_one_with_page()
RETURNS trigger
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
BEGIN
  IF NEW.question_id IS NULL THEN
    DELETE FROM public.submission_programs
    WHERE submission_id = NEW.id AND position = 1;
  ELSIF EXISTS (
    SELECT 1 FROM public.submission_programs
    WHERE submission_id = NEW.id AND position = 1
  ) THEN
    UPDATE public.submission_programs
    SET question_id = NEW.question_id
    WHERE submission_id = NEW.id
      AND position = 1
      AND question_id IS DISTINCT FROM NEW.question_id;
  ELSIF btrim(coalesce(NEW.verified_text, '')) <> '' THEN
    INSERT INTO public.submission_programs (submission_id, position, question_id, verified_text)
    VALUES (NEW.id, 1, NEW.question_id, NEW.verified_text);
  END IF;

  PERFORM public.sync_page_graded_status(NEW.id);
  RETURN NULL;
END;
$$;

REVOKE ALL ON FUNCTION public.sync_program_one_with_page()
  FROM PUBLIC, anon, authenticated;

CREATE TRIGGER sync_program_one_on_question_change
AFTER UPDATE OF question_id
ON public.submissions
FOR EACH ROW
WHEN (OLD.question_id IS DISTINCT FROM NEW.question_id)
EXECUTE FUNCTION public.sync_program_one_with_page();
