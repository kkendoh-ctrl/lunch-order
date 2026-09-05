import type { RegionSlug } from '../constants/prefectures'
import type { StyleTag } from '../constants/styleTags'

export type Visibility = 'public' | 'members' | 'hidden'
export type ClaimStatus = 'unclaimed' | 'claimed'

export type Team = {
  id: string
  name: string
  prefecture: string
  logo_url: string | null
  created_by: string | null
  created_at: string
}

export type Player = {
  id: string
  user_id: string | null
  dex_number: number
  nickname: string
  real_name: string | null
  team_id: string | null
  prefecture: string
  region_id: number
  home_ground: string | null
  avatar_url: string | null
  win_phrase: string | null
  miss_cry: string | null
  style_tags: StyleTag[]
  is_legend: boolean
  visibility: Visibility
  claim_status: ClaimStatus
  is_auto_hidden: boolean
  x_user_id: string | null
  x_handle: string | null
  source_url: string | null
  created_at: string
  updated_at: string
}

/** 一覧・詳細で使う、チーム名まで含んだカード */
export type PlayerWithTeam = Player & {
  teams: Pick<Team, 'id' | 'name'> | null
}

export type RegionStat = {
  region_id: number
  region_slug: RegionSlug
  region_name: string
  display_order: number
  player_count: number
  legend_count: number
}

/** 編集画面から書き戻せる項目だけ */
export type PlayerDraft = {
  nickname: string
  real_name: string | null
  team_id: string | null
  prefecture: string
  home_ground: string | null
  avatar_url: string | null
  win_phrase: string | null
  miss_cry: string | null
  style_tags: StyleTag[]
  visibility: Visibility
}
