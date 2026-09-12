create index if not exists market_journal_tracking_group on public.market_journal(owner_id,(payload->>'tracking_group'),observed_at desc,id) where kind='prediction';
