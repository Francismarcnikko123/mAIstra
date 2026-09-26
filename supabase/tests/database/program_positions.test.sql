begin;

-- Review 2026-09-26, finding #9 (docs/reviews/2026-09-26-judge0-integration-code-review.md):
-- Programs 2+ are matched to their rows by question, not by tab number, so
-- clearing or reordering tabs keeps the grades of programs that didn't change.
select plan(21);

insert into public.questions (id, question_name, question_text, model_answer, question_type, test_cases)
values
  ('00000000-0000-0000-0009-000000000001', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb),
  ('00000000-0000-0000-0009-000000000002', 'Max', 'Max.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "2"}]'::jsonb),
  ('00000000-0000-0000-0009-000000000003', 'Min', 'Min.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "1"}]'::jsonb),
  ('00000000-0000-0000-0009-000000000004', 'Avg', 'Avg.', 'x', 'program', '[{"test_input": "2 4", "expected_output": "3"}]'::jsonb);

insert into public.submissions (id, image_url, status, question_id)
values (
  '00000000-0000-0000-0009-000000000011',
  'https://example.test/storage/v1/object/public/handwritten-submissions/positions.jpg',
  'extracted', '00000000-0000-0000-0009-000000000001'
);

create temporary table results (step text, value bigint);
grant insert, select on table results to anon;

-- ── Three programs, 2 and 3 graded ──────────────────────────────────────
set local role anon;
insert into results
select 'three tabs', public.save_submission_programs(
  '00000000-0000-0000-0009-000000000011', 0,
  '[{"verified_text": "one", "question_id": "00000000-0000-0000-0009-000000000001"},
    {"verified_text": "two", "question_id": "00000000-0000-0000-0009-000000000002"},
    {"verified_text": "three", "question_id": "00000000-0000-0000-0009-000000000003"}]'::jsonb
);
insert into results
select 'grade ' || program.position, public.save_program_grade(
  program.id, program.grading_revision, program.question_id, program.verified_text,
  '[{"passed": true}]'::jsonb
)
from public.submission_programs as program
where program.submission_id = '00000000-0000-0000-0009-000000000011'
  and program.position in (2, 3);
reset role;

create temporary table before_clear as
select id, position, question_id, verified_text, graded_at, grading_revision
from public.submission_programs
where submission_id = '00000000-0000-0000-0009-000000000011';

-- ── Clearing the middle tab: the web sends [P1, P3] ─────────────────────
set local role anon;
insert into results
select 'clear middle', public.save_submission_programs(
  '00000000-0000-0000-0009-000000000011',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0009-000000000011'),
  '[{"verified_text": "one", "question_id": "00000000-0000-0000-0009-000000000001"},
    {"verified_text": "three", "question_id": "00000000-0000-0000-0009-000000000003"}]'::jsonb
);
reset role;

select cmp_ok(
  (select value from results where step = 'clear middle'),
  '>',
  (select value from results where step = 'three tabs'),
  'clearing a tab advances the page revision'
);

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0009-000000000011'),
  2::bigint,
  'two programs are left after clearing the middle tab'
);

select ok(
  (select program.position = 2
     and program.question_id = '00000000-0000-0000-0009-000000000003'
     and program.verified_text = 'three'
     and program.graded_at is not null
     and program.graded_at = old.graded_at
     and program.grading_revision = old.grading_revision
   from public.submission_programs as program
   join before_clear as old on old.id = program.id
   where old.position = 3),
  'Program 3 keeps its row and grade, now at position 2'
);

select ok(
  not exists (
    select 1 from public.submission_programs
    where id = (select id from before_clear where position = 2)
  ),
  'Program 2 (the cleared tab) is deleted'
);

select ok(
  (select program.position = 1
   from public.submission_programs as program
   join before_clear as old on old.id = program.id
   where old.position = 1),
  'Program 1 keeps its row at position 1'
);

