begin;

create extension if not exists pgtap with schema extensions;
set local search_path = public, extensions;

select plan(28);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'questions'
      and column_name = 'question_type'
      and data_type = 'text'
  ),
  'questions.question_type exists as text'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'topic'
      and data_type = 'text'
  ),
  'submissions.topic exists as text'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'question_id'
      and data_type = 'uuid'
  ),
  'submissions.question_id exists as uuid'
);

select ok(
  exists (
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
  ),
  'submissions.question_id references questions.id'
);

select ok(
  to_regclass('public.submissions_question_id_idx') is not null,
  'submissions.question_id has an index'
);

select ok(
  (
    select count(*) = 6
    from pg_class
    where relnamespace = 'public'::regnamespace
      and relkind = 'r'
      and relname = any (array[
        'assessments',
        'block_sections',
        'students',
        'assessment_questions',
        'assessment_roster',
        'similarity_scans'
      ])
  ),
  'assessment, roster, and scan tables exist'
);

select ok(
  (
    select count(*) = 5
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = any (array[
        'assessment_id',
        'student_id',
        'block_section_id',
        'verified_version',
        'is_current'
      ])
  ),
  'submissions contains similarity cohort metadata'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.assessments'::regclass
      and conname = 'assessments_status_check'
      and contype = 'c'
  ),
  'assessments restricts status values'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.assessment_questions'::regclass
      and conname = 'assessment_questions_pkey'
      and contype = 'p'
  ),
  'assessment questions use a composite primary key'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.assessment_roster'::regclass
      and conname = 'assessment_roster_pkey'
      and contype = 'p'
  ),
  'assessment roster identifies each student once per assessment'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.assessment_roster'::regclass
      and conname = 'assessment_roster_assessment_student_block_key'
      and contype = 'u'
  ),
  'assessment roster exposes the composite key used by submissions'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.submissions'::regclass
      and conname = 'submissions_assessment_question_fkey'
      and confrelid = 'public.assessment_questions'::regclass
      and contype = 'f'
  ),
  'submissions must use a question assigned to the assessment'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.submissions'::regclass
      and conname = 'submissions_assessment_roster_fkey'
      and confrelid = 'public.assessment_roster'::regclass
      and contype = 'f'
  ),
  'submissions must use a student and block from the assessment roster'
);

select ok(
  exists (
    select 1
    from pg_index
    where indexrelid = 'public.submissions_one_current_per_student_question_idx'::regclass
      and indisunique
      and indpred is not null
  ),
  'only one current submission is allowed per assessment question and student'
);

select ok(
  exists (
    select 1
    from pg_trigger
    where tgrelid = 'public.submissions'::regclass
      and tgname = 'submissions_verified_version_trigger'
      and not tgisinternal
  ),
  'submissions has a verified text version trigger'
);

select ok(
  not exists (
    select 1
    from public.submissions
    where verified_text is not null
      and verified_version < 1
  ),
  'existing verified text is backfilled to a positive version'
);

insert into public.assessments (id, name, status)
values ('10000000-0000-0000-0000-000000000001', 'Schema contract', 'active');

insert into public.block_sections (id, name)
values ('20000000-0000-0000-0000-000000000001', 'Contract A');

insert into public.students (id, student_number, display_name)
values ('30000000-0000-0000-0000-000000000001', 'CONTRACT-001', 'Contract Student');

insert into public.questions (
  id,
  question_name,
  question_text,
  model_answer,
  test_cases
)
values (
  '40000000-0000-0000-0000-000000000001',
  'Contract question',
  'Return zero.',
  'int main(void) { return 0; }',
  '[]'::jsonb
);

insert into public.assessment_questions (assessment_id, question_id, position)
values (
  '10000000-0000-0000-0000-000000000001',
  '40000000-0000-0000-0000-000000000001',
  1
);

insert into public.assessment_roster (
  assessment_id,
  student_id,
  block_section_id
)
values (
  '10000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '20000000-0000-0000-0000-000000000001'
);

