// 都道府県 → 地方の対応表。DB側(0001_init.sql の region_slug_for_prefecture)と同じ内容を持つ。
// 片方を直したら必ずもう片方も直すこと。

export type RegionSlug =
  | 'hokkaido'
  | 'tohoku'
  | 'kanto'
  | 'chubu'
  | 'kinki'
  | 'chugoku'
  | 'shikoku'
  | 'kyushu'

export type Region = {
  /** regions テーブルの id と一致させる（0001_init.sql の seed を参照） */
  id: number
  slug: RegionSlug
  name: string
  displayOrder: number
  /** 地方ごとの差し色。彩度は抑える。 */
  accent: string
}

export const REGIONS: Region[] = [
  { id: 1, slug: 'hokkaido', name: '北海道', displayOrder: 1, accent: '#78909c' },
  { id: 2, slug: 'tohoku', name: '東北', displayOrder: 2, accent: '#7e8a6f' },
  { id: 3, slug: 'kanto', name: '関東', displayOrder: 3, accent: '#96805f' },
  { id: 4, slug: 'chubu', name: '中部', displayOrder: 4, accent: '#6f8a84' },
  { id: 5, slug: 'kinki', name: '近畿', displayOrder: 5, accent: '#8f7280' },
  { id: 6, slug: 'chugoku', name: '中国', displayOrder: 6, accent: '#7b7a96' },
  { id: 7, slug: 'shikoku', name: '四国', displayOrder: 7, accent: '#6d8f78' },
  { id: 8, slug: 'kyushu', name: '九州沖縄', displayOrder: 8, accent: '#a3766b' },
]

export const PREFECTURE_TO_REGION: Record<string, RegionSlug> = {
  北海道: 'hokkaido',

  青森県: 'tohoku',
  岩手県: 'tohoku',
  宮城県: 'tohoku',
  秋田県: 'tohoku',
  山形県: 'tohoku',
  福島県: 'tohoku',

  茨城県: 'kanto',
  栃木県: 'kanto',
  群馬県: 'kanto',
  埼玉県: 'kanto',
  千葉県: 'kanto',
  東京都: 'kanto',
  神奈川県: 'kanto',

  新潟県: 'chubu',
  富山県: 'chubu',
  石川県: 'chubu',
  福井県: 'chubu',
  山梨県: 'chubu',
  長野県: 'chubu',
  岐阜県: 'chubu',
  静岡県: 'chubu',
  愛知県: 'chubu',

  三重県: 'kinki',
  滋賀県: 'kinki',
  京都府: 'kinki',
  大阪府: 'kinki',
  兵庫県: 'kinki',
  奈良県: 'kinki',
  和歌山県: 'kinki',

  鳥取県: 'chugoku',
  島根県: 'chugoku',
  岡山県: 'chugoku',
  広島県: 'chugoku',
  山口県: 'chugoku',

  徳島県: 'shikoku',
  香川県: 'shikoku',
  愛媛県: 'shikoku',
  高知県: 'shikoku',

  福岡県: 'kyushu',
  佐賀県: 'kyushu',
  長崎県: 'kyushu',
  熊本県: 'kyushu',
  大分県: 'kyushu',
  宮崎県: 'kyushu',
  鹿児島県: 'kyushu',
  沖縄県: 'kyushu',
}

export const PREFECTURES = Object.keys(PREFECTURE_TO_REGION)

export function regionOf(prefecture: string): Region | undefined {
  const slug = PREFECTURE_TO_REGION[prefecture]
  return slug ? REGIONS.find((r) => r.slug === slug) : undefined
}

export function regionBySlug(slug: string): Region | undefined {
  return REGIONS.find((r) => r.slug === slug)
}

export function regionById(id: number): Region | undefined {
  return REGIONS.find((r) => r.id === id)
}
