-- One row per teacher-verified program on a photographed page, Program 1
-- included (Nombrado's proposal,
-- docs/superpowers/specs/2026-09-26-submission-programs-table-proposal.md,
-- as decided in docs/TEAM_SYNC.md on 2026-09-26).
--
-- submissions stays the page: photo, raw whole-page OCR, workflow status.
-- Program 1 is still mirrored to submissions.verified_text / question_id so
-- the OCR export and the list keep working; grades live here, per program.
-- Replaces the submissions.answers jsonb column, which is dropped below.

CREATE TABLE public.submission_programs (
  id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  submission_id     uuid NOT NULL
    REFERENCES public.submissions (id) ON DELETE CASCADE,
  -- Tab order: 1 = Program 1.
  position          smallint NOT NULL CHECK (position >= 1),
  -- RESTRICT: a question with verified programs can't be deleted, so a
  -- program never silently loses the question it is graded against.
  question_id       uuid NOT NULL
    REFERENCES public.questions (id) ON DELETE RESTRICT,
  verified_text     text NOT NULL CHECK (btrim(verified_text) <> ''),
  grading_results   jsonb NOT NULL DEFAULT '[]'::jsonb,
  passed_test_cases integer,
  total_test_cases  integer,
  score_percent     numeric(5, 2) GENERATED ALWAYS AS (
    CASE
      WHEN total_test_cases IS NULL OR total_test_cases = 0 THEN NULL
      ELSE round(passed_test_cases::numeric * 100 / total_test_cases, 2)
    END
  ) STORED,
  graded_at         timestamptz,
  grading_revision  bigint NOT NULL DEFAULT 0,
  created_at        timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT submission_programs_position_key UNIQUE (submission_id, position),
  -- Deferred so one save can swap two tabs' questions.
  CONSTRAINT submission_programs_question_key UNIQUE (submission_id, question_id)
    DEFERRABLE INITIALLY DEFERRED,
  CONSTRAINT submission_programs_grade_counts_check CHECK (
    (passed_test_cases IS NULL AND total_test_cases IS NULL)
    OR (
      passed_test_cases IS NOT NULL
      AND total_test_cases IS NOT NULL
      AND passed_test_cases >= 0
      AND total_test_cases > 0
      AND passed_test_cases <= total_test_cases
    )
  )
);

-- Postgres does not index foreign keys by itself; the (submission_id, ...)
-- unique constraints already cover lookups by submission.
CREATE INDEX submission_programs_question_id_idx
  ON public.submission_programs (question_id);

COMMENT ON TABLE public.submission_programs IS
  'Each teacher-verified program on a photographed page, in tab order, with its own question and grade. Program 1 is position 1.';
COMMENT ON COLUMN public.submission_programs.verified_text IS
  'Teacher-verified code of this program. The raw OCR of the whole page stays in submissions.extracted_text.';

-- ── Stale-grade protection, as on submissions ───────────────────────────
-- Changing a program's code or question clears its grade and advances its
-- revision; a grade write advances the revision exactly once.

CREATE FUNCTION public.invalidate_program_grade()
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
  END IF;
  RETURN NEW;
END;
$$;

CREATE TRIGGER invalidate_program_grade_on_input_change
BEFORE UPDATE OF question_id, verified_text
ON public.submission_programs
FOR EACH ROW
EXECUTE FUNCTION public.invalidate_program_grade();

CREATE FUNCTION public.advance_program_revision_on_grade()
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

CREATE TRIGGER advance_program_revision_on_grade
BEFORE UPDATE OF grading_results, passed_test_cases, total_test_cases, graded_at
ON public.submission_programs
FOR EACH ROW
EXECUTE FUNCTION public.advance_program_revision_on_grade();

REVOKE ALL ON FUNCTION public.invalidate_program_grade()
  FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.advance_program_revision_on_grade()
  FROM PUBLIC, anon, authenticated;

