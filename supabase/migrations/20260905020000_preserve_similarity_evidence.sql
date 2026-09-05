alter table public.similarity_scans
  rename column compared_submission_count to compared_pair_count;
alter table public.similarity_scans
  rename column skipped_submission_count to skipped_pair_count;
alter table public.similarity_scans
  add column metadata jsonb not null default '{}'::jsonb;

alter table public.similarity_matches
  drop constraint similarity_matches_type_check,
  drop constraint similarity_matches_source_ranges_check;

update public.similarity_matches
set match_type = case match_type when 'exact' then 'exact_duplicate' else 'similar_code' end,
    source_ranges = jsonb_build_object(
      'left', coalesce((select jsonb_agg(item->'left') from jsonb_array_elements(source_ranges) item), '[]'::jsonb),
      'right', coalesce((select jsonb_agg(item->'right') from jsonb_array_elements(source_ranges) item), '[]'::jsonb)
    );

alter table public.similarity_matches
  alter column source_ranges set default '{"left":[],"right":[]}'::jsonb,
  add constraint similarity_matches_type_check
    check (match_type in ('exact_duplicate', 'normalized_duplicate', 'similar_code')),
  add constraint similarity_matches_source_ranges_check
    check (jsonb_typeof(source_ranges) = 'object'
      and source_ranges ? 'left' and source_ranges ? 'right'
      and jsonb_typeof(source_ranges->'left') = 'array'
      and jsonb_typeof(source_ranges->'right') = 'array');

comment on column public.similarity_scans.metadata is
  'Eligible submission count and analysis limitations retained when a scan is reopened.';
