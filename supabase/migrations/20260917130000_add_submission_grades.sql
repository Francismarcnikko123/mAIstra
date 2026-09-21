ALTER TABLE public.submissions
  ADD COLUMN IF NOT EXISTS grading_results jsonb DEFAULT '[]'::jsonb NOT NULL,
  ADD COLUMN IF NOT EXISTS passed_test_cases integer,
  ADD COLUMN IF NOT EXISTS total_test_cases integer,
  ADD COLUMN IF NOT EXISTS graded_at timestamptz,
  ADD COLUMN IF NOT EXISTS score_percent numeric(5, 2)
    GENERATED ALWAYS AS (
      CASE
        WHEN total_test_cases IS NULL OR total_test_cases = 0 THEN NULL
        ELSE round(
          passed_test_cases::numeric * 100 / total_test_cases,
          2
        )
      END
    ) STORED;

ALTER TABLE public.submissions
  ADD CONSTRAINT submissions_grade_counts_check
  CHECK (
    (passed_test_cases IS NULL AND total_test_cases IS NULL)
    OR (
      passed_test_cases IS NOT NULL
      AND total_test_cases IS NOT NULL
      AND passed_test_cases >= 0
      AND total_test_cases > 0
      AND passed_test_cases <= total_test_cases
    )
  );
