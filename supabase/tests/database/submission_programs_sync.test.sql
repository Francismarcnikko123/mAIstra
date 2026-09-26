begin;

-- Review 2026-09-26, findings #1 and #2 (docs/reviews/2026-09-26-judge0-integration-code-review.md).
select plan(9);

insert into public.questions (id, question_name, question_text, model_answer, question_type, test_cases)
values
  ('00000000-0000-0000-0000-00000000e001', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb),
  ('00000000-0000-0000-0000-00000000e002', 'Max', 'Max.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "2"}]'::jsonb),
  ('00000000-0000-0000-0000-00000000e003', 'Min', 'Min.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "1"}]'::jsonb);

insert into public.submissions (id, image_url, status, question_id)
values
  ('00000000-0000-0000-0000-00000000f001',
   'https://example.test/storage/v1/object/public/handwritten-submissions/a.jpg',
   'extracted', '00000000-0000-0000-0000-00000000e001'),
  ('00000000-0000-0000-0000-00000000f002',
   'https://example.test/storage/v1/object/public/handwritten-submissions/b.jpg',
   'extracted', null);

create temporary table results (step text, value bigint);
grant insert, select on table results to anon;

-- ── #2: a save that changes only Programs 2+ still moves the page revision ─
set local role anon;
insert into results
select 'program 1 only', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000f001', 0,
  '[{"verified_text": "one"}]'::jsonb, null, false
);
-- Teacher A adds Program 2 from the revision both teachers opened.
insert into results
select 'A adds tab', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000f001',
  (select value from results where step = 'program 1 only'),
  '[{"verified_text": "one"},
    {"verified_text": "two", "question_id": "00000000-0000-0000-0000-00000000e002"}]'::jsonb
);
-- Teacher B, still on the revision before A's save, saves only Program 1.
insert into results
select 'B stale', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000f001',
  (select value from results where step = 'program 1 only'),
  '[{"verified_text": "one"}]'::jsonb
);
reset role;

select cmp_ok(
  (select value from results where step = 'A adds tab'),
  '>',
  (select value from results where step = 'program 1 only'),
  'a save that only adds a tab advances the page revision'
);

select is((select value from results where step = 'B stale'), null::bigint,
  'a save from before another teacher''s tab edit is refused');

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000f001'),
  2::bigint,
  'the other teacher''s new tab is not deleted'
);

-- ── #1: changing the page's question (the Details step) moves Program 1 ──
set local role anon;
insert into results
select 'grade one', public.save_program_grade(
  (select id from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000f001' and position = 1),
  0, '00000000-0000-0000-0000-00000000e001', 'one', '[{"passed": true}]'::jsonb
);
-- What updateSubmissionDetails() sends.
update public.submissions
set question_id = '00000000-0000-0000-0000-00000000e003', topic = 'Basic'
where id = '00000000-0000-0000-0000-00000000f001';
reset role;

select ok(
  (select question_id = '00000000-0000-0000-0000-00000000e003' and graded_at is null
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000f001' and position = 1),
  'a new question on Details moves Program 1 to it and clears its grade'
);

select ok(
  (select status = 'verified' from public.submissions
   where id = '00000000-0000-0000-0000-00000000f001'),
  'the page is not graded after Program 1''s question changed'
);

-- The same question as Program 2 is refused: one question per paper.
select throws_ok(
  $$
    set constraints all immediate;
    update public.submissions
    set question_id = '00000000-0000-0000-0000-00000000e002'
    where id = '00000000-0000-0000-0000-00000000f001';
  $$,
  '23505',
  null,
  'Program 1 cannot take the question another program already has'
);
set constraints all deferred;

-- A page whose code was saved before it had a question gets Program 1 once
-- the question is chosen.
update public.submissions
set verified_text = 'code before a question', status = 'verified'
where id = '00000000-0000-0000-0000-00000000f002';

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000f002'),
  0::bigint,
  'no Program 1 row while the page has no question'
);

set local role anon;
update public.submissions
set question_id = '00000000-0000-0000-0000-00000000e001'
where id = '00000000-0000-0000-0000-00000000f002';
reset role;

select ok(
  (select question_id = '00000000-0000-0000-0000-00000000e001'
     and verified_text = 'code before a question'
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000f002' and position = 1),
  'choosing a question creates Program 1 from the page''s saved code'
);

-- Clearing the question removes Program 1 (it can't be graded).
set local role anon;
update public.submissions
set question_id = null
where id = '00000000-0000-0000-0000-00000000f002';
reset role;

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000f002'),
  0::bigint,
  'clearing the question removes Program 1'
);

select * from finish();

rollback;
