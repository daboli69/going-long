-- Append-only, owner-scoped journal. Writers use the server service-role secret.
-- No anonymous access and no client permission to rewrite a past prediction.
create table public.market_journal (
  id text primary key check (length(id)=64),
  owner_id uuid not null references auth.users(id),
  kind text not null check (kind in ('quote','prediction','settlement','closing','reference','run','notification','arbitrage','inactive_report')),
  observed_at timestamptz not null,
  received_at timestamptz not null default now(),
  payload jsonb not null check (jsonb_typeof(payload)='object'),
  check (kind <> 'prediction' or (payload ?& array['event','selection','market','side','odds','probability','raw_probability','actionable','proposed_stake','model_version','kickoff']))
);
create index market_journal_owner_time on public.market_journal(owner_id,kind,observed_at desc);
create index market_journal_event on public.market_journal ((payload->>'event'));
alter table public.market_journal enable row level security;
create policy owner_read on public.market_journal for select to authenticated using (owner_id=auth.uid());
revoke all on public.market_journal from anon,authenticated;
grant select on public.market_journal to authenticated;
grant select,insert on public.market_journal to service_role;

create function public.reject_journal_rewrite() returns trigger language plpgsql set search_path=public as $$
begin raise exception 'Journal records are immutable; append a documented correction'; end $$;
create trigger market_journal_immutable before update or delete on public.market_journal for each row execute function public.reject_journal_rewrite();

-- Real stakes are separate from hypothetical $100 validation stakes.
create table public.placed_bets (
 id uuid primary key default gen_random_uuid(),
 owner_id uuid not null default auth.uid() references auth.users(id),
 prediction_id text not null references public.market_journal(id),
 placed_at timestamptz not null,
 stake numeric not null check(stake>0),
 accepted_decimal numeric not null check(accepted_decimal>1),
 book text not null,
 created_at timestamptz not null default now()
);
alter table public.placed_bets enable row level security;
create policy owner_bets_read on public.placed_bets for select to authenticated using(owner_id=auth.uid());
create policy owner_bets_insert on public.placed_bets for insert to authenticated with check(owner_id=auth.uid() and exists(select 1 from public.market_journal j where j.id=prediction_id and j.owner_id=auth.uid() and j.kind='prediction' and placed_at<(j.payload->>'kickoff')::timestamptz));
revoke all on public.placed_bets from anon,authenticated;
grant select,insert on public.placed_bets to authenticated;
grant select,insert on public.placed_bets to service_role;
create trigger placed_bets_immutable before update or delete on public.placed_bets for each row execute function public.reject_journal_rewrite();
