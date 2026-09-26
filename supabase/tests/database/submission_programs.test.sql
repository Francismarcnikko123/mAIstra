begin;

select plan(18);

-- Two questions and one photographed page with two programs on it.
insert into public.questions (id, question_name, question_text, model_answer, question_type, test_cases)
values
  ('00000000-0000-0000-0000-00000000c001', 'Sum', 'Add.', 'int main(void){return 0;}', 'program',
   '[{"test_input": "1 2", "expected_output": "3"}]'::jsonb),
  ('00000000-0000-0000-0000-00000000c002', 'Max', 'Max.', 'int main(void){return 0;}', 'program',
   '[{"test_input": "1 2", "expected_output": "2"}]'::jsonb);

insert into public.submissions (id, image_url, status, question_id, extracted_text)
values (
  '00000000-0000-0000-0000-00000000d001',
  'https://example.test/storage/v1/object/public/handwritten-submissions/page.jpg',
  'extracted',
  '00000000-0000-0000-0000-00000000c001',
  'raw OCR of the whole page'
);

select ok(
  (select relrowsecurity from pg_class where oid = 'public.submission_programs'::regclass),
  'submission_programs enforces row level security'
);

select ok(
  not exists (
    select 1 from information_schema.columns
    where table_schema = 'public' and table_name = 'submissions' and column_name = 'answers'
  ),
  'the answers column is replaced by submission_programs'
);

create temporary table results (step text, value bigint);
grant insert, select on table results to anon;

set local role anon;

-- The review saves both tabs in one call.
insert into results
select 'first save', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000d001', 0,
  '[{"verified_text": "program one", "question_id": "00000000-0000-0000-0000-00000000c001"},
    {"verified_text": "program two", "question_id": "00000000-0000-0000-0000-00000000c002"}]'::jsonb
);

-- A second teacher still holding revision 99 saves nothing.
insert into results
select 'stale save', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000d001', 99,
  '[{"verified_text": "overwritten", "question_id": "00000000-0000-0000-0000-00000000c001"}]'::jsonb
);

reset role;

select isnt((select value from results where step = 'first save'), null::bigint,
  'anon can save every program of a page in one call');

select is((select value from results where step = 'stale save'), null::bigint,
  'a save against a stale page revision is refused');

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001'),
  2::bigint,
  'each program is its own row, and the stale save wrote nothing'
);

select ok(
  (select verified_text = 'program one'
     and question_id = '00000000-0000-0000-0000-00000000c001'
     and status = 'verified'
     and extracted_text = 'raw OCR of the whole page'
   from public.submissions where id = '00000000-0000-0000-0000-00000000d001'),
  'Program 1 is mirrored to the page row and the raw OCR is kept'
);

-- Grade Program 1 only.
set local role anon;
insert into results
select 'grade one', public.save_program_grade(
  (select id from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 1),
  0, '00000000-0000-0000-0000-00000000c001', 'program one',
  '[{"passed": true}]'::jsonb
);
reset role;

select ok(
  (select status = 'verified' from public.submissions
   where id = '00000000-0000-0000-0000-00000000d001'),
  'a page with an ungraded program is not graded yet'
);

-- A grade for code that isn't the stored code is refused.
set local role anon;
insert into results
select 'wrong code', public.save_program_grade(
  (select id from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 2),
  0, '00000000-0000-0000-0000-00000000c002', 'not the stored code',
  '[{"passed": true}]'::jsonb
);
insert into results
select 'grade two', public.save_program_grade(
  (select id from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 2),
  0, '00000000-0000-0000-0000-00000000c002', 'program two',
  '[{"passed": true}, {"passed": false}]'::jsonb
);
reset role;

select is((select value from results where step = 'wrong code'), null::bigint,
  'a program grade for code that is not stored is refused');

select ok(
  (select status = 'graded' from public.submissions
   where id = '00000000-0000-0000-0000-00000000d001'),
  'the page is graded once every program is graded'
);

