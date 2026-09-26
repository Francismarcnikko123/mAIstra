begin;

-- Review 2026-09-26, finding #7 (docs/reviews/2026-09-26-judge0-integration-code-review.md):
-- editing a validated question's model answer, test cases or type clears
-- can_publish on the server.
select plan(9);

insert into public.questions (id, question_name, question_text, model_answer, question_type, test_cases, can_publish)
values
  ('00000000-0000-0000-0007-000000000001', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb, true),
  ('00000000-0000-0000-0007-000000000002', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb, true),
  ('00000000-0000-0000-0007-000000000003', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb, true),
  ('00000000-0000-0000-0007-000000000004', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb, true),
  ('00000000-0000-0000-0007-000000000005', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb, true),
  ('00000000-0000-0000-0007-000000000006', 'Sum', 'Add.', 'x', 'program', '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb, true);

set local role anon;

-- Content changes sent together with can_publish = true.
update public.questions
set test_cases = '[{"test_input": "2 2", "expected_output": "4"}]'::jsonb, can_publish = true
where id = '00000000-0000-0000-0007-000000000001';

update public.questions
set model_answer = 'y', can_publish = true
where id = '00000000-0000-0000-0007-000000000002';

update public.questions
set question_type = 'function', can_publish = true
where id = '00000000-0000-0000-0007-000000000003';

-- A test case edit that doesn't mention can_publish.
update public.questions
set test_cases = '[]'::jsonb
where id = '00000000-0000-0000-0007-000000000004';

-- A rename.
update public.questions
set question_name = 'Sum of two', question_text = 'Add two numbers.'
where id = '00000000-0000-0000-0007-000000000005';

-- Saving the whole form unchanged, still marked validated.
update public.questions
set
  question_name = 'Sum',
  question_text = 'Add.',
  model_answer = 'x',
  question_type = 'program',
  test_cases = '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb,
  can_publish = true
where id = '00000000-0000-0000-0007-000000000006';

reset role;

select is(
  (select can_publish from public.questions where id = '00000000-0000-0000-0007-000000000001'),
  false,
  'changing test cases clears can_publish even when the update sends true'
);

select is(
  (select can_publish from public.questions where id = '00000000-0000-0000-0007-000000000002'),
  false,
  'changing the model answer clears can_publish even when the update sends true'
);

select is(
  (select can_publish from public.questions where id = '00000000-0000-0000-0007-000000000003'),
  false,
  'changing the question type clears can_publish even when the update sends true'
);

select is(
  (select can_publish from public.questions where id = '00000000-0000-0000-0007-000000000004'),
  false,
  'changing test cases without sending can_publish clears it'
);

select is(
  (select can_publish from public.questions where id = '00000000-0000-0000-0007-000000000005'),
  true,
  'renaming a question keeps can_publish'
);

select is(
  (select can_publish from public.questions where id = '00000000-0000-0000-0007-000000000006'),
  true,
  'an update that resends the same content keeps can_publish'
);

-- Validation is its own step after the content is saved.
set local role anon;
update public.questions
set can_publish = true
where id = '00000000-0000-0000-0007-000000000001';
reset role;

select is(
  (select can_publish from public.questions where id = '00000000-0000-0000-0007-000000000001'),
  true,
  'an update of only can_publish marks the edited question validated'
);

select is(
  (select test_cases from public.questions where id = '00000000-0000-0000-0007-000000000001'),
  '[{"test_input": "2 2", "expected_output": "4"}]'::jsonb,
  'the edited test cases were kept'
);

select ok(
  coalesce((
    select not has_function_privilege('anon', p.oid, 'execute')
      and not has_function_privilege('authenticated', p.oid, 'execute')
    from pg_catalog.pg_proc p
    where p.oid = to_regprocedure('public.reset_can_publish_on_question_edit()')
  ), false),
  'the trigger function exists and the browser roles cannot call it directly'
);

select * from finish();

rollback;
