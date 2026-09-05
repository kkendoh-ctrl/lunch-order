/** フェーズ2・3は機能フラグで隠す。既定はどちらもオフ。 */
const on = (value: string | undefined) => value === 'true' || value === '1'

export const FEATURES = {
  badges: on(import.meta.env.VITE_FEATURE_BADGES),
  match: on(import.meta.env.VITE_FEATURE_MATCH),
}