-- ── Add a third tab again, grade it ────────────────────────────────────
set local role anon;
insert into results
select 'add fourth question', public.save_submission_programs(
  '00000000-0000-0000-0009-000000000011',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0009-000000000011'),
  '[{"verified_text": "one", "question_id": "00000000-0000-0000-0009-000000000001"},
    {"verified_text": "three", "question_id": "00000000-0000-0000-0009-000000000003"},
    {"verified_text": "four", "question_id": "00000000-0000-0000-0009-000000000004"}]'::jsonb
);
insert into results
select 'grade four', public.save_program_grade(
  program.id, program.grading_revision, program.question_id, program.verified_text,
  '[{"passed": true}, {"passed": false}]'::jsonb
)
from public.submission_programs as program
where program.submission_id = '00000000-0000-0000-0009-000000000011'
  and program.position = 3;
reset role;

create temporary table before_reorder as
select id, position, question_id, verified_text, graded_at, grading_revision
from public.submission_programs
where submission_id = '00000000-0000-0000-0009-000000000011';

-- ── Reordering two tabs (code and question move together) ──────────────
set local role anon;
insert into results
select 'reorder', public.save_submission_programs(
  '00000000-0000-0000-0009-000000000011',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0009-000000000011'),
  '[{"verified_text": "one", "question_id": "00000000-0000-0000-0009-000000000001"},
    {"verified_text": "four", "question_id": "00000000-0000-0000-0009-000000000004"},
    {"verified_text": "three", "question_id": "00000000-0000-0000-0009-000000000003"}]'::jsonb
);
reset role;

select cmp_ok(
  (select value from results where step = 'reorder'),
  '>',
  (select value from results where step = 'grade four'),
  'a pure reorder still advances the page revision'
);

select ok(
  (select bool_and(
      program.position = case old.position when 2 then 3 when 3 then 2 else 1 end
      and program.graded_at is not distinct from old.graded_at
      and program.grading_revision = old.grading_revision)
   from public.submission_programs as program
   join before_reorder as old on old.id = program.id),
  'reordered programs keep their rows and grades at their new positions'
);

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0009-000000000011' and graded_at is not null),
  2::bigint,
  'both graded programs are still graded after the reorder'
);

-- ── Swapping only the questions of two tabs (code stays on its tab) ─────
set local role anon;
insert into results
select 'swap questions', public.save_submission_programs(
  '00000000-0000-0000-0009-000000000011',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0009-000000000011'),
  '[{"verified_text": "one", "question_id": "00000000-0000-0000-0009-000000000001"},
    {"verified_text": "four", "question_id": "00000000-0000-0000-0009-000000000003"},
    {"verified_text": "three", "question_id": "00000000-0000-0000-0009-000000000004"}]'::jsonb
);
reset role;

select isnt((select value from results where step = 'swap questions'), null::bigint,
  'two tabs can swap questions in one save');

select results_eq(
  $$ select position, question_id, verified_text, graded_at is null
     from public.submission_programs
     where submission_id = '00000000-0000-0000-0009-000000000011'
     order by position $$,
  $$ values
       (1::smallint, '00000000-0000-0000-0009-000000000001'::uuid, 'one', true),
       (2::smallint, '00000000-0000-0000-0009-000000000003'::uuid, 'four', true),
       (3::smallint, '00000000-0000-0000-0009-000000000004'::uuid, 'three', true) $$,
  'swapped questions pair each tab''s code with its new question, and both grades are cleared'
);

select ok(
  (select status = 'verified' from public.submissions
   where id = '00000000-0000-0000-0009-000000000011'),
  'the page is not graded after the swap'
);

-- ── Editing a program's code still clears its grade ────────────────────
set local role anon;
insert into results
select 'regrade ' || program.position, public.save_program_grade(
  program.id, program.grading_revision, program.question_id, program.verified_text,
  '[{"passed": true}]'::jsonb
)
from public.submission_programs as program
where program.submission_id = '00000000-0000-0000-0009-000000000011'
  and program.position in (2, 3);
reset role;

create temporary table before_edit as
select id, position, question_id, verified_text, graded_at, grading_revision
from public.submission_programs
where submission_id = '00000000-0000-0000-0009-000000000011';

set local role anon;
insert into results
select 'edit code', public.save_submission_programs(
  '00000000-0000-0000-0009-000000000011',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0009-000000000011'),
  '[{"verified_text": "one", "question_id": "00000000-0000-0000-0009-000000000001"},
    {"verified_text": "four, fixed", "question_id": "00000000-0000-0000-0009-000000000003"},
    {"verified_text": "three", "question_id": "00000000-0000-0000-0009-000000000004"}]'::jsonb
);
reset role;

