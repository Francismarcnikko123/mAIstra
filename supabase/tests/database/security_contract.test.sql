begin;

select plan(13);

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
  'anon cannot update questions'
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

select * from finish();

rollback;
