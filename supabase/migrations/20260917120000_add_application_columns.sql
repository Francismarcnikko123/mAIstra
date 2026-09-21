ALTER TABLE public.questions
  ADD COLUMN IF NOT EXISTS question_type text;

UPDATE public.questions
SET question_type = 'program'
WHERE question_type IS NULL;

ALTER TABLE public.questions
  ALTER COLUMN question_type SET DEFAULT 'program',
  ALTER COLUMN question_type SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.questions'::regclass
      AND conname = 'questions_question_type_check'
  ) THEN
    ALTER TABLE public.questions
      ADD CONSTRAINT questions_question_type_check
      CHECK (question_type IN ('function', 'program'));
  END IF;
END
$$;

ALTER TABLE public.submissions
  ADD COLUMN IF NOT EXISTS topic text,
  ADD COLUMN IF NOT EXISTS question_id uuid;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conrelid = 'public.submissions'::regclass
      AND conname = 'submissions_question_id_fkey'
  ) THEN
    ALTER TABLE public.submissions
      ADD CONSTRAINT submissions_question_id_fkey
      FOREIGN KEY (question_id)
      REFERENCES public.questions (id)
      ON DELETE SET NULL;
  END IF;
END
$$;

CREATE INDEX IF NOT EXISTS submissions_question_id_idx
  ON public.submissions (question_id);
