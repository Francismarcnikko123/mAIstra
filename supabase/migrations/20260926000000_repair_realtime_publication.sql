-- Reassert the Realtime publication contract. A migration can remain marked
-- as applied even if publication membership is changed later, so this repair
-- is intentionally safe to run against databases that are already correct.
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'submissions'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.submissions;
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_publication_tables
    WHERE pubname = 'supabase_realtime'
      AND schemaname = 'public'
      AND tablename = 'questions'
  ) THEN
    ALTER PUBLICATION supabase_realtime ADD TABLE public.questions;
  END IF;
END $$;
