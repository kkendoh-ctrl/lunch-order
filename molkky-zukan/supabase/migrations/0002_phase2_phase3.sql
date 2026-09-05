-- ============================================================================
-- 全国モルッカー図鑑 / フェーズ2・3のテーブル
--   画面は機能フラグ(VITE_FEATURE_BADGES / VITE_FEATURE_MATCH)で隠すが、
--   スキーマとRLSは先に置いておく。
-- ============================================================================

-- ログイン中の人のカードID
create or replace function public.my_player_id()
returns uuid
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select id from public.players where user_id = auth.uid() limit 1;
$$;
grant execute on function public.my_player_id() to authenticated;

-- ---------------------------------------------------------------------------
-- gyms（門番）【フェーズ2】
-- ---------------------------------------------------------------------------
create table if not exists public.gyms (
  id               uuid primary key default gen_random_uuid(),
  region_id        smallint not null references public.regions(id),
  leader_player_id uuid not null references public.players(id) on delete cascade,
  name             text not null check (char_length(name) between 1 and 40),
  description      text check (char_length(description) <= 300),
  active           boolean not null default true,
  created_at       timestamptz not null default now()
);
create index if not exists gyms_region_idx on public.gyms (region_id) where active;

-- ---------------------------------------------------------------------------
-- badges（バッジ）【フェーズ2】
-- ---------------------------------------------------------------------------
create table if not exists public.badges (
  id         uuid primary key default gen_random_uuid(),
  gym_id     uuid not null references public.gyms(id) on delete cascade,
  player_id  uuid not null references public.players(id) on delete cascade,
  awarded_at timestamptz not null default now(),
  awarded_by uuid not null references public.players(id) on delete cascade,
  unique (gym_id, player_id)
);
create index if not exists badges_player_idx on public.badges (player_id);

-- ---------------------------------------------------------------------------
-- match_rooms（今日やりたい）【フェーズ3】
-- ---------------------------------------------------------------------------
create table if not exists public.match_rooms (
  id             uuid primary key default gen_random_uuid(),
  host_player_id uuid not null references public.players(id) on delete cascade,
  prefecture     text not null check (public.region_slug_for_prefecture(prefecture) is not null),
  place_text     text not null check (char_length(place_text) between 1 and 80),
  starts_at      timestamptz not null,
  status         text not null default 'open' check (status in ('open','closed')),
  expires_at     timestamptz not null default now() + interval '12 hours',
  created_at     timestamptz not null default now()
);
create index if not exists match_rooms_open_idx on public.match_rooms (prefecture, starts_at)
  where status = 'open';

-- 12時間で自動クローズ（pg_cron もしくは Edge Function から定期実行する）
create or replace function public.close_expired_match_rooms()
returns integer
language sql
security definer
set search_path = public, pg_temp
as $$
  with closed as (
    update public.match_rooms
       set status = 'closed'
     where status = 'open' and expires_at <= now()
    returning 1
  )
  select count(*)::integer from closed;
$$;

-- ---------------------------------------------------------------------------
-- match_messages【フェーズ3】
-- ---------------------------------------------------------------------------
create table if not exists public.match_messages (
  id         uuid primary key default gen_random_uuid(),
  room_id    uuid not null references public.match_rooms(id) on delete cascade,
  player_id  uuid not null references public.players(id) on delete cascade,
  body       text not null check (char_length(body) between 1 and 300),
  created_at timestamptz not null default now()
);
create index if not exists match_messages_room_idx on public.match_messages (room_id, created_at);

-- Realtime購読
do $$
begin
  if exists (select 1 from pg_publication where pubname = 'supabase_realtime') then
    execute 'alter publication supabase_realtime add table public.match_messages';
  end if;
exception
  when duplicate_object then null;
end
$$;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
alter table public.gyms           enable row level security;
alter table public.badges         enable row level security;
alter table public.match_rooms    enable row level security;
alter table public.match_messages enable row level security;

-- gyms: 誰でも読める。任命は運営(service_role)のみ。
drop policy if exists gyms_select on public.gyms;
create policy gyms_select on public.gyms
  for select using (active);

-- badges: 誰でも読める。授与できるのはその門番本人だけ。
drop policy if exists badges_select on public.badges;
create policy badges_select on public.badges
  for select using (true);

drop policy if exists badges_insert_by_leader on public.badges;
create policy badges_insert_by_leader on public.badges
  for insert to authenticated
  with check (
    awarded_by = public.my_player_id()
    and exists (
      select 1 from public.gyms g
      where g.id = badges.gym_id
        and g.active
        and g.leader_player_id = public.my_player_id()
    )
  );

drop policy if exists badges_delete_by_leader on public.badges;
create policy badges_delete_by_leader on public.badges
  for delete to authenticated
  using (
    exists (
      select 1 from public.gyms g
      where g.id = badges.gym_id and g.leader_player_id = public.my_player_id()
    )
  );

-- match_rooms: 開いている部屋だけ見える。主催者だけが閉じられる。
drop policy if exists match_rooms_select on public.match_rooms;
create policy match_rooms_select on public.match_rooms
  for select to authenticated
  using (
    (status = 'open' and expires_at > now())
    or host_player_id = public.my_player_id()
  );

drop policy if exists match_rooms_insert on public.match_rooms;
create policy match_rooms_insert on public.match_rooms
  for insert to authenticated
  with check (host_player_id = public.my_player_id());

drop policy if exists match_rooms_update_host on public.match_rooms;
create policy match_rooms_update_host on public.match_rooms
  for update to authenticated
  using (host_player_id = public.my_player_id())
  with check (host_player_id = public.my_player_id());

-- match_messages: 閉じた部屋は読めない。
drop policy if exists match_messages_select on public.match_messages;
create policy match_messages_select on public.match_messages
  for select to authenticated
  using (
    exists (
      select 1 from public.match_rooms r
      where r.id = match_messages.room_id
        and r.status = 'open'
        and r.expires_at > now()
    )
  );

drop policy if exists match_messages_insert on public.match_messages;
create policy match_messages_insert on public.match_messages
  for insert to authenticated
  with check (
    player_id = public.my_player_id()
    and exists (
      select 1 from public.match_rooms r
      where r.id = match_messages.room_id
        and r.status = 'open'
        and r.expires_at > now()
    )
  );

-- ---------------------------------------------------------------------------
-- 権限
-- ---------------------------------------------------------------------------
grant select on public.gyms   to anon, authenticated;
grant select on public.badges to anon, authenticated;
grant insert, delete on public.badges to authenticated;
grant select, insert, update on public.match_rooms    to authenticated;
grant select, insert          on public.match_messages to authenticated;
grant execute on function public.close_expired_match_rooms() to service_role;
