begin;

-- Follow-ups to the 2026-09-26 review: the #4 edge case (a leftover
-- page-level grade) and the security-advisor warning on
-- advance_page_revision().
select plan(9);

insert into public.questions (id, question_name, question_text, model_answer, question_type, test_cases)
values
  ('00000000-0000-0000-0012-000000000001', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb),
  ('00000000-0000-0000-0012-000000000002', 'Max', 'Max.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "2"}]'::jsonb),
  ('00000000-0000-0000-0012-000000000003', 'Min', 'Min.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "1"}]'::jsonb);

-- A page given code, a question and a page-level grade directly in the
-- database, with no program rows (never through the review).
insert into public.submissions (
  id, image_url, status, question_id, verified_text,
  grading_results, passed_test_cases, total_test_cases, graded_at
)
values (
  '00000000-0000-0000-0012-000000000011',
  'https://example.test/storage/v1/object/public/handwritten-submissions/f.jpg',
  'graded', '00000000-0000-0000-0012-000000000001', 'old code',
  '[{"passed": true}]'::jsonb, 1, 1, now()
);
delete from public.submission_programs
where submission_id = '00000000-0000-0000-0012-000000000011';

-- ── The advisor warning: nothing SECURITY DEFINER is callable by the browser
select ok(
  to_regprocedure('public.advance_page_revision(uuid)') is null,
  'advance_page_revision() no longer exists'
);

select is(
  (select count(*)
   from pg_proc p
   join pg_namespace n on n.oid = p.pronamespace
   where n.nspname = 'public'
     and p.prosecdef
     and has_function_privilege('anon', p.oid, 'EXECUTE')),
  0::bigint,
  'no SECURITY DEFINER function in public is executable by anon'
);

create temporary table results (step text, value bigint);
grant insert, select on table results to anon;

-- ── #4 edge case: saving the review clears the leftover page-level grade
set local role anon;
insert into results
select 'save', public.save_submission_programs(
  '00000000-0000-0000-0012-000000000011',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0012-000000000011'),
  '[{"verified_text": "old code"},
    {"verified_text": "two", "question_id": "00000000-0000-0000-0012-000000000002"}]'::jsonb
);
reset role;

select ok(
  (select grading_results = '[]'::jsonb and passed_test_cases is null
     and total_test_cases is null and graded_at is null
   from public.submissions where id = '00000000-0000-0000-0012-000000000011'),
  'once a page has programs, its leftover page-level grade is cleared'
);

select is(
  (select value from results where step = 'save'),
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0012-000000000011'),
  'the save returns the page''s final revision'
);

-- ── The revision still moves on any program change, from any writer ─────
insert into results
select 'before direct edit', grading_revision
from public.submissions where id = '00000000-0000-0000-0012-000000000011';

set local role anon;
update public.submission_programs
set verified_text = 'two, edited directly'
where submission_id = '00000000-0000-0000-0012-000000000011' and position = 2;
reset role;

select cmp_ok(
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0012-000000000011'),
  '>',
  (select value from results where step = 'before direct edit'),
  'editing a program directly advances the page revision too'
);

-- A save from before that edit is refused.
set local role anon;
insert into results
select 'stale', public.save_submission_programs(
  '00000000-0000-0000-0012-000000000011',
  (select value from results where step = 'before direct edit'),
  '[{"verified_text": "old code"}]'::jsonb
);
reset role;

select is((select value from results where step = 'stale'), null::bigint,
  'a save from before a program edit is refused');

-- Grading a program does not move the page revision (no self-conflict).
insert into results
select 'before grade', grading_revision
from public.submissions where id = '00000000-0000-0000-0012-000000000011';

set local role anon;
insert into results
select 'grade', public.save_program_grade(
  (select id from public.submission_programs
   where submission_id = '00000000-0000-0000-0012-000000000011' and position = 1),
  (select grading_revision from public.submission_programs
   where submission_id = '00000000-0000-0000-0012-000000000011' and position = 1),
  '00000000-0000-0000-0012-000000000001', 'old code', '[{"passed": true}]'::jsonb
);
reset role;

select is(
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0012-000000000011'),
  (select value from results where step = 'before grade'),
  'grading a program leaves the page revision alone'
);

-- ── The Details save returns the revision the page really has ───────────
create temporary table details_result (revision bigint);
grant insert, select on table details_result to anon;

set local role anon;
with changed as (
  update public.submissions
  set question_id = '00000000-0000-0000-0012-000000000003'
  where id = '00000000-0000-0000-0012-000000000011'
  returning grading_revision
)
insert into details_result select grading_revision from changed;
reset role;

select is(
  (select revision from details_result),
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0012-000000000011'),
  'a Details question change returns the page''s final revision'
);
select ok(
  (select question_id = '00000000-0000-0000-0012-000000000003'
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0012-000000000011' and position = 1),
  'Program 1 still follows the page''s question'
);

select * from finish();

rollback;