insert into public.submissions (
  id,
  image_url,
  verified_text,
  assessment_id,
  question_id,
  student_id,
  block_section_id
)
values (
  '50000000-0000-0000-0000-000000000001',
  'https://example.test/contract.png',
  'int main(void) { return 0; }',
  '10000000-0000-0000-0000-000000000001',
  '40000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '20000000-0000-0000-0000-000000000001'
);

select is(
  (
    select verified_version
    from public.submissions
    where id = '50000000-0000-0000-0000-000000000001'
  ),
  1,
  'new verified text starts at version one'
);

update public.submissions
set status = 'verified'
where id = '50000000-0000-0000-0000-000000000001';

select is(
  (
    select verified_version
    from public.submissions
    where id = '50000000-0000-0000-0000-000000000001'
  ),
  1,
  'metadata-only updates preserve the verified version'
);

update public.submissions
set verified_text = 'int main(void) { return 1; }'
where id = '50000000-0000-0000-0000-000000000001';

select is(
  (
    select verified_version
    from public.submissions
    where id = '50000000-0000-0000-0000-000000000001'
  ),
  2,
  'changing verified text increments the version once'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.similarity_scans'::regclass
      and conname = 'similarity_scans_assessment_question_fkey'
      and confrelid = 'public.assessment_questions'::regclass
      and contype = 'f'
  ),
  'similarity scans belong to an assessment question'
);

select ok(
  (
    select array_agg(column_name::text order by column_name) = array[
      'compared_pair_count', 'metadata', 'skipped_pair_count'
    ]
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'similarity_scans'
      and column_name = any (array[
        'compared_pair_count', 'metadata', 'skipped_pair_count'
      ])
  ),
  'similarity scans retain pair counts and reproducibility metadata'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.similarity_matches'::regclass
      and conname = 'similarity_matches_type_check'
      and pg_get_constraintdef(oid) like '%exact_duplicate%'
      and pg_get_constraintdef(oid) like '%normalized_duplicate%'
      and pg_get_constraintdef(oid) like '%similar_code%'
  ),
  'similarity matches preserve all evidence classifications'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.similarity_matches'::regclass
      and conname = 'similarity_matches_source_ranges_check'
      and pg_get_constraintdef(oid) like '%left%'
      and pg_get_constraintdef(oid) like '%right%'
  ),
  'similarity matches keep independent source range arrays'
);

select ok(
  (
    select count(*) = 2
    from pg_constraint
    where conrelid = 'public.similarity_matches'::regclass
      and conname = any (array[
        'similarity_matches_lower_submission_fkey',
        'similarity_matches_higher_submission_fkey'
      ])
      and confrelid = 'public.submissions'::regclass
      and contype = 'f'
  ),
  'similarity matches reference both compared submissions'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.similarity_matches'::regclass
      and conname = 'similarity_matches_canonical_pair_check'
      and contype = 'c'
  ),
  'similarity match pairs must use canonical UUID order'
);

select ok(
  to_regclass('public.similarity_matches_lower_submission_idx') is not null
    and to_regclass('public.similarity_matches_higher_submission_idx') is not null,
  'similarity match lookup indexes cover both submissions'
);

select ok(
  (
    select count(*) = 7
    from pg_class
    where relnamespace = 'public'::regnamespace
      and relkind = 'r'
      and relrowsecurity
      and relname = any (array[
        'assessments',
        'block_sections',
        'students',
        'assessment_questions',
        'assessment_roster',
        'similarity_scans',
        'similarity_matches'
      ])
  ),
  'all new tables have row-level security enabled'
);

select ok(
  not exists (
    select 1
    from pg_policies
    where schemaname = 'public'
      and tablename = any (array[
        'assessments',
        'block_sections',
        'students',
        'assessment_questions',
        'assessment_roster',
        'similarity_scans',
        'similarity_matches'
      ])
  ),
  'new tables do not expose permissive public policies'
);

select * from finish();

rollback;
