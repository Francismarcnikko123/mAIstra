-- The phone's capture quality gate verdict for each uploaded page, so a low
-- grade can be traced back to a bad or auto-corrected photo. The mobile app
-- writes 'PASS' or 'FIXABLE' (a page the gate auto-corrected counts as
-- FIXABLE). Rows from before this column, and from the web, stay NULL.
ALTER TABLE public.submissions
  ADD COLUMN IF NOT EXISTS gate_result text;

ALTER TABLE public.submissions
  DROP CONSTRAINT IF EXISTS submissions_gate_result_check;
ALTER TABLE public.submissions
  ADD CONSTRAINT submissions_gate_result_check
  CHECK (gate_result IN ('PASS', 'FIXABLE', 'RETAKE'));

COMMENT ON COLUMN public.submissions.gate_result IS
  'Mobile capture quality gate verdict for this page: PASS, FIXABLE or RETAKE. NULL when the page did not come through the gate.';

-- Same insert rules as 20260921000000_lock_down_public_api.sql, plus the
-- gate verdict. RETAKE pages must be captured again, never uploaded.
ALTER POLICY submissions_public_insert
  ON public.submissions
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
    AND (gate_result IS NULL OR gate_result IN ('PASS', 'FIXABLE'))
  );

-- Insert only: the verdict records how the photo was taken and is not
-- edited afterwards.
GRANT INSERT (gate_result) ON TABLE public.submissions TO anon, authenticated;
