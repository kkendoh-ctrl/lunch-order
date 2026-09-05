-- ============================================================================
-- 全国モルッカー図鑑 / フェーズ1 初期スキーマ
--   regions / teams / players / reports / deletion_requests
--   + RLS、地方の自動導出、通報3件での自動非表示、本人確認(claim)、削除依頼
-- ============================================================================

create extension if not exists "pgcrypto";

-- ---------------------------------------------------------------------------
-- regions（地方）
-- ---------------------------------------------------------------------------
create table if not exists public.regions (
  id            smallint primary key,
  slug          text not null unique,
  name          text not null unique,
  display_order smallint not null
);

insert into public.regions (id, slug, name, display_order) values
  (1, 'hokkaido', '北海道',   1),
  (2, 'tohoku',   '東北',     2),
  (3, 'kanto',    '関東',     3),
  (4, 'chubu',    '中部',     4),
  (5, 'kinki',    '近畿',     5),
  (6, 'chugoku',  '中国',     6),
  (7, 'shikoku',  '四国',     7),
  (8, 'kyushu',   '九州沖縄', 8)
on conflict (id) do update
  set slug = excluded.slug,
      name = excluded.name,
      display_order = excluded.display_order;

-- 都道府県 → 地方。フロントの定数ファイル(src/constants/prefectures.ts)と同じ対応表。
create or replace function public.region_slug_for_prefecture(p_prefecture text)
returns text
language sql
immutable
as $$
  select case p_prefecture
    when '北海道'   then 'hokkaido'
    when '青森県'   then 'tohoku'
    when '岩手県'   then 'tohoku'
    when '宮城県'   then 'tohoku'
    when '秋田県'   then 'tohoku'
    when '山形県'   then 'tohoku'
    when '福島県'   then 'tohoku'
    when '茨城県'   then 'kanto'
    when '栃木県'   then 'kanto'
    when '群馬県'   then 'kanto'
    when '埼玉県'   then 'kanto'
    when '千葉県'   then 'kanto'
    when '東京都'   then 'kanto'
    when '神奈川県' then 'kanto'
    when '新潟県'   then 'chubu'
    when '富山県'   then 'chubu'
    when '石川県'   then 'chubu'
    when '福井県'   then 'chubu'
    when '山梨県'   then 'chubu'
    when '長野県'   then 'chubu'
    when '岐阜県'   then 'chubu'
    when '静岡県'   then 'chubu'
    when '愛知県'   then 'chubu'
    when '三重県'   then 'kinki'
    when '滋賀県'   then 'kinki'
    when '京都府'   then 'kinki'
    when '大阪府'   then 'kinki'
    when '兵庫県'   then 'kinki'
    when '奈良県'   then 'kinki'
    when '和歌山県' then 'kinki'
    when '鳥取県'   then 'chugoku'
    when '島根県'   then 'chugoku'
    when '岡山県'   then 'chugoku'
    when '広島県'   then 'chugoku'
    when '山口県'   then 'chugoku'
    when '徳島県'   then 'shikoku'
    when '香川県'   then 'shikoku'
    when '愛媛県'   then 'shikoku'
    when '高知県'   then 'shikoku'
    when '福岡県'   then 'kyushu'
    when '佐賀県'   then 'kyushu'
    when '長崎県'   then 'kyushu'
    when '熊本県'   then 'kyushu'
    when '大分県'   then 'kyushu'
    when '宮崎県'   then 'kyushu'
    when '鹿児島県' then 'kyushu'
    when '沖縄県'   then 'kyushu'
    else null
  end;
$$;

-- ---------------------------------------------------------------------------
-- teams
-- ---------------------------------------------------------------------------
create table if not exists public.teams (
  id          uuid primary key default gen_random_uuid(),
  name        text not null check (char_length(name) between 1 and 40),
  prefecture  text not null check (public.region_slug_for_prefecture(prefecture) is not null),
  logo_url    text,
  created_by  uuid references auth.users(id) on delete set null,
  created_at  timestamptz not null default now()
);
create index if not exists teams_prefecture_idx on public.teams (prefecture);

-- ---------------------------------------------------------------------------
-- players（選手カード）
--   仕様の「auth.users と1:1」は user_id 側で表現する。
--   Xから取り込んだ未確認カードには auth ユーザーが存在しないため、
--   主キーを auth.users に直結させず nullable な user_id で紐づける。
-- ---------------------------------------------------------------------------
create sequence if not exists public.players_dex_number_seq as integer start 1;

