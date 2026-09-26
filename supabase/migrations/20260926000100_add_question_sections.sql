-- Question sections (e.g. 'Basic') and each question's number inside its
-- section (1 -> 'Q1'). Kept in separate Nikko-owned tables so the column
-- grants and insert policy on public.questions stay untouched.
--
-- A question with no row in question_section_items is unsectioned: it shows
-- under "No section yet" in the web bank and never appears in the mobile
-- picker.

CREATE TABLE public.question_sections (
  id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  name        text NOT NULL UNIQUE,
  position    integer NOT NULL DEFAULT 0,
  created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE public.question_section_items (
  section_id  uuid NOT NULL REFERENCES public.question_sections(id) ON DELETE CASCADE,
  question_id uuid NOT NULL REFERENCES public.questions(id) ON DELETE CASCADE,
  number      integer NOT NULL,
  PRIMARY KEY (section_id, question_id),
  -- Refuses a duplicate question number inside one section.
  UNIQUE (section_id, number),
  -- A question belongs to at most one section.
  UNIQUE (question_id)
);

-- Same no-login model as public.questions in
-- 20260921000000_lock_down_public_api.sql: RLS on, public read, validated
-- insert/update, minimum column grants. No delete from the API.

ALTER TABLE public.question_sections ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.question_section_items ENABLE ROW LEVEL SECURITY;

CREATE POLICY question_sections_public_select
  ON public.question_sections
  FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY question_sections_public_insert
  ON public.question_sections
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (length(btrim(name)) BETWEEN 1 AND 60);

CREATE POLICY question_section_items_public_select
  ON public.question_section_items
  FOR SELECT
  TO anon, authenticated
  USING (true);

CREATE POLICY question_section_items_public_insert
  ON public.question_section_items
  FOR INSERT
  TO anon, authenticated
  WITH CHECK (number BETWEEN 1 AND 999);

CREATE POLICY question_section_items_public_update
  ON public.question_section_items
  FOR UPDATE
  TO anon, authenticated
  USING (true)
  WITH CHECK (number BETWEEN 1 AND 999);

REVOKE ALL ON TABLE public.question_sections FROM anon, authenticated;
REVOKE ALL ON TABLE public.question_section_items FROM anon, authenticated;

GRANT SELECT ON TABLE public.question_sections TO anon, authenticated;
GRANT INSERT (name, position) ON TABLE public.question_sections
  TO anon, authenticated;

GRANT SELECT ON TABLE public.question_section_items TO anon, authenticated;
GRANT INSERT (section_id, question_id, number)
  ON TABLE public.question_section_items TO anon, authenticated;
GRANT UPDATE (section_id, number)
  ON TABLE public.question_section_items TO anon, authenticated;
