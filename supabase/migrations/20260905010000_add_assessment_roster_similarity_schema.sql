create table public.assessments (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  status text not null default 'draft',
  starts_at timestamp with time zone,
  created_at timestamp with time zone not null default now(),
  constraint assessments_status_check
    check (status in ('draft', 'active', 'closed'))
);

create table public.block_sections (
  id uuid primary key default gen_random_uuid(),
  name text not null unique,
  created_at timestamp with time zone not null default now()
);

create table public.students (
  id uuid primary key default gen_random_uuid(),
  student_number text not null unique,
  display_name text not null,
  created_at timestamp with time zone not null default now()
);

create table public.assessment_questions (
  assessment_id uuid not null,
  question_id uuid not null,
  starter_code text not null default '',
  position integer not null default 0,
  updated_at timestamp with time zone not null default now(),
  constraint assessment_questions_pkey
    primary key (assessment_id, question_id),
  constraint assessment_questions_assessment_fkey
    foreign key (assessment_id)
    references public.assessments (id)
    on delete cascade,
  constraint assessment_questions_question_fkey
    foreign key (question_id)
    references public.questions (id)
    on delete cascade,
  constraint assessment_questions_position_check
    check (position >= 0)
);

create index assessment_questions_question_id_idx
  on public.assessment_questions (question_id);

create table public.assessment_roster (
  assessment_id uuid not null,
  student_id uuid not null,
  block_section_id uuid not null,
  created_at timestamp with time zone not null default now(),
  constraint assessment_roster_pkey
    primary key (assessment_id, student_id),
  constraint assessment_roster_assessment_student_block_key
    unique (assessment_id, student_id, block_section_id),
  constraint assessment_roster_assessment_fkey
    foreign key (assessment_id)
    references public.assessments (id)
    on delete cascade,
  constraint assessment_roster_student_fkey
    foreign key (student_id)
    references public.students (id)
    on delete cascade,
  constraint assessment_roster_block_section_fkey
    foreign key (block_section_id)
    references public.block_sections (id)
    on delete restrict
);

create index assessment_roster_student_id_idx
  on public.assessment_roster (student_id);

create index assessment_roster_block_section_id_idx
  on public.assessment_roster (block_section_id);

alter table public.submissions
  add column assessment_id uuid,
  add column student_id uuid,
  add column block_section_id uuid,
  add column verified_version integer not null default 0,
  add column is_current boolean not null default true;

update public.submissions
set verified_version = 1
where verified_text is not null
  and verified_version = 0;

alter table public.submissions
  add constraint submissions_verified_version_check
    check (verified_version >= 0),
  add constraint submissions_assessment_question_fkey
    foreign key (assessment_id, question_id)
    references public.assessment_questions (assessment_id, question_id)
    on delete restrict,
  add constraint submissions_assessment_roster_fkey
    foreign key (assessment_id, student_id, block_section_id)
    references public.assessment_roster (
      assessment_id,
      student_id,
      block_section_id
    )
    on delete restrict;

create index submissions_assessment_question_idx
  on public.submissions (assessment_id, question_id);

create index submissions_student_id_idx
  on public.submissions (student_id);

create index submissions_block_section_id_idx
  on public.submissions (block_section_id);

create unique index submissions_one_current_per_student_question_idx
  on public.submissions (assessment_id, question_id, student_id)
  where is_current
    and assessment_id is not null
    and question_id is not null
    and student_id is not null;

create function public.set_submission_verified_version()
returns trigger
language plpgsql
set search_path = ''
as $$
begin
  if tg_op = 'INSERT' then
    if new.verified_text is null then
      new.verified_version := 0;
    else
      new.verified_version := greatest(coalesce(new.verified_version, 0), 1);
    end if;
  elsif new.verified_text is distinct from old.verified_text then
    new.verified_version := old.verified_version + 1;
  else
    new.verified_version := old.verified_version;
  end if;

  return new;
end;
$$;

create trigger submissions_verified_version_trigger
before insert or update of verified_text, verified_version
on public.submissions
for each row
execute function public.set_submission_verified_version();

