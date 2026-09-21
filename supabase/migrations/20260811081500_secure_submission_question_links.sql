alter table public.questions
  add column if not exists question_type text not null default 'program';

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'questions_question_type_check'
      and conrelid = 'public.questions'::regclass
  ) then
    alter table public.questions
      add constraint questions_question_type_check
      check (question_type = any (array['function'::text, 'program'::text]));
  end if;
end $$;

alter table public.submissions
  add column if not exists topic text,
  add column if not exists question_id uuid;

do $$
begin
  if not exists (
    select 1
    from pg_constraint
    where conname = 'submissions_question_id_fkey'
      and conrelid = 'public.submissions'::regclass
  ) then
    alter table public.submissions
      add constraint submissions_question_id_fkey
      foreign key (question_id)
      references public.questions(id)
      on delete set null;
  end if;
end $$;

create index if not exists submissions_question_id_idx
  on public.submissions (question_id);

alter table public.questions enable row level security;
alter table public.submissions enable row level security;

drop policy if exists "allow public inserts questions" on public.questions;
drop policy if exists "allow public inserts" on public.submissions;

drop policy if exists questions_public_select on public.questions;
drop policy if exists questions_public_insert on public.questions;
drop policy if exists submissions_public_select on public.submissions;
drop policy if exists submissions_public_insert on public.submissions;
drop policy if exists submissions_public_update on public.submissions;

create policy questions_public_select
  on public.questions
  for select
  to anon, authenticated
  using (true);

create policy questions_public_insert
  on public.questions
  for insert
  to anon, authenticated
  with check (true);

create policy submissions_public_select
  on public.submissions
  for select
  to anon, authenticated
  using (true);

create policy submissions_public_insert
  on public.submissions
  for insert
  to anon, authenticated
  with check (true);

create policy submissions_public_update
  on public.submissions
  for update
  to anon, authenticated
  using (true)
  with check (
    status = any (array['pending'::text, 'verified'::text])
    and coalesce(length(topic), 0) <= 120
  );

revoke all on table public.questions from anon, authenticated;
revoke all on table public.submissions from anon, authenticated;

grant select, insert on table public.questions to anon, authenticated;
grant select, insert on table public.submissions to anon, authenticated;
grant update (
  topic,
  question_id,
  extracted_text,
  verified_text,
  verified_at,
  status
) on table public.submissions to anon, authenticated;

do $$
begin
  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'submissions'
  ) then
    alter publication supabase_realtime add table public.submissions;
  end if;

  if not exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'questions'
  ) then
    alter publication supabase_realtime add table public.questions;
  end if;
end $$;
