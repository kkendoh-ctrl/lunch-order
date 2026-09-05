/**
 * Xの公開プロフィールから「未確認カード」を作る取り込みスクリプト（雛形）。
 *
 *   npm run import:x -- handles.txt
 *   （handles.txt に1行1アカウント。@は付けても付けなくてもよい）
 *
 * 前提と決めごと:
 *   - X API v2 の Basic 以上が必要。無料枠ではユーザー取得ができない。
 *   - 取り込むのは Xで公開されている範囲だけ（表示名・アイコン・自己紹介・所在地）。
 *     DMや非公開情報は扱わない。
 *   - 取得したデータの再配布・第三者提供はしない。図鑑の表示にだけ使う。
 *   - 出典として source_url（プロフィールURL）を必ず残す。
 *   - レート制限に当たったら x-rate-limit-reset まで待つ。
 *   - 所在地から都道府県を読み取れなかった人は取り込まない（誤った地方に載せないため）。
 */
import { readFileSync } from 'node:fs'
import { createClient } from '@supabase/supabase-js'

const SUPABASE_URL = process.env.SUPABASE_URL
const SERVICE_KEY = process.env.SUPABASE_SERVICE_ROLE_KEY
const BEARER = process.env.X_BEARER_TOKEN

const PREFECTURES = [
  '北海道','青森県','岩手県','宮城県','秋田県','山形県','福島県',
  '茨城県','栃木県','群馬県','埼玉県','千葉県','東京都','神奈川県',
  '新潟県','富山県','石川県','福井県','山梨県','長野県','岐阜県','静岡県','愛知県',
  '三重県','滋賀県','京都府','大阪府','兵庫県','奈良県','和歌山県',
  '鳥取県','島根県','岡山県','広島県','山口県',
  '徳島県','香川県','愛媛県','高知県',
  '福岡県','佐賀県','長崎県','熊本県','大分県','宮崎県','鹿児島県','沖縄県',
]

/** 「東京」「Tokyo」のような書き方も拾う */
function guessPrefecture(location) {
  if (!location) return null
  const hit = PREFECTURES.find((p) => location.includes(p))
  if (hit) return hit
  const bare = PREFECTURES.find((p) => location.includes(p.replace(/[都道府県]$/, '')))
  return bare ?? null
}

async function fetchUsers(usernames) {
  const url = new URL('https://api.x.com/2/users/by')
  url.searchParams.set('usernames', usernames.join(','))
  url.searchParams.set(
    'user.fields',
    'id,name,username,description,location,profile_image_url,url',
  )

  const res = await fetch(url, {
    headers: { Authorization: `Bearer ${BEARER}` },
  })

  if (res.status === 429) {
    const reset = Number(res.headers.get('x-rate-limit-reset') ?? 0) * 1000
    const waitMs = Math.max(reset - Date.now(), 60_000)
    console.warn(`レート制限。${Math.ceil(waitMs / 1000)}秒待ちます`)
    await new Promise((r) => setTimeout(r, waitMs))
    return fetchUsers(usernames)
  }
  if (!res.ok) {
    throw new Error(`X API ${res.status}: ${await res.text()}`)
  }
  const json = await res.json()
  return json.data ?? []
}

async function main() {
  if (!BEARER) {
    console.error(
      [
        'X_BEARER_TOKEN が未設定です。',
        '',
        'X API v2 のユーザー取得は Basic 以上の有料プランが前提です。',
        '費用を確認したうえで .env.local に X_BEARER_TOKEN を設定してください。',
        'この取り込みが動かなくても、図鑑本体（自分でカードを作る流れ）は動きます。',
      ].join('\n'),
    )
    process.exit(1)
  }
  if (!SUPABASE_URL || !SERVICE_KEY) {
    console.error('SUPABASE_URL と SUPABASE_SERVICE_ROLE_KEY が必要です。')
    process.exit(1)
  }

  const file = process.argv[2]
  if (!file) {
    console.error('使い方: npm run import:x -- handles.txt')
    process.exit(1)
  }

  const handles = readFileSync(file, 'utf8')
    .split('\n')
    .map((l) => l.trim().replace(/^@/, ''))
    .filter(Boolean)

  const supabase = createClient(SUPABASE_URL, SERVICE_KEY, {
    auth: { persistSession: false },
  })

  // /2/users/by は1回100件まで
  for (let i = 0; i < handles.length; i += 100) {
    const batch = handles.slice(i, i + 100)
    const users = await fetchUsers(batch)

    for (const u of users) {
      const prefecture = guessPrefecture(u.location)
      if (!prefecture) {
        console.warn(`所在地から都道府県を読み取れないので見送り: @${u.username}`)
        continue
      }

      const { data: existing } = await supabase
        .from('players')
        .select('id, claim_status')
        .eq('x_user_id', u.id)
        .maybeSingle()

      if (existing) {
        // 本人確認済みのカードは、こちらから上書きしない。
        if (existing.claim_status === 'claimed') {
          console.log(`本人が編集中なので触らない: @${u.username}`)
          continue
        }
        await supabase
          .from('players')
          .update({
            nickname: u.name.slice(0, 20),
            x_handle: u.username,
            source_url: `https://x.com/${u.username}`,
          })
          .eq('id', existing.id)
        console.log(`更新: @${u.username}`)
        continue
      }

      const { data, error } = await supabase
        .from('players')
        .insert({
          nickname: u.name.slice(0, 20),
          prefecture,
          // アイコンは元URLをそのまま参照する（削除依頼が来たら即非公開になる）
          avatar_url: u.profile_image_url?.replace('_normal', '') ?? null,
          x_user_id: u.id,
          x_handle: u.username,
          source_url: `https://x.com/${u.username}`,
          claim_status: 'unclaimed',
          visibility: 'public',
        })
        .select('dex_number')
        .single()

      if (error) {
        console.error(`失敗: @${u.username}`, error.message)
        continue
      }
      console.log(`No.${String(data.dex_number).padStart(4, '0')} @${u.username}`)
    }

    // 続けて叩きすぎない
    await new Promise((r) => setTimeout(r, 1500))
  }
}

main().catch((e) => {
  console.error(e)
  process.exit(1)
})