create table public.similarity_scans (
  id uuid primary key default gen_random_uuid(),
  assessment_id uuid not null,
  question_id uuid not null,
  status text not null default 'checking',
  algorithm_version text not null,
  cohort_fingerprint text not null,
  compared_submission_count integer not null default 0,
  skipped_submission_count integer not null default 0,
  error_message text,
  started_at timestamp with time zone not null default now(),
  completed_at timestamp with time zone,
  created_at timestamp with time zone not null default now(),
  constraint similarity_scans_status_check
    check (status in ('checking', 'complete', 'failed')),
  constraint similarity_scans_compared_count_check
    check (compared_submission_count >= 0),
  constraint similarity_scans_skipped_count_check
    check (skipped_submission_count >= 0),
  constraint similarity_scans_assessment_question_fkey
    foreign key (assessment_id, question_id)
    references public.assessment_questions (assessment_id, question_id)
    on delete cascade
);

create index similarity_scans_assessment_question_created_idx
  on public.similarity_scans (assessment_id, question_id, created_at desc);

create table public.similarity_matches (
  scan_id uuid not null,
  lower_submission_id uuid not null,
  higher_submission_id uuid not null,
  lower_verified_version integer not null,
  higher_verified_version integer not null,
  match_type text not null,
  matched_token_count integer not null,
  lower_coverage double precision not null,
  higher_coverage double precision not null,
  source_ranges jsonb not null default '[]'::jsonb,
  created_at timestamp with time zone not null default now(),
  constraint similarity_matches_pkey
    primary key (scan_id, lower_submission_id, higher_submission_id),
  constraint similarity_matches_scan_fkey
    foreign key (scan_id)
    references public.similarity_scans (id)
    on delete cascade,
  constraint similarity_matches_lower_submission_fkey
    foreign key (lower_submission_id)
    references public.submissions (id)
    on delete cascade,
  constraint similarity_matches_higher_submission_fkey
    foreign key (higher_submission_id)
    references public.submissions (id)
    on delete cascade,
  constraint similarity_matches_canonical_pair_check
    check (lower_submission_id < higher_submission_id),
  constraint similarity_matches_verified_versions_check
    check (lower_verified_version > 0 and higher_verified_version > 0),
  constraint similarity_matches_type_check
    check (match_type in ('exact', 'structural')),
  constraint similarity_matches_matched_tokens_check
    check (matched_token_count > 0),
  constraint similarity_matches_lower_coverage_check
    check (lower_coverage between 0 and 1),
  constraint similarity_matches_higher_coverage_check
    check (higher_coverage between 0 and 1),
  constraint similarity_matches_source_ranges_check
    check (jsonb_typeof(source_ranges) = 'array')
);

create index similarity_matches_lower_submission_idx
  on public.similarity_matches (lower_submission_id);

create index similarity_matches_higher_submission_idx
  on public.similarity_matches (higher_submission_id);

alter table public.assessments enable row level security;
alter table public.block_sections enable row level security;
alter table public.students enable row level security;
alter table public.assessment_questions enable row level security;
alter table public.assessment_roster enable row level security;
alter table public.similarity_scans enable row level security;
alter table public.similarity_matches enable row level security;

revoke all on table public.assessments from anon, authenticated;
revoke all on table public.block_sections from anon, authenticated;
revoke all on table public.students from anon, authenticated;
revoke all on table public.assessment_questions from anon, authenticated;
revoke all on table public.assessment_roster from anon, authenticated;
revoke all on table public.similarity_scans from anon, authenticated;
revoke all on table public.similarity_matches from anon, authenticated;

grant all on table public.assessments to service_role;
grant all on table public.block_sections to service_role;
grant all on table public.students to service_role;
grant all on table public.assessment_questions to service_role;
grant all on table public.assessment_roster to service_role;
grant all on table public.similarity_scans to service_role;
grant all on table public.similarity_matches to service_role;

comment on column public.submissions.verified_version is
  'Increments only when the instructor-saved verified text changes.';

comment on table public.similarity_scans is
  'One reproducible similarity analysis for an assessment question cohort.';

comment on table public.similarity_matches is
  'Canonical submission pairs flagged for optional instructor review.';
