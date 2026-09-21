ALTER TABLE public.questions
  DROP COLUMN IF EXISTS validation_status,
  DROP COLUMN IF EXISTS can_publish,
  DROP COLUMN IF EXISTS model_validation_results;
