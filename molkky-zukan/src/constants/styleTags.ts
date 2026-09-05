/** プレースタイル固定タグ。1枚のカードに最大2つまで。 */
export const STYLE_TAGS = [
  '遠投型',
  '精密型',
  '一発狙い',
  '堅実積み上げ',
  'メンタル強者',
  'ムードメーカー',
  '左投げ',
  '高速テンポ',
] as const

export type StyleTag = (typeof STYLE_TAGS)[number]

export const MAX_STYLE_TAGS = 2