-- A page is 'graded' only when every program on it is graded; otherwise a
-- 'graded' page goes back to 'verified'. Pages that aren't verified or
-- graded yet are left alone.
CREATE FUNCTION public.sync_page_graded_status(p_submission_id uuid)
RETURNS void
LANGUAGE sql
SECURITY INVOKER
SET search_path = ''
AS $$
  UPDATE public.submissions AS page
  SET status = CASE
    WHEN EXISTS (
      SELECT 1 FROM public.submission_programs p
      WHERE p.submission_id = page.id
    )
    AND NOT EXISTS (
      SELECT 1 FROM public.submission_programs p
      WHERE p.submission_id = page.id AND p.graded_at IS NULL
    ) THEN 'graded'
    ELSE 'verified'
  END
  WHERE page.id = p_submission_id
    AND page.status IN ('verified', 'graded');
$$;

-- Editing a question's test cases or type now also clears the grades of
-- every program linked to it (Programs 2+ included), and un-grades their
-- pages. Replaces the version from 20260926000400.
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

  UPDATE public.submissions
  SET status = 'verified'
  WHERE status = 'graded'
    AND id IN (
      SELECT submission_id FROM public.submission_programs
      WHERE question_id = NEW.id
    );

  RETURN NULL;
END;
$$;

