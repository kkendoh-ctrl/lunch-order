import {
  useMutation,
  useQuery,
  useQueryClient,
  type UseQueryResult,
} from '@tanstack/react-query'
import { supabase, AVATAR_BUCKET } from '../lib/supabase'
import type {
  Player,
  PlayerDraft,
  PlayerWithTeam,
  RegionStat,
  Team,
} from '../types/database'

const PLAYER_COLUMNS = '*, teams:team_id (id, name)'

export const keys = {
  regionStats: ['region-stats'] as const,
  regionPlayers: (regionId: number) => ['region-players', regionId] as const,
  player: (id: string) => ['player', id] as const,
  myPlayer: (userId: string | null) => ['my-player', userId] as const,
  teams: ['teams'] as const,
  unclaimed: ['unclaimed-card'] as const,
}

/** 図鑑トップ: 地方ごとの登録人数 */
export function useRegionStats(): UseQueryResult<RegionStat[]> {
  return useQuery({
    queryKey: keys.regionStats,
    queryFn: async () => {
      const { data, error } = await supabase
        .from('region_dex_stats')
        .select('*')
        .order('display_order')
      if (error) throw error
      return data as RegionStat[]
    },
  })
}

/** 地方一覧: 伝説を先頭に、あとは図鑑番号順 */
export function useRegionPlayers(regionId: number | undefined) {
  return useQuery({
    queryKey: keys.regionPlayers(regionId ?? -1),
    enabled: regionId != null,
    queryFn: async () => {
      const { data, error } = await supabase
        .from('players')
        .select(PLAYER_COLUMNS)
        .eq('region_id', regionId!)
        .order('is_legend', { ascending: false })
        .order('dex_number', { ascending: true })
      if (error) throw error
      return data as unknown as PlayerWithTeam[]
    },
  })
}

export function usePlayer(id: string | undefined) {
  return useQuery({
    queryKey: keys.player(id ?? ''),
    enabled: !!id,
    queryFn: async () => {
      const { data, error } = await supabase
        .from('players')
        .select(PLAYER_COLUMNS)
        .eq('id', id!)
        .maybeSingle()
      if (error) throw error
      return data as unknown as PlayerWithTeam | null
    },
  })
}

/** 自分のカード。無ければ null。 */
export function useMyPlayer(userId: string | null) {
  return useQuery({
    queryKey: keys.myPlayer(userId),
    enabled: !!userId,
    queryFn: async () => {
      const { data, error } = await supabase
        .from('players')
        .select(PLAYER_COLUMNS)
        .eq('user_id', userId!)
        .maybeSingle()
      if (error) throw error
      return data as unknown as PlayerWithTeam | null
    },
  })
}

export function useTeams() {
  return useQuery({
    queryKey: keys.teams,
    queryFn: async () => {
      const { data, error } = await supabase
        .from('teams')
        .select('*')
        .order('name')
      if (error) throw error
      return data as Team[]
    },
  })
}

/** Xログイン直後: 自分あての未確認カードを探す */
export function useUnclaimedCard(enabled: boolean) {
  return useQuery({
    queryKey: keys.unclaimed,
    enabled,
    staleTime: 0,
    queryFn: async () => {
      const { data, error } = await supabase.rpc('find_my_unclaimed_card')
      if (error) throw error
      const rows = (data ?? []) as Player[]
      return rows[0] ?? null
    },
  })
}

export function useClaimCard() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async (playerId: string) => {
      const { data, error } = await supabase.rpc('claim_card', {
        p_player_id: playerId,
      })
      if (error) throw error
      return data as Player
    },
    onSuccess: () => {
      qc.invalidateQueries()
    },
  })
}

export function useCreateMyPlayer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      userId,
      draft,
      xUserId,
      xHandle,
    }: {
      userId: string
      draft: PlayerDraft
      xUserId?: string | null
      xHandle?: string | null
    }) => {
      const { data, error } = await supabase
        .from('players')
        .insert({
          ...draft,
          user_id: userId,
          claim_status: 'claimed',
          // region_id は都道府県からトリガーが決める
          x_user_id: xUserId ?? null,
          x_handle: xHandle ?? null,
        })
        .select(PLAYER_COLUMNS)
        .single()
      if (error) throw error
      return data as unknown as PlayerWithTeam
    },
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useUpdateMyPlayer() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({ id, draft }: { id: string; draft: Partial<PlayerDraft> }) => {
      const { data, error } = await supabase
        .from('players')
        .update(draft)
        .eq('id', id)
        .select(PLAYER_COLUMNS)
        .single()
      if (error) throw error
      return data as unknown as PlayerWithTeam
    },
    onSuccess: () => qc.invalidateQueries(),
  })
}

export function useCreateTeam() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      name,
      prefecture,
      userId,
    }: {
      name: string
      prefecture: string
      userId: string
    }) => {
      const { data, error } = await supabase
        .from('teams')
        .insert({ name, prefecture, created_by: userId })
        .select('*')
        .single()
      if (error) throw error
      return data as Team
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: keys.teams }),
  })
}

export function useUploadAvatar() {
  return useMutation({
    mutationFn: async ({ userId, file }: { userId: string; file: File }) => {
      const ext = file.name.split('.').pop()?.toLowerCase() ?? 'jpg'
      const path = `${userId}/avatar-${Date.now()}.${ext}`
      const { error } = await supabase.storage
        .from(AVATAR_BUCKET)
        .upload(path, file, { upsert: true, cacheControl: '3600' })
      if (error) throw error
      return path
    },
  })
}

export function useReport() {
  return useMutation({
    mutationFn: async ({
      targetId,
      reason,
      reporterId,
    }: {
      targetId: string
      reason: string
      reporterId: string | null
    }) => {
      const { error } = await supabase.from('reports').insert({
        target_type: 'player',
        target_id: targetId,
        reason,
        reporter_id: reporterId,
      })
      if (error) throw error
    },
  })
}

/** 削除依頼。受け付けた時点で未確認カードは非公開になる。 */
export function useRequestDeletion() {
  const qc = useQueryClient()
  return useMutation({
    mutationFn: async ({
      playerId,
      reason,
      contact,
    }: {
      playerId: string
      reason?: string
      contact?: string
    }) => {
      const { error } = await supabase.rpc('request_card_deletion', {
        p_player_id: playerId,
        p_reason: reason ?? null,
        p_contact: contact ?? null,
      })
      if (error) throw error
    },
    onSuccess: () => qc.invalidateQueries(),
  })
}
