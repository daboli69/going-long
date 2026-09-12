-- Index bounded owner-scoped decisions and exact prediction follow-ups.
create index if not exists market_journal_owner_kind_cursor
on public.market_journal(owner_id,kind,observed_at desc,id);
create index if not exists market_journal_owner_actionable_cursor
on public.market_journal(owner_id,(payload->>'actionable'),observed_at desc,id)
where kind='prediction';
create index if not exists market_journal_owner_prediction_cursor
on public.market_journal(owner_id,kind,(payload->>'prediction_id'),observed_at desc,id)
where kind in ('settlement','closing');
create index if not exists placed_bets_owner_time
on public.placed_bets(owner_id,placed_at desc);
