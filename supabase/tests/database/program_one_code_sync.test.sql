begin;

-- Program 1 follows the page's code as well as its question
-- (20260926001300_sync_program_one_code.sql): a plain PATCH of
-- submissions.verified_text, as an older branch sends, reaches Program 1's
-- submission_programs row, which grading reads.
select plan(24);

insert into public.questions (id, question_name, question_text, model_answer, question_type, test_cases)
values
  ('00000000-0000-0000-0013-000000000001', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb),
  ('00000000-0000-0000-0013-000000000002', 'Max', 'Max.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "2"}]'::jsonb);

-- Page A: Program 1 only, graded.
insert into public.submissions (id, image_url, status, question_id, verified_text)
values (
  '00000000-0000-0000-0013-000000000011',
  'https://example.test/storage/v1/object/public/handwritten-submissions/a.jpg',
  'graded', '00000000-0000-0000-0013-000000000001', 'code v1'
);
insert into public.submission_programs (
  id, submission_id, position, question_id, verified_text,
  grading_results, passed_test_cases, total_test_cases, graded_at
)
values (
  '00000000-0000-0000-0013-000000000021',
  '00000000-0000-0000-0013-000000000011', 1,
  '00000000-0000-0000-0013-000000000001', 'code v1',
  '[{"passed": true}]'::jsonb, 1, 1, now()
);

-- Page B: Programs 1 and 2, both graded.
insert into public.submissions (id, image_url, status, question_id, verified_text)
values (
  '00000000-0000-0000-0013-000000000012',
  'https://example.test/storage/v1/object/public/handwritten-submissions/b.jpg',
  'graded', '00000000-0000-0000-0013-000000000002', 'b one'
);
insert into public.submission_programs (
  id, submission_id, position, question_id, verified_text,
  grading_results, passed_test_cases, total_test_cases, graded_at
)
values
  ('00000000-0000-0000-0013-000000000031', '00000000-0000-0000-0013-000000000012', 1,
   '00000000-0000-0000-0013-000000000002', 'b one', '[{"passed": true}]'::jsonb, 1, 1, now()),
  ('00000000-0000-0000-0013-000000000032', '00000000-0000-0000-0013-000000000012', 2,
   '00000000-0000-0000-0013-000000000001', 'b two', '[{"passed": true}]'::jsonb, 1, 1, now());

create temporary table results (step text, value bigint);
grant insert, select on table results to anon;

-- ── A plain PATCH of the page's code reaches Program 1 ──────────────────
insert into results
select 'before patch', grading_revision
from public.submissions where id = '00000000-0000-0000-0013-000000000011';

set local role anon;
with changed as (
  update public.submissions
  set verified_text = 'code v2', status = 'verified', verified_at = now()
  where id = '00000000-0000-0000-0013-000000000011'
  returning grading_revision
)
insert into results select 'patch', grading_revision from changed;
reset role;

select is(
  (select verified_text from public.submission_programs
   where submission_id = '00000000-0000-0000-0013-000000000011' and position = 1),
  'code v2',
  'a PATCH of the page code updates Program 1''s code'
);
select ok(
  (select grading_results = '[]'::jsonb and passed_test_cases is null
     and total_test_cases is null and graded_at is null
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0013-000000000011' and position = 1),
  'the PATCH clears Program 1''s grade'
);
select is(
  (select id from public.submission_programs
   where submission_id = '00000000-0000-0000-0013-000000000011' and position = 1),
  '00000000-0000-0000-0013-000000000021'::uuid,
  'Program 1 is updated in place, not replaced'
);
select is(
  (select value from results where step = 'patch'),
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0013-000000000011'),
  'the PATCH returns the page''s final revision'
);
select is(
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0013-000000000011'),
  (select value + 1 from results where step = 'before patch'),
  'the PATCH advances the page revision exactly once'
);
select is(
  (select status from public.submissions where id = '00000000-0000-0000-0013-000000000011'),
  'verified',
  'the page is no longer graded'
);

-- ── A PATCH that changes nothing relevant leaves Program 1 alone ────────
set local role anon;
insert into results
select 'grade', public.save_program_grade(
  '00000000-0000-0000-0013-000000000021',
  (select grading_revision from public.submission_programs
   where id = '00000000-0000-0000-0013-000000000021'),
  '00000000-0000-0000-0013-000000000001', 'code v2', '[{"passed": true}]'::jsonb
);
reset role;

insert into results
select 'program before topic', grading_revision
from public.submission_programs where id = '00000000-0000-0000-0013-000000000021';
insert into results
select 'page before topic', grading_revision
from public.submissions where id = '00000000-0000-0000-0013-000000000011';

set local role anon;
update public.submissions
set topic = 'Loops', verified_text = 'code v2'
where id = '00000000-0000-0000-0013-000000000011';
reset role;

select ok(
  (select graded_at is not null and passed_test_cases = 1
     and grading_revision = (select value from results where step = 'program before topic')
   from public.submission_programs where id = '00000000-0000-0000-0013-000000000021'),
  'a topic-only PATCH (same code) keeps Program 1 and its grade'
);
select is(
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0013-000000000011'),
  (select value from results where step = 'page before topic'),
  'a topic-only PATCH leaves the page revision alone'
);
select is(
  (select status from public.submissions where id = '00000000-0000-0000-0013-000000000011'),
  'graded',
  'the page stays graded'
);

-- ── A question-only change moves Program 1 and keeps its code ───────────
set local role anon;
update public.submissions
set question_id = '00000000-0000-0000-0013-000000000002'
where id = '00000000-0000-0000-0013-000000000011';
reset role;

select ok(
  (select question_id = '00000000-0000-0000-0013-000000000002'
     and verified_text = 'code v2' and graded_at is null
   from public.submission_programs where id = '00000000-0000-0000-0013-000000000021'),
  'a new question moves Program 1 (code kept, grade cleared)'
);

-- ── Blanking the page code deletes Program 1 ─────────────────────────────
set local role anon;
with changed as (
  update public.submissions
  set verified_text = '   '
  where id = '00000000-0000-0000-0013-000000000011'
  returning grading_revision
)
insert into results select 'blank', grading_revision from changed;
reset role;

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0013-000000000011'),
  0::bigint,
  'blanking the page code deletes Program 1'
);
select is(
  (select value from results where step = 'blank'),
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0013-000000000011'),
  'the blanking PATCH returns the page''s final revision'
);

