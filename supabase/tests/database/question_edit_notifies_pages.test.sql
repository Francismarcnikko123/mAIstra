begin;

-- Review 2026-09-26, finding #5 (docs/reviews/2026-09-26-judge0-integration-code-review.md):
-- editing a question must touch every page with a program linked to it, so a
-- realtime UPDATE on submissions reaches open pages.
select plan(13);

-- Q_A (…01) is the question that gets edited.
insert into public.questions (id, question_name, question_text, model_answer, question_type, test_cases)
values
  ('00000000-0000-0000-0005-000000000001', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb),
  ('00000000-0000-0000-0005-000000000002', 'Max', 'Max.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "2"}]'::jsonb),
  ('00000000-0000-0000-0005-000000000003', 'Min', 'Min.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "1"}]'::jsonb);

-- …11: Program 1 on Q_B (ungraded), Program 2 on Q_A (graded)  -> 'verified'
-- …12: Program 1 on Q_A, Program 2 on Q_B, both graded          -> 'graded'
-- …13: Program 1 on Q_C, Program 2 on Q_A, both graded          -> 'graded'
-- …14: Program 1 on Q_B, Program 2 on Q_C, both graded (no Q_A)  -> 'graded'
insert into public.submissions (id, image_url, status, question_id)
values
  ('00000000-0000-0000-0005-000000000011',
   'https://example.test/storage/v1/object/public/handwritten-submissions/a.jpg',
   'extracted', '00000000-0000-0000-0005-000000000002'),
  ('00000000-0000-0000-0005-000000000012',
   'https://example.test/storage/v1/object/public/handwritten-submissions/b.jpg',
   'extracted', '00000000-0000-0000-0005-000000000001'),
  ('00000000-0000-0000-0005-000000000013',
   'https://example.test/storage/v1/object/public/handwritten-submissions/c.jpg',
   'extracted', '00000000-0000-0000-0005-000000000003'),
  ('00000000-0000-0000-0005-000000000014',
   'https://example.test/storage/v1/object/public/handwritten-submissions/d.jpg',
   'extracted', '00000000-0000-0000-0005-000000000002');

create temporary table results (step text, value bigint);
grant insert, select on table results to anon;

-- ── Fixtures through the functions the review uses ───────────────────────
set local role anon;
insert into results
select 'save 11', public.save_submission_programs(
  '00000000-0000-0000-0005-000000000011', 0,
  '[{"verified_text": "one"},
    {"verified_text": "two", "question_id": "00000000-0000-0000-0005-000000000001"}]'::jsonb
);
insert into results
select 'save 12', public.save_submission_programs(
  '00000000-0000-0000-0005-000000000012', 0,
  '[{"verified_text": "one"},
    {"verified_text": "two", "question_id": "00000000-0000-0000-0005-000000000002"}]'::jsonb
);
insert into results
select 'save 13', public.save_submission_programs(
  '00000000-0000-0000-0005-000000000013', 0,
  '[{"verified_text": "one"},
    {"verified_text": "two", "question_id": "00000000-0000-0000-0005-000000000001"}]'::jsonb
);
insert into results
select 'save 14', public.save_submission_programs(
  '00000000-0000-0000-0005-000000000014', 0,
  '[{"verified_text": "one"},
    {"verified_text": "two", "question_id": "00000000-0000-0000-0005-000000000003"}]'::jsonb
);

-- Grade: page …11 Program 2 only; every program on …12, …13 and …14.
insert into results
select 'grade ' || program.submission_id || ' ' || program.position,
  public.save_program_grade(
    program.id, program.grading_revision, program.question_id,
    program.verified_text, '[{"passed": true}, {"passed": false}]'::jsonb
  )
from public.submission_programs program
where program.submission_id in (
    '00000000-0000-0000-0005-000000000012',
    '00000000-0000-0000-0005-000000000013',
    '00000000-0000-0000-0005-000000000014'
  )
  or (program.submission_id = '00000000-0000-0000-0005-000000000011'
      and program.position = 2);
reset role;

create temporary table pages_before as
select id, grading_revision, status from public.submissions
where id::text like '00000000-0000-0000-0005-%';
grant select on table pages_before to anon;

