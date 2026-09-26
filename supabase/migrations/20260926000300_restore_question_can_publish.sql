-- Brings back the "model answer validated" flag dropped in
-- 20260917000000_remove_unused_question_validation_columns.sql. The mobile
-- question picker lists only questions with can_publish = true, and the web
-- question form sets it on insert once every test case has passed in Judge0.
ALTER TABLE public.questions
  ADD COLUMN IF NOT EXISTS can_publish boolean NOT NULL DEFAULT false;

COMMENT ON COLUMN public.questions.can_publish IS
  'True only when the model answer passes every saved Judge0 test case.';

-- The web form has refused to save a question until its test cases pass
-- since 2026-09-04, and every existing cloud question was created after
-- that, so questions that already have test cases count as validated.
UPDATE public.questions
SET can_publish = true
WHERE NOT can_publish
  AND jsonb_typeof(test_cases) = 'array'
  AND test_cases <> '[]'::jsonb;

GRANT INSERT (can_publish) ON TABLE public.questions TO anon, authenticated;
