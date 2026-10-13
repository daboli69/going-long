-- Requires approval before applying. Licensed input objects remain service-only.
do $$
begin
 if exists(select 1 from storage.buckets where id='going-fp-private' and public) then
  raise exception 'Existing bucket is public; private intake must not use it';
 end if;
end $$;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('going-fp-private','going-fp-private',false,8000000,array['application/json'])
on conflict(id) do nothing;
-- Restrictive policy also closes any pre-existing broad Storage policy.
do $$
begin
 if not exists(select 1 from pg_policies where schemaname='storage' and tablename='objects' and policyname='going_fp_service_only') then
  create policy going_fp_service_only on storage.objects as restrictive
  for all to anon, authenticated
  using(bucket_id <> 'going-fp-private') with check(bucket_id <> 'going-fp-private');
 end if;
end $$;
-- No permissive anon/authenticated read/write policy is added. Service role only.
