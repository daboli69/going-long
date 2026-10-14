-- Prepared recovery only. Do not apply before verified archive upload/cutover approval.
begin;
do $$ begin
 if exists(select 1 from storage.buckets where id='going-journal-private' and public) then
  raise exception 'Archive bucket must never be public';
 end if;
end $$;
insert into storage.buckets(id,name,public,file_size_limit,allowed_mime_types)
values('going-journal-private','going-journal-private',false,9437184,array['application/gzip','application/x-gzip','application/json'])
on conflict(id) do nothing;
-- Restrictive guard defeats any pre-existing broad permissive Storage policy.
create policy journal_archive_owner_guard on storage.objects as restrictive
for select to anon, authenticated using(
 bucket_id <> 'going-journal-private' or (storage.foldername(name))[1]=auth.uid()::text
);
create policy journal_archive_owner_read on storage.objects
for select to authenticated using(
 bucket_id='going-journal-private' and (storage.foldername(name))[1]=auth.uid()::text
);
create policy journal_archive_no_client_insert on storage.objects as restrictive
for insert to anon, authenticated with check(bucket_id <> 'going-journal-private');
create policy journal_archive_no_client_update on storage.objects as restrictive
for update to anon, authenticated using(bucket_id <> 'going-journal-private') with check(bucket_id <> 'going-journal-private');
create policy journal_archive_no_client_delete on storage.objects as restrictive
for delete to anon, authenticated using(bucket_id <> 'going-journal-private');
commit;