-- ── New code on a page with a question but no Program 1 creates it ──────
set local role anon;
with changed as (
  update public.submissions
  set verified_text = 'code v3'
  where id = '00000000-0000-0000-0013-000000000011'
  returning grading_revision
)
insert into results select 'recreate', grading_revision from changed;
reset role;

select ok(
  (select question_id = '00000000-0000-0000-0013-000000000002'
     and verified_text = 'code v3' and graded_at is null
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0013-000000000011' and position = 1),
  'new code on a page with a question creates Program 1'
);
select is(
  (select value from results where step = 'recreate'),
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0013-000000000011'),
  'the creating PATCH returns the page''s final revision'
);

-- ── NULL code deletes Program 1 too ──────────────────────────────────────
set local role anon;
update public.submissions
set verified_text = null
where id = '00000000-0000-0000-0013-000000000011';
reset role;

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0013-000000000011'),
  0::bigint,
  'clearing the page code to NULL deletes Program 1'
);

-- ── Code and question changed in one PATCH ───────────────────────────────
set local role anon;
update public.submissions
set question_id = '00000000-0000-0000-0013-000000000001', verified_text = 'code v4'
where id = '00000000-0000-0000-0013-000000000011';
reset role;

select ok(
  (select question_id = '00000000-0000-0000-0013-000000000001' and verified_text = 'code v4'
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0013-000000000011' and position = 1),
  'a PATCH of code and question gives Program 1 both'
);

-- ── save_submission_programs() behaves as before ─────────────────────────
set local role anon;
insert into results
select 'save', public.save_submission_programs(
  '00000000-0000-0000-0013-000000000012',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0013-000000000012'),
  '[{"verified_text": "b one, edited"},
    {"verified_text": "b two", "question_id": "00000000-0000-0000-0013-000000000001"}]'::jsonb
);
reset role;

select is(
  (select value from results where step = 'save'),
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0013-000000000012'),
  'the save returns the page''s stored revision'
);
select is(
  (select array_agg(id::text || ':' || position || ':' || verified_text order by position)
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0013-000000000012'),
  array[
    '00000000-0000-0000-0013-000000000031:1:b one, edited',
    '00000000-0000-0000-0013-000000000032:2:b two'
  ],
  'the save leaves exactly Programs 1 and 2, updated in place'
);
select ok(
  (select graded_at is null from public.submission_programs
   where id = '00000000-0000-0000-0013-000000000031')
  and (select graded_at is not null from public.submission_programs
   where id = '00000000-0000-0000-0013-000000000032'),
  'the save clears only the edited Program 1''s grade'
);
select is(
  (select verified_text from public.submissions where id = '00000000-0000-0000-0013-000000000012'),
  'b one, edited',
  'the save still mirrors Program 1 on the page'
);

-- A save from before it is refused.
set local role anon;
insert into results
select 'stale save', public.save_submission_programs(
  '00000000-0000-0000-0013-000000000012',
  (select value - 1 from results where step = 'save'),
  '[{"verified_text": "b one"}]'::jsonb
);
reset role;

select is((select value from results where step = 'stale save'), null::bigint,
  'a save from an older revision is still refused');

-- A save that empties Program 1 keeps Program 2.
set local role anon;
insert into results
select 'save blank', public.save_submission_programs(
  '00000000-0000-0000-0013-000000000012',
  (select value from results where step = 'save'),
  '[{"verified_text": ""},
    {"verified_text": "b two", "question_id": "00000000-0000-0000-0013-000000000001"}]'::jsonb
);
reset role;

select is(
  (select array_agg(id::text || ':' || position order by position)
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0013-000000000012'),
  array['00000000-0000-0000-0013-000000000032:2'],
  'a save that empties Program 1 deletes it and keeps Program 2 and its tab'
);
select is(
  (select value from results where step = 'save blank'),
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0013-000000000012'),
  'that save returns the page''s stored revision'
);
select cmp_ok(
  (select value from results where step = 'save blank'),
  '>',
  (select value from results where step = 'save'),
  'that save advances the page revision'
);

select * from finish();

rollback;