select ok(
  (select program.id = old.id
     and program.graded_at is null
     and program.grading_revision = old.grading_revision + 1
     and program.verified_text = 'four, fixed'
   from public.submission_programs as program
   join before_edit as old on old.position = program.position
   where program.submission_id = '00000000-0000-0000-0009-000000000011'
     and program.position = 2),
  'editing a program''s code keeps its row but clears its grade'
);

select ok(
  (select program.id = old.id
     and program.graded_at = old.graded_at
     and program.grading_revision = old.grading_revision
   from public.submission_programs as program
   join before_edit as old on old.position = program.position
   where program.submission_id = '00000000-0000-0000-0009-000000000011'
     and program.position = 3),
  'the unedited program keeps its grade'
);

-- ── A stale page revision writes nothing ───────────────────────────────
create temporary table before_stale as
select id, position, question_id, verified_text, graded_at, grading_revision
from public.submission_programs
where submission_id = '00000000-0000-0000-0009-000000000011';
create temporary table page_before_stale as
select verified_text, question_id, grading_revision, status
from public.submissions
where id = '00000000-0000-0000-0009-000000000011';

set local role anon;
insert into results
select 'stale', public.save_submission_programs(
  '00000000-0000-0000-0009-000000000011',
  (select value from results where step = 'three tabs'),
  '[{"verified_text": "stale one", "question_id": "00000000-0000-0000-0009-000000000001"},
    {"verified_text": "three", "question_id": "00000000-0000-0000-0009-000000000004"}]'::jsonb
);
reset role;

select is((select value from results where step = 'stale'), null::bigint,
  'a save against a stale page revision returns NULL');

select results_eq(
  $$ select id, position, question_id, verified_text, graded_at, grading_revision
     from public.submission_programs
     where submission_id = '00000000-0000-0000-0009-000000000011'
     order by position $$,
  $$ select id, position, question_id, verified_text, graded_at, grading_revision
     from before_stale order by position $$,
  'a stale save changes no program'
);

select results_eq(
  $$ select verified_text, question_id, grading_revision, status
     from public.submissions where id = '00000000-0000-0000-0009-000000000011' $$,
  $$ select verified_text, question_id, grading_revision, status from page_before_stale $$,
  'a stale save leaves the page row alone'
);

-- ── p_replace_all = false with Program 1 only ──────────────────────────
set local role anon;
insert into results
select 'program 1 only', public.save_submission_programs(
  '00000000-0000-0000-0009-000000000011',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0009-000000000011'),
  '[{"verified_text": "one, edited"}]'::jsonb,
  null,
  false
);
reset role;

select isnt((select value from results where step = 'program 1 only'), null::bigint,
  'saving Program 1 alone succeeds');

select ok(
  (select verified_text = 'one, edited'
     and question_id = '00000000-0000-0000-0009-000000000001'
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0009-000000000011' and position = 1),
  'Program 1 alone is saved with the page''s question'
);

select results_eq(
  $$ select id, position, question_id, verified_text, graded_at, grading_revision
     from public.submission_programs
     where submission_id = '00000000-0000-0000-0009-000000000011' and position > 1
     order by position $$,
  $$ select id, position, question_id, verified_text, graded_at, grading_revision
     from before_stale where position > 1 order by position $$,
  'saving only Program 1 leaves Programs 2+ untouched'
);

-- ── One question per page still holds ──────────────────────────────────
select throws_ok(
  $$
    set constraints all immediate;
    select public.save_submission_programs(
      '00000000-0000-0000-0009-000000000011',
      (select grading_revision from public.submissions where id = '00000000-0000-0000-0009-000000000011'),
      '[{"verified_text": "one, edited", "question_id": "00000000-0000-0000-0009-000000000001"},
        {"verified_text": "dup a", "question_id": "00000000-0000-0000-0009-000000000002"},
        {"verified_text": "dup b", "question_id": "00000000-0000-0000-0009-000000000002"}]'::jsonb
    );
  $$,
  '23505',
  null,
  'two tabs cannot share a question'
);
set constraints all deferred;

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0009-000000000011'),
  3::bigint,
  'the refused save wrote nothing'
);

select * from finish();

rollback;