create table if not exists public.players (
  id            uuid primary key default gen_random_uuid(),
  user_id       uuid unique references auth.users(id) on delete cascade,
  dex_number    integer not null unique default nextval('public.players_dex_number_seq'),

  nickname      text not null check (char_length(nickname) between 1 and 20),
  real_name     text check (char_length(real_name) <= 40),
  team_id       uuid references public.teams(id) on delete set null,
  prefecture    text not null check (public.region_slug_for_prefecture(prefecture) is not null),
  region_id     smallint not null references public.regions(id),
  home_ground   text check (char_length(home_ground) <= 60),
  avatar_url    text,

  win_phrase    text check (char_length(win_phrase) <= 40),
  miss_cry      text check (char_length(miss_cry) <= 20),
  style_tags    text[] not null default '{}'::text[]
                  check (array_length(style_tags, 1) is null or array_length(style_tags, 1) <= 2)
                  check (style_tags <@ array[
                    '遠投型','精密型','一発狙い','堅実積み上げ',
                    'メンタル強者','ムードメーカー','左投げ','高速テンポ'
                  ]::text[]),

  is_legend     boolean not null default false,
  visibility    text not null default 'public' check (visibility in ('public','members','hidden')),
  claim_status  text not null default 'unclaimed' check (claim_status in ('unclaimed','claimed')),
  is_auto_hidden boolean not null default false,

  x_user_id     text,
  x_handle      text,
  source_url    text,

  created_at    timestamptz not null default now(),
  updated_at    timestamptz not null default now(),

  -- 本人確認済みのカードには必ず持ち主がいる。逆に未確認カードに持ち主はいない。
  constraint players_claim_owner_ck check (
    (claim_status = 'claimed' and user_id is not null)
    or (claim_status = 'unclaimed' and user_id is null)
  )
);

create unique index if not exists players_x_user_id_key on public.players (x_user_id) where x_user_id is not null;
create index if not exists players_region_idx on public.players (region_id);
create index if not exists players_visible_idx on public.players (region_id, is_legend desc, dex_number)
  where visibility = 'public' and is_auto_hidden = false;

-- 更新時刻
create or replace function public.touch_updated_at()
returns trigger
language plpgsql
as $$
begin
  new.updated_at := now();
  return new;
end;
$$;

drop trigger if exists players_touch_updated_at on public.players;
create trigger players_touch_updated_at
  before update on public.players
  for each row execute function public.touch_updated_at();

-- 都道府県から地方を自動導出（クライアントに決めさせない）
create or replace function public.set_player_region()
returns trigger
language plpgsql
as $$
begin
  select r.id into new.region_id
  from public.regions r
  where r.slug = public.region_slug_for_prefecture(new.prefecture);

  if new.region_id is null then
    raise exception '都道府県から地方を導出できません: %', new.prefecture;
  end if;
  return new;
end;
$$;

drop trigger if exists players_set_region on public.players;
create trigger players_set_region
  before insert or update of prefecture on public.players
  for each row execute function public.set_player_region();

-- 一般利用者に触らせない列を凍結する（伝説・図鑑番号・本人確認状態・取り込み元）
create or replace function public.guard_player_columns()
returns trigger
language plpgsql
as $$
begin
  -- service_role と、下の SECURITY DEFINER 関数からの更新だけは通す
  if auth.role() = 'service_role'
     or coalesce(current_setting('app.bypass_player_guard', true), 'off') = 'on' then
    return new;
  end if;
  new.dex_number     := old.dex_number;
  new.is_legend      := old.is_legend;
  new.claim_status   := old.claim_status;
  new.user_id        := old.user_id;
  new.is_auto_hidden := old.is_auto_hidden;
  new.x_user_id      := old.x_user_id;
  new.x_handle       := old.x_handle;
  new.source_url     := old.source_url;
  return new;
end;
$$;

drop trigger if exists players_guard_columns on public.players;
create trigger players_guard_columns
  before update on public.players
  for each row execute function public.guard_player_columns();

-- ---------------------------------------------------------------------------
-- reports（通報）: 同一対象3件で自動非表示。運営が見なくても回る。
-- ---------------------------------------------------------------------------
create table if not exists public.reports (
  id          uuid primary key default gen_random_uuid(),
  target_type text not null check (target_type in ('player','team')),
  target_id   uuid not null,
  reporter_id uuid references auth.users(id) on delete set null,
  reason      text not null check (char_length(reason) between 1 and 400),
  created_at  timestamptz not null default now()
);
-- 同じ人が同じ対象を何度も通報しても1件として数える
create unique index if not exists reports_unique_reporter
  on public.reports (target_type, target_id, reporter_id)
  where reporter_id is not null;