select results_eq(
  $$ select right(id::text, 2), status from pages_before order by id $$,
  $$ values ('11', 'verified'), ('12', 'graded'), ('13', 'graded'), ('14', 'graded') $$,
  'fixtures: page statuses before the question edit'
);

create temporary table programs_before as
select submission_id, position, grading_revision, graded_at
from public.submission_programs
where submission_id::text like '00000000-0000-0000-0005-%';

-- ── The edit: Q_A's test cases change, from the browser ──────────────────
set local role anon;
update public.questions
set test_cases = '[{"test_input": "2 2", "expected_output": "4"}]'::jsonb
where id = '00000000-0000-0000-0005-000000000001';
reset role;

-- ── Page …11: 'verified', only Program 2 uses Q_A ────────────────────────
select is(
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0005-000000000011'),
  (select grading_revision + 1 from pages_before where id = '00000000-0000-0000-0005-000000000011'),
  'a verified page whose Program 2 uses the edited question has its revision advanced'
);

select ok(
  (select graded_at is null and passed_test_cases is null and total_test_cases is null
     and grading_results = '[]'::jsonb
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0005-000000000011' and position = 2),
  'Program 2''s grade is cleared'
);

select is(
  (select status from public.submissions where id = '00000000-0000-0000-0005-000000000011'),
  'verified',
  'the verified page stays verified'
);

select is(
  (select grading_revision from public.submission_programs
   where submission_id = '00000000-0000-0000-0005-000000000011' and position = 1),
  (select grading_revision from programs_before
   where submission_id = '00000000-0000-0000-0005-000000000011' and position = 1),
  'Program 1, on another question, is not touched'
);

-- A review opened before the edit is refused on its next save.
set local role anon;
insert into results
select 'stale save 11', public.save_submission_programs(
  '00000000-0000-0000-0005-000000000011',
  (select grading_revision from pages_before where id = '00000000-0000-0000-0005-000000000011'),
  '[{"verified_text": "one"},
    {"verified_text": "two", "question_id": "00000000-0000-0000-0005-000000000001"}]'::jsonb
);
reset role;

select is(
  (select value from results where step = 'stale save 11'),
  null::bigint,
  'a save from before the question edit reports a conflict'
);

-- ── Page …12: its own question_id is Q_A ─────────────────────────────────
select is(
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0005-000000000012'),
  (select grading_revision + 1 from pages_before where id = '00000000-0000-0000-0005-000000000012'),
  'a page whose Program 1 uses the question is advanced exactly once'
);

select ok(
  (select status = 'verified' from public.submissions where id = '00000000-0000-0000-0005-000000000012')
  and (select graded_at is null from public.submission_programs
       where submission_id = '00000000-0000-0000-0005-000000000012' and position = 1),
  'that page is no longer graded and its Program 1 grade is cleared'
);

select ok(
  (select graded_at is not null from public.submission_programs
   where submission_id = '00000000-0000-0000-0005-000000000012' and position = 2),
  'its Program 2, on another question, keeps its grade'
);

-- ── Page …13: 'graded', Program 2 uses Q_A ───────────────────────────────
select is(
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0005-000000000013'),
  (select grading_revision + 1 from pages_before where id = '00000000-0000-0000-0005-000000000013'),
  'a graded page whose Program 2 uses the question is advanced exactly once'
);

select is(
  (select status from public.submissions where id = '00000000-0000-0000-0005-000000000013'),
  'verified',
  'that page goes back to verified'
);

-- ── Page …14: no program uses Q_A ────────────────────────────────────────
select results_eq(
  $$ select grading_revision, status from public.submissions
     where id = '00000000-0000-0000-0005-000000000014' $$,
  $$ select grading_revision, status from pages_before
     where id = '00000000-0000-0000-0005-000000000014' $$,
  'a page not linked to the question keeps its revision and status'
);

select results_eq(
  $$ select position, grading_revision, graded_at from public.submission_programs
     where submission_id = '00000000-0000-0000-0005-000000000014' order by position $$,
  $$ select position, grading_revision, graded_at from programs_before
     where submission_id = '00000000-0000-0000-0005-000000000014' order by position $$,
  'its programs keep their grades and revisions'
);

select * from finish();

rollback;
