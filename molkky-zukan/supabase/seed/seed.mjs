// ダミーデータ投入（5人分）
//   1. .env.local に SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY を書く
//   2. npm run seed
// service_role キーを使うので、手元でだけ実行すること。
import { createClient } from '@supabase/supabase-js'

const url = process.env.SUPABASE_URL
const key = process.env.SUPABASE_SERVICE_ROLE_KEY

if (!url || !key) {
  console.error(
    'SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY が必要です。.env.local を用意して `npm run seed` で実行してください。',
  )
  process.exit(1)
}

const supabase = createClient(url, key, { auth: { persistSession: false } })

const TEAMS = [
  { name: '三番町スロウ', prefecture: '東京都' },
  { name: '弟子屈ノーザン', prefecture: '北海道' },
]

// 架空の人物。実在のアカウントは入れない。
const PLAYERS = [
  {
    nickname: 'ハルカ',
    prefecture: '東京都',
    team: '三番町スロウ',
    home_ground: '多摩川河川敷',
    win_phrase: 'ここで決めないと、帰れない。',
    miss_cry: 'あーっ、抜けた',
    style_tags: ['精密型', '高速テンポ'],
    is_legend: false,
  },
  {
    nickname: 'クマガイ',
    prefecture: '北海道',
    team: '弟子屈ノーザン',
    home_ground: '町民体育館',
    win_phrase: '雪が降る前に、終わらせる。',
    miss_cry: 'ぬおー',
    style_tags: ['遠投型', 'メンタル強者'],
    is_legend: true,
  },
  {
    nickname: 'とよ',
    prefecture: '愛知県',
    team: null,
    home_ground: '庄内緑地',
    win_phrase: '積んだぶんは、裏切らない。',
    miss_cry: 'うーん',
    style_tags: ['堅実積み上げ'],
    is_legend: false,
  },
  {
    nickname: 'ミナミ',
    prefecture: '福岡県',
    team: null,
    home_ground: '大濠公園',
    win_phrase: '一本で、ひっくり返す。',
    miss_cry: 'いやー！',
    style_tags: ['一発狙い', 'ムードメーカー'],
    is_legend: false,
  },
  {
    nickname: 'サコ',
    prefecture: '香川県',
    team: null,
    home_ground: '中央公園',
    win_phrase: '左からいきます。',
    miss_cry: 'ほい……',
    style_tags: ['左投げ', '精密型'],
    is_legend: false,
  },
]

const teamIds = new Map()

for (const team of TEAMS) {
  const { data: existing } = await supabase
    .from('teams')
    .select('id')
    .eq('name', team.name)
    .maybeSingle()

  if (existing) {
    teamIds.set(team.name, existing.id)
    continue
  }
  const { data, error } = await supabase
    .from('teams')
    .insert(team)
    .select('id')
    .single()
  if (error) throw error
  teamIds.set(team.name, data.id)
  console.log('team:', team.name)
}

for (const p of PLAYERS) {
  const { data: existing } = await supabase
    .from('players')
    .select('id')
    .eq('nickname', p.nickname)
    .eq('prefecture', p.prefecture)
    .maybeSingle()

  if (existing) {
    console.log('skip (already there):', p.nickname)
    continue
  }

  const { team, ...rest } = p
  const { data, error } = await supabase
    .from('players')
    .insert({
      ...rest,
      team_id: team ? teamIds.get(team) : null,
      claim_status: 'unclaimed',
      visibility: 'public',
    })
    .select('dex_number, nickname')
    .single()
  if (error) throw error
  console.log(`No.${String(data.dex_number).padStart(4, '0')} ${data.nickname}`)
}

console.log('\n投入しました。図鑑トップを開いて人数を確認してください。')