create index if not exists reports_target_idx on public.reports (target_type, target_id);

create or replace function public.apply_report_threshold()
returns trigger
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_count integer;
begin
  select count(*) into v_count
  from public.reports
  where target_type = new.target_type and target_id = new.target_id;

  if v_count >= 3 and new.target_type = 'player' then
    perform set_config('app.bypass_player_guard', 'on', true);
    update public.players set is_auto_hidden = true where id = new.target_id;
    perform set_config('app.bypass_player_guard', 'off', true);
  end if;
  return null;
end;
$$;

drop trigger if exists reports_apply_threshold on public.reports;
create trigger reports_apply_threshold
  after insert on public.reports
  for each row execute function public.apply_report_threshold();

-- ---------------------------------------------------------------------------
-- deletion_requests（削除依頼）: 受け付けた時点で未確認カードは即非公開になる。
-- ---------------------------------------------------------------------------
create table if not exists public.deletion_requests (
  id         uuid primary key default gen_random_uuid(),
  player_id  uuid not null references public.players(id) on delete cascade,
  requested_by uuid references auth.users(id) on delete set null,
  contact    text check (char_length(contact) <= 120),
  reason     text check (char_length(reason) <= 400),
  created_at timestamptz not null default now()
);
create index if not exists deletion_requests_player_idx on public.deletion_requests (player_id);

-- ---------------------------------------------------------------------------
-- RPC
-- ---------------------------------------------------------------------------

-- ログイン中のXアカウントIDを JWT から取り出す
create or replace function public.current_x_user_id()
returns text
language sql
stable
as $$
  select coalesce(
    nullif(auth.jwt() -> 'user_metadata' ->> 'provider_id', ''),
    nullif(auth.jwt() -> 'user_metadata' ->> 'sub', '')
  );
$$;

-- 「あなたのカードが見つかりました」: 未確認カードを探す
create or replace function public.find_my_unclaimed_card()
returns setof public.players
language sql
stable
security definer
set search_path = public, pg_temp
as $$
  select p.*
  from public.players p
  where p.claim_status = 'unclaimed'
    and p.x_user_id is not null
    and p.x_user_id = public.current_x_user_id()
    and auth.uid() is not null
  limit 1;
$$;

-- 本人確認: XのユーザーIDが一致したときだけ、そのカードの持ち主になる
create or replace function public.claim_card(p_player_id uuid)
returns public.players
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_x_id   text := public.current_x_user_id();
  v_player public.players;
begin
  if auth.uid() is null then
    raise exception 'ログインが必要です';
  end if;
  if v_x_id is null then
    raise exception 'Xのアカウント情報が取得できません';
  end if;
  if exists (select 1 from public.players where user_id = auth.uid()) then
    raise exception 'すでにカードをお持ちです';
  end if;

  perform set_config('app.bypass_player_guard', 'on', true);
  update public.players
     set user_id      = auth.uid(),
         claim_status = 'claimed',
         updated_at   = now()
   where id = p_player_id
     and claim_status = 'unclaimed'
     and x_user_id = v_x_id
  returning * into v_player;
  perform set_config('app.bypass_player_guard', 'off', true);

  if v_player.id is null then
    raise exception 'このカードは本人確認できません';
  end if;
  return v_player;
end;
$$;

-- 削除依頼: 運営の確認を挟まず、その場で非公開にする
create or replace function public.request_card_deletion(
  p_player_id uuid,
  p_reason text default null,
  p_contact text default null
)
returns void
language plpgsql
security definer
set search_path = public, pg_temp
as $$
declare
  v_player public.players;
begin
  select * into v_player from public.players where id = p_player_id;
  if v_player.id is null then
    raise exception 'カードが見つかりません';
  end if;

  insert into public.deletion_requests (player_id, requested_by, contact, reason)
  values (p_player_id, auth.uid(), p_contact, p_reason);

  -- 未確認カードは誰の依頼でも即非公開。本人確認済みカードは持ち主本人のときだけ。
  if v_player.claim_status = 'unclaimed'
     or (v_player.user_id is not null and v_player.user_id = auth.uid()) then
    update public.players
       set visibility = 'hidden', updated_at = now()
     where id = p_player_id;
  end if;
end;
$$;

-- ---------------------------------------------------------------------------
-- 図鑑トップ用の集計ビュー（RLSは呼び出し元の権限で効く）
-- ---------------------------------------------------------------------------
drop view if exists public.region_dex_stats;
create view public.region_dex_stats
with (security_invoker = on) as
select
  r.id            as region_id,
  r.slug          as region_slug,
  r.name          as region_name,
  r.display_order as display_order,
  count(p.id)                                  as player_count,
  count(p.id) filter (where p.is_legend)       as legend_count
