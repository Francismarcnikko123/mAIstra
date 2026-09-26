begin;

select plan(26);

select ok(
  (
    select relrowsecurity
    from pg_class
    where oid = 'public.questions'::regclass
  ),
  'questions enforce row level security'
);

select ok(
  (
    select relrowsecurity
    from pg_class
    where oid = 'public.submissions'::regclass
  ),
  'submissions enforce row level security'
);

select ok(
  not has_table_privilege('anon', 'public.questions', 'UPDATE'),
  'anon does not have broad question update privileges'
);

select ok(
  not has_table_privilege('anon', 'public.questions', 'DELETE'),
  'anon cannot delete questions'
);

select ok(
  has_column_privilege(
    'anon',
    'public.questions',
    'question_name',
    'INSERT'
  ),
  'anon can insert the required question fields'
);

select ok(
  not has_table_privilege('anon', 'public.questions', 'INSERT'),
  'anon does not have broad question insert privileges'
);

select ok(
  not has_table_privilege('anon', 'public.submissions', 'INSERT'),
  'anon does not have broad submission insert privileges'
);

select ok(
  has_column_privilege(
    'anon',
    'public.submissions',
    'image_url',
    'INSERT'
  ),
  'anon can insert a submission image URL'
);

select ok(
  not has_column_privilege(
    'anon',
    'public.submissions',
    'grading_results',
    'INSERT'
  ),
  'anon cannot forge grade fields while inserting a submission'
);

select ok(
  has_column_privilege(
    'anon',
    'public.submissions',
    'grading_results',
    'UPDATE'
  ),
  'anon can persist a completed grade in the no-login workflow'
);

select ok(
  not has_column_privilege(
    'anon',
    'public.submissions',
    'id',
    'UPDATE'
  ),
  'anon cannot change submission identifiers'
);

select ok(
  exists (
    select 1
    from pg_policies
    where schemaname = 'storage'
      and tablename = 'objects'
      and policyname = 'handwritten_submissions_public_insert'
      and cmd = 'INSERT'
  ),
  'handwritten uploads have a bucket-specific insert policy'
);

select ok(
  exists (
    select 1
    from storage.buckets
    where id = 'handwritten-submissions'
      and file_size_limit = 10485760
      and allowed_mime_types @> ARRAY['image/jpeg', 'image/png']::text[]
  ),
  'handwritten uploads are limited by size and MIME type'
);

select ok(
  exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'submissions'
  ),
  'submission changes are published to Supabase Realtime'
);

select ok(
  exists (
    select 1
    from pg_publication_tables
    where pubname = 'supabase_realtime'
      and schemaname = 'public'
      and tablename = 'questions'
  ),
  'question changes are published to Supabase Realtime'
);

select ok(
  has_column_privilege('anon', 'public.submissions', 'gate_result', 'INSERT'),
  'anon can record the phone gate verdict when uploading a page'
);

select ok(
  not has_column_privilege('anon', 'public.submissions', 'gate_result', 'UPDATE'),
  'anon cannot rewrite a page''s gate verdict after upload'
);

select ok(
  has_column_privilege('anon', 'public.questions', 'can_publish', 'INSERT'),
  'anon can mark a validated question when saving it'
);

create temporary table anon_gate_upload_results (
  attempt text,
  outcome text
);

grant insert, select on table anon_gate_upload_results to anon;

set local role anon;

do $$
begin
  insert into public.submissions (image_url, status, gate_result)
  values (
    'https://example.test/storage/v1/object/public/handwritten-submissions/fixable.jpg',
    'pending',
    'FIXABLE'
  );
  insert into anon_gate_upload_results values ('FIXABLE', 'inserted');
exception when insufficient_privilege then
  insert into anon_gate_upload_results values ('FIXABLE', 'rejected');
end $$;

do $$
begin
  insert into public.submissions (image_url, status, gate_result)
  values (
    'https://example.test/storage/v1/object/public/handwritten-submissions/retake.jpg',
    'pending',
    'RETAKE'
  );
  insert into anon_gate_upload_results values ('RETAKE', 'inserted');
exception when insufficient_privilege then
  insert into anon_gate_upload_results values ('RETAKE', 'rejected');
end $$;

reset role;

select is(
  (select outcome from anon_gate_upload_results where attempt = 'FIXABLE'),
  'inserted',
  'anon can upload a page the gate passed or auto-corrected'
);

select is(
  (select outcome from anon_gate_upload_results where attempt = 'RETAKE'),
  'rejected',
  'anon cannot upload a page the gate said to retake'
);

select ok(
  has_column_privilege('anon', 'public.questions', 'test_cases', 'UPDATE'),
  'anon can edit a saved question''s test cases'
);

select ok(
  not has_column_privilege('anon', 'public.questions', 'id', 'UPDATE'),
  'anon cannot change question identifiers'
);

insert into public.questions (
  id, question_name, question_text, model_answer, question_type
)
values (
  '00000000-0000-0000-0000-000000000b01',
  'Editable question',
  'Print a number.',
  'int main(void) { return 0; }',
  'program'
);

create temporary table anon_question_update_results (
  attempt text,
  outcome text
);

grant insert, select on table anon_question_update_results to anon;

set local role anon;

do $$
begin
  update public.questions
  set question_name = 'Renamed question'
  where id = '00000000-0000-0000-0000-000000000b01';
  insert into anon_question_update_results values ('rename', 'updated');
exception when insufficient_privilege then
  insert into anon_question_update_results values ('rename', 'rejected');
end $$;

do $$
begin
  update public.questions
  set question_type = 'essay'
  where id = '00000000-0000-0000-0000-000000000b01';
  insert into anon_question_update_results values ('bad type', 'updated');
exception when insufficient_privilege then
  insert into anon_question_update_results values ('bad type', 'rejected');
end $$;

reset role;

select is(
  (select outcome from anon_question_update_results where attempt = 'rename'),
  'updated',
  'anon can edit a saved question'
);

select is(
  (select outcome from anon_question_update_results where attempt = 'bad type'),
  'rejected',
  'question edits are validated like new questions'
);

select ok(
  has_column_privilege('anon', 'public.submissions', 'batch_id', 'INSERT'),
  'anon can group uploaded pages into one answer'
);

select ok(
  not has_column_privilege('anon', 'public.submissions', 'batch_id', 'UPDATE'),
  'anon cannot move a page to another answer after upload'
);

select * from finish();

rollback;
