begin;

select plan(36);

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
      and table_name = 'questions'
      and column_name = 'question_type'
      and is_nullable = 'NO'
  ),
  'questions.question_type is required'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'questions'
      and column_name = 'question_type'
      and column_default = '''program''::text'
  ),
  'questions.question_type defaults to program'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.questions'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) like '%question_type%'
      and pg_get_constraintdef(oid) like '%function%'
      and pg_get_constraintdef(oid) like '%program%'
  ),
  'questions.question_type accepts only function or program'
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
    from pg_constraint constraint_record
    join pg_attribute column_record
      on column_record.attrelid = constraint_record.conrelid
      and column_record.attnum = any (constraint_record.conkey)
    where constraint_record.conrelid = 'public.submissions'::regclass
      and constraint_record.confrelid = 'public.questions'::regclass
      and constraint_record.contype = 'f'
      and column_record.attname = 'question_id'
  ),
  'submissions.question_id references questions.id'
);

select ok(
  exists (
    select 1
    from pg_index index_record
    join pg_attribute column_record
      on column_record.attrelid = index_record.indrelid
      and column_record.attnum = any (index_record.indkey)
    where index_record.indrelid = 'public.submissions'::regclass
      and column_record.attname = 'question_id'
  ),
  'submissions.question_id is indexed'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'grading_results'
      and data_type = 'jsonb'
      and is_nullable = 'NO'
  ),
  'submissions.grading_results stores per-test results'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'passed_test_cases'
      and data_type = 'integer'
  ),
  'submissions.passed_test_cases stores the earned count'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'total_test_cases'
      and data_type = 'integer'
  ),
  'submissions.total_test_cases stores the possible count'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'score_percent'
      and data_type = 'numeric'
      and is_generated = 'ALWAYS'
  ),
  'submissions.score_percent is generated from the counts'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'graded_at'
      and data_type = 'timestamp with time zone'
  ),
  'submissions.graded_at records when grading completed'
);

select ok(
  exists (
    select 1
    from pg_constraint
    where conrelid = 'public.submissions'::regclass
      and contype = 'c'
      and pg_get_constraintdef(oid) like '%passed_test_cases%'
      and pg_get_constraintdef(oid) like '%total_test_cases%'
  ),
  'submission grade counts are constrained to a valid range'
);

insert into public.submissions (
  id,
  image_url,
  status,
  grading_results,
  passed_test_cases,
  total_test_cases,
  graded_at
)
values (
  '00000000-0000-0000-0000-000000000901',
  'https://example.test/submission.png',
  'graded',
  '[{"passed": true}]'::jsonb,
  3,
  4,
  now()
);

select is(
  (
    select score_percent
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000901'
  ),
  75.00::numeric,
  'a three-of-four grade stores a 75 percent score'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'grading_revision'
      and data_type = 'bigint'
      and is_nullable = 'NO'
      and column_default = '0'
  ),
  'submissions.grading_revision exists with a zero default'
);

select ok(
  exists (
    select 1
    from pg_trigger
    where tgrelid = 'public.submissions'::regclass
      and tgname = 'invalidate_submission_grade_on_input_change'
      and not tgisinternal
  ),
  'persisted grading input changes have an invalidation trigger'
);

update public.submissions
set verified_text = 'updated code'
where id = '00000000-0000-0000-0000-000000000901';

select is(
  (
    select (to_jsonb(submission_record) ->> 'grading_revision')::bigint
    from public.submissions submission_record
    where id = '00000000-0000-0000-0000-000000000901'
  ),
  1::bigint,
  'changing verified code increments the grading revision'
);

select ok(
  (
    select grading_results = '[]'::jsonb
      and passed_test_cases is null
      and total_test_cases is null
      and score_percent is null
      and graded_at is null
      and status = 'verified'
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000901'
  ),
  'changing verified code clears the persisted grade'
);

select ok(
  exists (
    select 1
    from pg_trigger
    where tgrelid = 'public.submissions'::regclass
      and tgname = 'advance_grading_revision_on_grade'
      and not tgisinternal
  ),
  'successful grade writes have a revision-advancing trigger'
);

update public.submissions
set grading_results = '[{"passed": true}]'::jsonb,
    passed_test_cases = 1,
    total_test_cases = 1,
    graded_at = now(),
    status = 'graded'
where id = '00000000-0000-0000-0000-000000000901'
  and grading_revision = 1;

select is(
  (
    select grading_revision
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000901'
  ),
  2::bigint,
  'a successful grade write advances the grading revision exactly once'
);

update public.submissions
set grading_results = '[{"passed": false}]'::jsonb,
    passed_test_cases = 0,
    total_test_cases = 1,
    graded_at = now(),
    status = 'graded'
where id = '00000000-0000-0000-0000-000000000901'
  and grading_revision = 1;

select ok(
  (
    select grading_revision = 2
      and grading_results = '[{"passed": true}]'::jsonb
      and passed_test_cases = 1
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000901'
  ),
  'a second writer using the stale revision cannot overwrite the grade'
);

update public.submissions
set verified_text = 'code and grade changed together',
    grading_results = '[{"passed": false}]'::jsonb,
    passed_test_cases = 0,
    total_test_cases = 1,
    graded_at = now(),
    status = 'graded'
where id = '00000000-0000-0000-0000-000000000901'
  and grading_revision = 2;

select ok(
  (
    select grading_revision = 3
      and grading_results = '[]'::jsonb
      and passed_test_cases is null
      and total_test_cases is null
      and graded_at is null
      and status = 'verified'
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000901'
  ),
  'input invalidation and grade triggers advance the revision only once'
);

insert into public.submissions (
  id,
  image_url,
  verified_text,
  status,
  grading_results,
  passed_test_cases,
  total_test_cases,
  graded_at
)
values (
  '00000000-0000-0000-0000-000000000902',
  'https://example.test/second-submission.png',
  'unchanged code',
  'graded',
  '[{"passed": true}]'::jsonb,
  1,
  1,
  now()
);

update public.submissions
set verified_text = 'unchanged code',
    status = 'verified'
where id = '00000000-0000-0000-0000-000000000902';

select ok(
  (
    select grading_revision = 0
      and status = 'graded'
      and grading_results = '[{"passed": true}]'::jsonb
      and passed_test_cases = 1
      and total_test_cases = 1
      and graded_at is not null
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000902'
  ),
  'resaving identical code preserves the consistent graded snapshot'
);

create temporary table anon_grade_write_results (
  attempt text,
  revision bigint
);

grant insert, select on table anon_grade_write_results to anon;

set local role anon;

with updated as (
  update public.submissions
  set grading_results = '[{"passed": false}]'::jsonb,
      passed_test_cases = 0,
      total_test_cases = 1,
      graded_at = now(),
      status = 'graded'
  where id = '00000000-0000-0000-0000-000000000902'
    and grading_revision = 0
  returning grading_revision
)
insert into anon_grade_write_results (attempt, revision)
select 'fresh', grading_revision from updated;

with updated as (
  update public.submissions
  set grading_results = '[{"passed": true}]'::jsonb,
      passed_test_cases = 1,
      total_test_cases = 1,
      graded_at = now(),
      status = 'graded'
  where id = '00000000-0000-0000-0000-000000000902'
    and grading_revision = 0
  returning grading_revision
)
insert into anon_grade_write_results (attempt, revision)
select 'stale', grading_revision from updated;

reset role;

select is(
  (
    select revision
    from anon_grade_write_results
    where attempt = 'fresh'
  ),
  1::bigint,
  'anon can save a grade and receive the atomically incremented revision'
);

select is(
  (
    select count(*)
    from anon_grade_write_results
    where attempt = 'stale'
  ),
  0::bigint,
  'anon stale compare-and-set grade writes affect zero rows'
);

select ok(
  exists (
    select 1
    from pg_proc
    where oid = 'public.save_submission_grade(uuid, bigint, uuid, text, jsonb)'::regprocedure
      and not prosecdef
  ),
  'grades are saved through a security-invoker function'
);

insert into public.questions (
  id,
  question_name,
  question_text,
  model_answer,
  question_type
)
values (
  '00000000-0000-0000-0000-000000000a01',
  'Contract question',
  'Print a number.',
  'int main(void) { return 0; }',
  'program'
);

insert into public.submissions (
  id,
  image_url,
  verified_text,
  question_id,
  status
)
values (
  '00000000-0000-0000-0000-000000000903',
  'https://example.test/third-submission.png',
  'stored code',
  '00000000-0000-0000-0000-000000000a01',
  'verified'
);

create temporary table anon_save_grade_results (
  attempt text,
  revision bigint
);

grant insert, select on table anon_save_grade_results to anon;

set local role anon;

insert into anon_save_grade_results (attempt, revision)
select 'unsaved code', public.save_submission_grade(
  '00000000-0000-0000-0000-000000000903',
  0,
  '00000000-0000-0000-0000-000000000a01',
  'edited but never saved code',
  '[{"passed": true}]'::jsonb
);

insert into anon_save_grade_results (attempt, revision)
select 'stored code', public.save_submission_grade(
  '00000000-0000-0000-0000-000000000903',
  0,
  '00000000-0000-0000-0000-000000000a01',
  'stored code',
  '[{"passed": true}, {"passed": false}]'::jsonb
);

insert into anon_save_grade_results (attempt, revision)
select 'stale revision', public.save_submission_grade(
  '00000000-0000-0000-0000-000000000903',
  0,
  '00000000-0000-0000-0000-000000000a01',
  'stored code',
  '[{"passed": true}, {"passed": true}]'::jsonb
);

reset role;

select is(
  (
    select revision
    from anon_save_grade_results
    where attempt = 'unsaved code'
  ),
  null::bigint,
  'a grade for code that differs from the stored code is not saved'
);

select is(
  (
    select revision
    from anon_save_grade_results
    where attempt = 'stored code'
  ),
  1::bigint,
  'a grade for the stored code is saved and returns the new revision'
);

select ok(
  (
    select grading_revision = 1
      and status = 'graded'
      and passed_test_cases = 1
      and total_test_cases = 2
      and score_percent = 50.00
      and graded_at is not null
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000903'
  ),
  'the saved grade derives its counts from the submitted results'
);

select is(
  (
    select revision
    from anon_save_grade_results
    where attempt = 'stale revision'
  ),
  null::bigint,
  'a grade computed against a stale revision is not saved'
);

insert into public.submissions (
  id,
  image_url,
  verified_text,
  question_id,
  status
)
values (
  '00000000-0000-0000-0000-000000000904',
  'https://example.test/fourth-submission.png',
  'ungraded code',
  '00000000-0000-0000-0000-000000000a01',
  'verified'
);

set local role anon;

update public.questions
set question_name = 'Renamed contract question',
    question_text = 'Print a number, clearly.'
where id = '00000000-0000-0000-0000-000000000a01';

reset role;

select ok(
  (
    select grading_revision = 1
      and status = 'graded'
      and passed_test_cases = 1
      and total_test_cases = 2
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000903'
  ),
  'renaming a question keeps the grades of its papers'
);

set local role anon;

update public.questions
set test_cases = '[{"test_input": "", "expected_output": "0"}]'::jsonb
where id = '00000000-0000-0000-0000-000000000a01';

reset role;

select ok(
  (
    select grading_revision = 2
      and status = 'verified'
      and grading_results = '[]'::jsonb
      and passed_test_cases is null
      and total_test_cases is null
      and graded_at is null
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000903'
  ),
  'editing a question''s test cases clears the grades of its papers'
);

select ok(
  (
    select grading_revision = 1
      and status = 'verified'
    from public.submissions
    where id = '00000000-0000-0000-0000-000000000904'
  ),
  'editing test cases refuses grades still being computed against the old ones'
);

select ok(
  exists (
    select 1
    from information_schema.columns
    where table_schema = 'public'
      and table_name = 'submissions'
      and column_name = 'batch_id'
      and data_type = 'uuid'
      and is_nullable = 'YES'
  ),
  'submissions.batch_id groups the pages of one answer'
);

select ok(
  exists (
    select 1
    from pg_index index_record
    join pg_attribute column_record
      on column_record.attrelid = index_record.indrelid
      and column_record.attnum = any (index_record.indkey)
    where index_record.indrelid = 'public.submissions'::regclass
      and column_record.attname = 'batch_id'
  ),
  'submissions.batch_id is indexed'
);

select * from finish();

rollback;
