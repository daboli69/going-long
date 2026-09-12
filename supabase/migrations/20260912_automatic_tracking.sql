create index if not exists market_journal_tracking_group on public.market_journal(owner_id,(payload->>'tracking_group'),observed_at desc,id) where kind='prediction';
create index if not exists market_journal_tracked_only on public.market_journal(owner_id,(payload->>'tracking_group'),observed_at desc,id) where kind='prediction' and (payload->>'tracking_group') is not null;
analyze public.market_journal;
create index if not exists market_journal_eligible_only on public.market_journal(owner_id,observed_at desc,id) where kind='prediction' and (payload->>'actionable')='true';