from public.regions r
left join public.players p on p.region_id = r.id
group by r.id, r.slug, r.name, r.display_order;

-- ---------------------------------------------------------------------------
-- RLS
-- ---------------------------------------------------------------------------
alter table public.regions           enable row level security;
alter table public.teams             enable row level security;
alter table public.players           enable row level security;
alter table public.reports           enable row level security;
alter table public.deletion_requests enable row level security;

-- regions: 誰でも読める
drop policy if exists regions_select on public.regions;
create policy regions_select on public.regions
  for select using (true);

-- teams: 誰でも読める / ログイン中の人が作れる / 作った人だけ直せる
drop policy if exists teams_select on public.teams;
create policy teams_select on public.teams
  for select using (true);

drop policy if exists teams_insert on public.teams;
create policy teams_insert on public.teams
  for insert to authenticated
  with check (created_by = auth.uid());

drop policy if exists teams_update on public.teams;
create policy teams_update on public.teams
  for update to authenticated
  using (created_by = auth.uid())
  with check (created_by = auth.uid());

drop policy if exists teams_delete on public.teams;
create policy teams_delete on public.teams
  for delete to authenticated
  using (created_by = auth.uid());

-- players: 公開範囲どおりに見せる。自分のカードはいつでも見える。
drop policy if exists players_select_public on public.players;
create policy players_select_public on public.players
  for select using (
    (visibility = 'public' and is_auto_hidden = false)
    or (visibility = 'members' and is_auto_hidden = false and auth.uid() is not null)
    or (user_id is not null and user_id = auth.uid())
  );

drop policy if exists players_insert_own on public.players;
create policy players_insert_own on public.players
  for insert to authenticated
  with check (user_id = auth.uid() and claim_status = 'claimed');

drop policy if exists players_update_own on public.players;
create policy players_update_own on public.players
  for update to authenticated
  using (user_id = auth.uid())
  with check (user_id = auth.uid());

drop policy if exists players_delete_own on public.players;
create policy players_delete_own on public.players
  for delete to authenticated
  using (user_id = auth.uid());

-- reports: 誰でも出せる。読めるのは service_role だけ（＝運営が見なくても回る）。
drop policy if exists reports_insert on public.reports;
create policy reports_insert on public.reports
  for insert
  with check (reporter_id is null or reporter_id = auth.uid());

-- deletion_requests: 通常の経路は RPC のみ。直接の読み書きは許可しない。

-- ---------------------------------------------------------------------------
-- 権限
-- ---------------------------------------------------------------------------
grant usage on schema public to anon, authenticated;

grant select on public.regions to anon, authenticated;
grant select on public.teams   to anon, authenticated;
grant select on public.players to anon, authenticated;
grant insert, update, delete on public.teams   to authenticated;
grant insert, update, delete on public.players to authenticated;
grant insert on public.reports to anon, authenticated;
grant usage on sequence public.players_dex_number_seq to authenticated;

grant select on public.region_dex_stats to anon, authenticated;
grant execute on function public.region_slug_for_prefecture(text) to anon, authenticated;
grant execute on function public.current_x_user_id() to authenticated;
grant execute on function public.find_my_unclaimed_card() to authenticated;
grant execute on function public.claim_card(uuid) to authenticated;
grant execute on function public.request_card_deletion(uuid, text, text) to anon, authenticated;

-- ---------------------------------------------------------------------------
-- Storage（カード写真）
-- ---------------------------------------------------------------------------
insert into storage.buckets (id, name, public)
values ('avatars', 'avatars', true)
on conflict (id) do nothing;

drop policy if exists "avatars are readable by anyone" on storage.objects;
create policy "avatars are readable by anyone" on storage.objects
  for select using (bucket_id = 'avatars');

drop policy if exists "avatars are writable by owner" on storage.objects;
create policy "avatars are writable by owner" on storage.objects
  for insert to authenticated
  with check (
    bucket_id = 'avatars'
    and (storage.foldername(name))[1] = auth.uid()::text
  );

drop policy if exists "avatars are replaceable by owner" on storage.objects;
create policy "avatars are replaceable by owner" on storage.objects
  for update to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text)
  with check (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);

drop policy if exists "avatars are removable by owner" on storage.objects;
create policy "avatars are removable by owner" on storage.objects
  for delete to authenticated
  using (bucket_id = 'avatars' and (storage.foldername(name))[1] = auth.uid()::text);
