alter table public.questions
  add column if not exists question_type text;

update public.questions
set question_type = 'program'
where question_type is null;

alter table public.questions
  alter column question_type set default 'program',
  alter column question_type set not null;

alter table public.submissions
  add column if not exists topic text,
  add column if not exists question_id uuid;

update public.submissions
set topic = 'Uncategorized'
where topic is null;

alter table public.submissions
  alter column topic set default 'Uncategorized',
  alter column topic set not null;

do $$
begin
  if not exists (
    select 1
    from pg_constraint as constraint_record
    join pg_attribute as source_column
      on source_column.attrelid = constraint_record.conrelid
      and source_column.attnum = any (constraint_record.conkey)
    join pg_attribute as target_column
      on target_column.attrelid = constraint_record.confrelid
      and target_column.attnum = any (constraint_record.confkey)
    where constraint_record.contype = 'f'
      and constraint_record.conrelid = 'public.submissions'::regclass
      and constraint_record.confrelid = 'public.questions'::regclass
      and source_column.attname = 'question_id'
      and target_column.attname = 'id'
  ) then
    alter table public.submissions
      add constraint submissions_question_id_fkey
      foreign key (question_id)
      references public.questions (id)
      on delete set null;
  end if;
end
$$;

create index if not exists submissions_question_id_idx
  on public.submissions (question_id);

comment on column public.questions.question_type is
  'Selects function or program execution behavior in the Angular question workflow.';

comment on column public.submissions.topic is
  'Groups submissions in the Angular review interface.';

comment on column public.submissions.question_id is
  'Links a submission to the question used for Judge0 grading.';
