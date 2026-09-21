-- Replace the original broad grants with the minimum privileges required by
-- the current no-login thesis workflow. RLS remains the enforcement boundary
-- for requests made with the publishable API key.

ALTER TABLE public.questions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.submissions ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "allow public inserts questions" ON public.questions;
DROP POLICY IF EXISTS questions_public_select ON public.questions;
DROP POLICY IF EXISTS questions_public_insert ON public.questions;

DROP POLICY IF EXISTS "allow public inserts" ON public.submissions;
DROP POLICY IF EXISTS submissions_public_select ON public.submissions;
DROP POLICY IF EXISTS submissions_public_insert ON public.submissions;
DROP POLICY IF EXISTS submissions_public_update ON public.submissions;

CREATE POLICY questions_public_select
  ON public.questions
  FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY questions_public_insert
  ON public.questions
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (
    question_type = ANY (ARRAY['function'::text, 'program'::text])
    AND length(question_name) BETWEEN 1 AND 200
    AND length(question_text) BETWEEN 1 AND 10000
    AND length(model_answer) BETWEEN 1 AND 50000
    AND jsonb_typeof(test_cases) = 'array'
  );

CREATE POLICY submissions_public_select
  ON public.submissions
  FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY submissions_public_insert
  ON public.submissions
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (
    status = 'pending'
    AND image_url LIKE '%/storage/v1/object/public/handwritten-submissions/%'
    AND extracted_text IS NULL
    AND verified_text IS NULL
    AND verified_at IS NULL
    AND grading_results = '[]'::jsonb
    AND passed_test_cases IS NULL
    AND total_test_cases IS NULL
    AND graded_at IS NULL
  );

CREATE POLICY submissions_public_update
  ON public.submissions
  FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (
    status = ANY (ARRAY[
        'pending'::text,
        'extracted'::text,
        'verified'::text,
        'graded'::text
      ])
    AND coalesce(length(topic), 0) <= 120
  );

REVOKE ALL ON TABLE public.questions FROM anon, authenticated;
REVOKE ALL ON TABLE public.submissions FROM anon, authenticated;

GRANT SELECT ON TABLE public.questions TO anon, authenticated;
GRANT INSERT (
  question_name,
  question_text,
  model_answer,
  test_cases,
  question_type
) ON TABLE public.questions TO anon, authenticated;

GRANT SELECT ON TABLE public.submissions TO anon, authenticated;
GRANT INSERT (
  image_url,
  student_name,
  captured_at,
  status,
  question_id
) ON TABLE public.submissions TO anon, authenticated;
GRANT UPDATE (
  topic,
  question_id,
  extracted_text,
  verified_text,
  verified_at,
  status,
  grading_results,
  passed_test_cases,
  total_test_cases,
  graded_at
) ON TABLE public.submissions TO anon, authenticated;

-- Prevent future tables, functions, or sequences from inheriting the broad
-- public privileges contained in the original schema dump.
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON TABLES FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON FUNCTIONS FROM anon, authenticated;
ALTER DEFAULT PRIVILEGES FOR ROLE postgres IN SCHEMA public
  REVOKE ALL ON SEQUENCES FROM anon, authenticated;

REVOKE ALL ON FUNCTION public.invalidate_submission_grade()
  FROM PUBLIC, anon, authenticated;

-- The mobile app uploads only camera images to this public bucket. Public
-- reads remain intentional because the OCR service downloads image URLs.
UPDATE storage.buckets
SET
  file_size_limit = 10485760,
  allowed_mime_types = ARRAY['image/jpeg', 'image/png']::text[],
  updated_at = now()
WHERE id = 'handwritten-submissions';

DROP POLICY IF EXISTS handwritten_submissions_public_insert
  ON storage.objects;

CREATE POLICY handwritten_submissions_public_insert
  ON storage.objects
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (
    bucket_id = 'handwritten-submissions'
    AND lower(name) ~ '\.(jpe?g|png)$'
  );