select ok(
  (select passed_test_cases = 1 and total_test_cases = 2 and score_percent = 50.00
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 2),
  'each program keeps its own score'
);

-- Re-save with Program 2 edited: only Program 2 loses its grade.
set local role anon;
insert into results
select 'edit two', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000d001',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0000-00000000d001'),
  '[{"verified_text": "program one", "question_id": "00000000-0000-0000-0000-00000000c001"},
    {"verified_text": "program two, fixed", "question_id": "00000000-0000-0000-0000-00000000c002"}]'::jsonb
);
reset role;

select ok(
  (select bool_and(case position
      when 1 then graded_at is not null
      when 2 then graded_at is null and grading_revision = 2
    end)
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001'),
  'editing one program clears only that program''s grade'
);

select ok(
  (select status = 'verified' from public.submissions
   where id = '00000000-0000-0000-0000-00000000d001'),
  'a page with a cleared program grade is no longer graded'
);

-- Swap the two questions between the tabs in one save (deferred unique).
set local role anon;
insert into results
select 'swap', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000d001',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0000-00000000d001'),
  '[{"verified_text": "program one", "question_id": "00000000-0000-0000-0000-00000000c002"},
    {"verified_text": "program two, fixed", "question_id": "00000000-0000-0000-0000-00000000c001"}]'::jsonb
);
reset role;

select ok(
  (select question_id = '00000000-0000-0000-0000-00000000c002'
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 1),
  'two tabs can swap questions in one save'
);

-- Grade Program 2 again, then change its question's test cases.
set local role anon;
insert into results
select 'regrade', public.save_program_grade(
  (select id from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 2),
  (select grading_revision from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 2),
  '00000000-0000-0000-0000-00000000c001', 'program two, fixed',
  '[{"passed": true}]'::jsonb
);
update public.questions
set test_cases = '[{"test_input": "2 2", "expected_output": "4"}]'::jsonb
where id = '00000000-0000-0000-0000-00000000c001';
reset role;

select ok(
  (select graded_at is null from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 2),
  'editing a question''s test cases clears the grade of a Program 2+ linked to it'
);

-- Removing the second tab deletes its row.
set local role anon;
insert into results
select 'remove tab', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000d001',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0000-00000000d001'),
  '[{"verified_text": "program one", "question_id": "00000000-0000-0000-0000-00000000c002"}]'::jsonb
);
reset role;

select is(
  (select count(*) from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001'),
  1::bigint,
  'a removed tab is deleted'
);

-- A paper with no tabs saves Program 1 alone, without its question id: the
-- page's question is used and Program 2 (saved earlier) is left alone.
set local role anon;
insert into results
select 'program 2 back', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000d001',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0000-00000000d001'),
  '[{"verified_text": "program one", "question_id": "00000000-0000-0000-0000-00000000c002"},
    {"verified_text": "program two again", "question_id": "00000000-0000-0000-0000-00000000c001"}]'::jsonb
);
insert into results
select 'program 1 only', public.save_submission_programs(
  '00000000-0000-0000-0000-00000000d001',
  (select grading_revision from public.submissions where id = '00000000-0000-0000-0000-00000000d001'),
  '[{"verified_text": "program one, edited"}]'::jsonb,
  null,
  false
);
reset role;

select ok(
  (select question_id = '00000000-0000-0000-0000-00000000c002'
     and verified_text = 'program one, edited'
   from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 1),
  'Program 1 saved without a question id keeps the page''s question'
);

select is(
  (select verified_text from public.submission_programs
   where submission_id = '00000000-0000-0000-0000-00000000d001' and position = 2),
  'program two again',
  'saving only Program 1 leaves the other programs as they are'
);

select throws_ok(
  $$ delete from public.questions where id = '00000000-0000-0000-0000-00000000c002' $$,
  '23503',
  null,
  'a question with verified programs cannot be deleted'
);

select * from finish();

rollback;