-- ── Saving the review: every program of a page in one call ──────────────
-- supabase-js can't run a multi-table transaction, so the review calls this
-- instead of separate writes. SECURITY INVOKER: the caller's grants and RLS
-- stay in force, and the triggers above still run.
--
-- p_programs: [{ "verified_text": text, "question_id": uuid }, ...] in tab
-- order, Program 1 first. Program 1 without a question_id uses the page's
-- question (chosen on the Details step). An entry without code or without a
-- question is not stored (it can't be graded) but keeps its tab number.
-- p_replace_all: true when p_programs is every tab of the page, so programs
-- beyond it are deleted; false to save only the programs given (Program 1
-- alone, when the paper has no tabs) and leave the others as they are.
-- Writes nothing and returns NULL when the page's grading_revision is no
-- longer p_grading_revision (someone else saved it meanwhile); otherwise
-- returns the page's new grading_revision.
CREATE FUNCTION public.save_submission_programs(
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

  PERFORM public.sync_page_graded_status(p_submission_id);

  RETURN v_revision;
END;
$$;

-- ── Saving one program's grade ───────────────────────────────────────────
-- Same compare-and-set as save_submission_grade(): written only while the
-- program's revision, question and stored code all still match. Returns the
-- program's new grading_revision, or NULL when anything differs.
CREATE FUNCTION public.save_program_grade(
  p_program_id uuid,
  p_grading_revision bigint,
  p_question_id uuid,
  p_graded_code text,
  p_grading_results jsonb
)
RETURNS bigint
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path = ''
AS $$
DECLARE
  v_revision bigint;
  v_submission_id uuid;
BEGIN
  UPDATE public.submission_programs
  SET
    grading_results = p_grading_results,
    passed_test_cases = (
      SELECT count(*)::integer
      FROM jsonb_array_elements(p_grading_results) AS result
      WHERE (result ->> 'passed')::boolean
    ),
    total_test_cases = jsonb_array_length(p_grading_results),
    graded_at = now()
  WHERE id = p_program_id
    AND grading_revision = p_grading_revision
    AND question_id = p_question_id
    AND verified_text = p_graded_code
  RETURNING grading_revision, submission_id INTO v_revision, v_submission_id;

  IF v_revision IS NULL THEN
    RETURN NULL;
  END IF;

  PERFORM public.sync_page_graded_status(v_submission_id);
  RETURN v_revision;
END;
$$;

REVOKE ALL ON FUNCTION public.save_submission_programs(uuid, bigint, jsonb, text, boolean)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.save_submission_programs(uuid, bigint, jsonb, text, boolean)
  TO anon, authenticated;
REVOKE ALL ON FUNCTION public.save_program_grade(uuid, bigint, uuid, text, jsonb)
  FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.save_program_grade(uuid, bigint, uuid, text, jsonb)
  TO anon, authenticated;
-- The two save functions run as the caller and call this helper. Calling it
-- directly only recomputes a page's status from its programs.
REVOKE ALL ON FUNCTION public.sync_page_graded_status(uuid) FROM PUBLIC;
GRANT EXECUTE ON FUNCTION public.sync_page_graded_status(uuid)
  TO anon, authenticated;

-- ── Security: same no-login model as 20260921000000_lock_down_public_api ─

ALTER TABLE public.submission_programs ENABLE ROW LEVEL SECURITY;

CREATE POLICY submission_programs_public_select
  ON public.submission_programs
  FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY submission_programs_public_insert
  ON public.submission_programs
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (
    position BETWEEN 1 AND 50
    AND length(verified_text) <= 50000
    AND grading_results = '[]'::jsonb
    AND passed_test_cases IS NULL
    AND total_test_cases IS NULL
    AND graded_at IS NULL
  );

CREATE POLICY submission_programs_public_update
  ON public.submission_programs
  FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (
    position BETWEEN 1 AND 50
    AND length(verified_text) <= 50000
    AND jsonb_typeof(grading_results) = 'array'
  );

CREATE POLICY submission_programs_public_delete
  ON public.submission_programs
  FOR DELETE
  TO anon, authenticated
  USING (true);

REVOKE ALL ON TABLE public.submission_programs FROM anon, authenticated;
GRANT SELECT ON TABLE public.submission_programs TO anon, authenticated;
GRANT INSERT (submission_id, position, question_id, verified_text)
  ON TABLE public.submission_programs TO anon, authenticated;
-- Grade columns are granted for the SECURITY INVOKER save_program_grade(),
-- as they are on submissions for save_submission_grade().
GRANT UPDATE (
  question_id,
  verified_text,
  grading_results,
  passed_test_cases,
  total_test_cases,
  graded_at
) ON TABLE public.submission_programs TO anon, authenticated;
GRANT DELETE ON TABLE public.submission_programs TO anon, authenticated;

-- ── Existing data ────────────────────────────────────────────────────────
-- Program 1 of every page that has verified code and a question, keeping
-- the grade it already has.
INSERT INTO public.submission_programs (
  submission_id, position, question_id, verified_text,
  grading_results, passed_test_cases, total_test_cases, graded_at
)
SELECT
  s.id, 1, s.question_id, s.verified_text,
  s.grading_results, s.passed_test_cases, s.total_test_cases, s.graded_at
FROM public.submissions s
WHERE s.question_id IS NOT NULL
  AND btrim(coalesce(s.verified_text, '')) <> '';

-- Programs 2+ from the answers column (empty in the cloud; kept for local
-- databases that already have some). Invalid entries, questions that no
-- longer exist, and a question already used on the same page are skipped.
INSERT INTO public.submission_programs (submission_id, position, question_id, verified_text)
SELECT DISTINCT ON (candidate.submission_id, candidate.question_id)
  candidate.submission_id, candidate.position, candidate.question_id, candidate.code
FROM (
  SELECT
    s.id AS submission_id,
    (entry.ordinality + 1)::smallint AS position,
    (entry.value ->> 'question_id')::uuid AS question_id,
    entry.value ->> 'code' AS code
  FROM public.submissions s
  CROSS JOIN LATERAL jsonb_array_elements(
    CASE WHEN jsonb_typeof(s.answers) = 'array' THEN s.answers ELSE '[]'::jsonb END
  ) WITH ORDINALITY AS entry
  WHERE jsonb_typeof(entry.value) = 'object'
    AND btrim(coalesce(entry.value ->> 'code', '')) <> ''
    AND (entry.value ->> 'question_id') ~* '^[0-9a-f-]{36}$'
) AS candidate
WHERE EXISTS (
    SELECT 1 FROM public.questions q WHERE q.id = candidate.question_id
  )
  AND NOT EXISTS (
    SELECT 1 FROM public.submission_programs p
    WHERE p.submission_id = candidate.submission_id
      AND p.question_id = candidate.question_id
  )
ORDER BY candidate.submission_id, candidate.question_id, candidate.position;

ALTER TABLE public.submissions DROP COLUMN IF EXISTS answers;
