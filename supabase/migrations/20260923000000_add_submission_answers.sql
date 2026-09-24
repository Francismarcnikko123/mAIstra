-- Programs 2..n that a teacher separates out of one handwritten paper.
-- Program 1 stays in verified_text / question_id. Each entry is
-- {"code": text, "question_id": uuid-or-null}, in tab order.
-- The original OCR output stays in extracted_text and is never written here.
ALTER TABLE public.submissions
  ADD COLUMN IF NOT EXISTS answers jsonb NOT NULL DEFAULT '[]'::jsonb;

-- The public API lockdown grants UPDATE by column, so the review editor
-- needs an explicit grant for Programs 2..n.
GRANT UPDATE (answers) ON TABLE public.submissions TO anon, authenticated;
