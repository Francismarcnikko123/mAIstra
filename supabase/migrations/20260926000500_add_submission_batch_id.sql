-- Groups the pages of one answer. The phone saves one submissions row per
-- photographed page and sets the same batch_id on every page it uploads
-- together; each page stays its own row, so OCR still reads one image per
-- row. Rows from before this column, and from the web, stay NULL.
ALTER TABLE public.submissions
  ADD COLUMN IF NOT EXISTS batch_id uuid;

COMMENT ON COLUMN public.submissions.batch_id IS
  'Shared by every page the phone uploaded as one answer. NULL for single pages captured before 2026-09-26 and for rows not created by the phone.';

-- "All pages of this answer" is a lookup by batch_id.
CREATE INDEX IF NOT EXISTS submissions_batch_id_idx
  ON public.submissions (batch_id)
  WHERE batch_id IS NOT NULL;

-- Set once by the phone on insert; pages are not moved between answers.
GRANT INSERT (batch_id) ON TABLE public.submissions TO anon, authenticated;
