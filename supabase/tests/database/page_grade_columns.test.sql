begin;

-- Review 2026-09-26, finding #4 (docs/reviews/2026-09-26-judge0-integration-code-review.md):
-- the page row's grade columns are used only for pages without programs.
select plan(8);

-- The migration cleared the page-level grade of every page that has programs.
select is(
  (select count(*) from public.submissions as page
   where exists (
       select 1 from public.submission_programs as program
       where program.submission_id = page.id
     )
     and (
       page.grading_results is distinct from '[]'::jsonb
       or page.passed_test_cases is not null
       or page.total_test_cases is not null
       or page.graded_at is not null
     )),
  0::bigint,
  'no page with programs keeps a page-level grade'
);

insert into public.questions (id, question_name, question_text, model_answer, question_type, test_cases)
values
  ('00000000-0000-0000-0004-000000000001', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb),
  ('00000000-0000-0000-0004-000000000002', 'Max', 'Max.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "2"}]'::jsonb);

insert into public.submissions (id, image_url, status, question_id, verified_text)
values
  -- A page reviewed into two programs.
  ('00000000-0000-0000-0004-000000000021',
   'https://example.test/storage/v1/object/public/handwritten-submissions/a.jpg',
   'extracted', '00000000-0000-0000-0004-000000000001', null),
  -- A page with code and a question but no program rows (legacy path).
  ('00000000-0000-0000-0004-000000000022',
   'https://example.test/storage/v1/object/public/handwritten-submissions/b.jpg',
   'verified', '00000000-0000-0000-0004-000000000001', 'legacy code');

create temporary table results (step text, value bigint);
grant insert, select on table results to anon;

set local role anon;
insert into results
select 'programs saved', public.save_submission_programs(
  '00000000-0000-0000-0004-000000000021', 0,
  '[{"verified_text": "one"},
    {"verified_text": "two", "question_id": "00000000-0000-0000-0004-000000000002"}]'::jsonb
);
-- The legacy page-level save, with everything else matching Program 1.
insert into results
select 'page grade on programs page', public.save_submission_grade(
  '00000000-0000-0000-0004-000000000021',
  (select value from results where step = 'programs saved'),
  '00000000-0000-0000-0004-000000000001', 'one', '[{"passed": true}]'::jsonb
);
insert into results
select 'legacy page grade', public.save_submission_grade(
  '00000000-0000-0000-0004-000000000022', 0,
  '00000000-0000-0000-0004-000000000001', 'legacy code',
  '[{"passed": true}, {"passed": false}]'::jsonb
);
reset role;

-- ── save_submission_grade() refuses a page that has programs ────────────
select is(
  (select value from results where step = 'page grade on programs page'),
  null::bigint,
  'save_submission_grade returns NULL for a page with programs'
);

select ok(
  (select grading_results = '[]'::jsonb
     and passed_test_cases is null
     and total_test_cases is null
     and graded_at is null
     and status = 'verified'
     and grading_revision = (select value from results where step = 'programs saved')
   from public.submissions
   where id = '00000000-0000-0000-0004-000000000021'),
  'the refused save leaves the page''s grade, status and revision untouched'
);

-- ── ...but still grades a page without programs ─────────────────────────
select is(
  (select value from results where step = 'legacy page grade'),
  1::bigint,
  'save_submission_grade still grades a page without programs'
);

select ok(
  (select passed_test_cases = 1
     and total_test_cases = 2
     and graded_at is not null
     and status = 'graded'
   from public.submissions
   where id = '00000000-0000-0000-0004-000000000022'),
  'the page without programs holds its page-level grade'
);

-- ── Grading every program: the page is graded, its own columns stay empty ─
set local role anon;
insert into results
select 'grade program ' || program.position, public.save_program_grade(
  program.id, program.grading_revision, program.question_id,
  program.verified_text, '[{"passed": true}]'::jsonb
)
from public.submission_programs as program
where program.submission_id = '00000000-0000-0000-0004-000000000021';
reset role;

select ok(
  (select status = 'graded' from public.submissions
   where id = '00000000-0000-0000-0004-000000000021'),
  'the page is graded once every program is graded'
);

select ok(
  (select grading_results = '[]'::jsonb
     and passed_test_cases is null
     and total_test_cases is null
     and score_percent is null
     and graded_at is null
   from public.submissions
   where id = '00000000-0000-0000-0004-000000000021'),
  'the graded page keeps its page-level grade columns empty'
);

select is(
  (select grading_revision from public.submissions
   where id = '00000000-0000-0000-0004-000000000021'),
  (select value from results where step = 'programs saved'),
  'grading programs does not advance the page revision'
);

select * from finish();

rollback;
