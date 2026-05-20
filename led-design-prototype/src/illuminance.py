"""JIS Z 9127 に基づく照度計算と灯具選定の試算。

正確な照度シミュレーションは各メーカーの専用ソフト（DIALux等）で行うこと。
本モジュールは設計ドラフト用の概算値を提供する。

【方式】
LED化工事の多くは「1:1置換」（既存灯数を維持してLED灯具に交換）が主流のため、
本プロトタイプも 1:1置換を基本としつつ、JIS基準を満たすか達成照度を試算する。
"""

from dataclasses import dataclass

# JIS Z 9127 推奨水平面平均照度 (lx)
ILLUMINANCE_STANDARDS: dict[str, dict[str, dict[str, int]]] = {
    "baseball": {
        "official": {"infield": 1500, "outfield": 750},
        "practice": {"infield": 500, "outfield": 300},
    },
    "tennis": {
        "official": {"court": 500},
        "practice": {"court": 200},
    },
    "track_field": {
        "official": {"track": 500},
        "practice": {"track": 100},
    },
    "soccer": {
        "official": {"field": 500},
        "practice": {"field": 75},
    },
}

LAMP_TYPE_JP = {
    "mercury": "水銀灯",
    "metal_halide": "メタルハライドランプ",
    "halogen": "ハロゲンランプ",
    "fluorescent": "蛍光灯",
}

# 既存光源 → LED置換目安（1灯あたり相当W）
# 出典: knowledge/led_floodlights.md
REPLACEMENT_TABLE: dict[tuple[str, int], int] = {
    ("mercury", 400): 150,
    ("mercury", 700): 250,
    ("mercury", 1000): 400,
    ("metal_halide", 400): 200,
    ("metal_halide", 700): 300,
    ("metal_halide", 1000): 400,
    ("metal_halide", 2000): 1000,
    ("halogen", 500): 100,
    ("halogen", 1000): 200,
}

# LED灯具の仕様（概算）。watt → (lumens, 単価)
LED_FIXTURES: dict[int, dict] = {
    150: {"lumens": 22500, "unit_price": 120000},
    200: {"lumens": 30000, "unit_price": 150000},
    250: {"lumens": 37500, "unit_price": 180000},
    300: {"lumens": 45000, "unit_price": 200000},
    400: {"lumens": 60000, "unit_price": 240000},
    500: {"lumens": 75000, "unit_price": 290000},
    600: {"lumens": 90000, "unit_price": 350000},
    1000: {"lumens": 150000, "unit_price": 500000},
}

# 計算定数
UTILIZATION_FACTOR = 0.60   # 照明率（スポーツ用ナロー配光、適切な配光設計を想定）
MAINTENANCE_FACTOR = 0.75   # 保守率（屋外LED）


@dataclass
class IlluminanceArea:
    name: str
    area_m2: int
    required_lx: int
    achieved_lx_estimate: float
    meets_standard: bool


@dataclass
class FixturePlan:
    """1:1置換ベースの灯具計画。"""
    total_count: int
    led_watt_per_fixture: int
    led_lumens_per_fixture: int
    total_watt: int
    total_lumens: int
    unit_price: int


def plan_fixtures(
    existing_lamp_type: str,
    existing_lamp_watt: int,
    existing_total_count: int,
) -> FixturePlan:
    """既存灯具を1:1でLEDに置換する計画を作成。"""
    key = (existing_lamp_type, existing_lamp_watt)
    if key not in REPLACEMENT_TABLE:
        # 表にない場合は、既存Wの30%を目安にする
        led_watt = max(150, int(existing_lamp_watt * 0.3))
        # 最も近い規格Wを選ぶ
        led_watt = min(LED_FIXTURES.keys(), key=lambda w: abs(w - led_watt))
    else:
        led_watt = REPLACEMENT_TABLE[key]

    spec = LED_FIXTURES[led_watt]
    return FixturePlan(
        total_count=existing_total_count,
        led_watt_per_fixture=led_watt,
        led_lumens_per_fixture=spec["lumens"],
        total_watt=led_watt * existing_total_count,
        total_lumens=spec["lumens"] * existing_total_count,
        unit_price=spec["unit_price"],
    )


def estimate_areas(
    facility_type: str,
    use_class: str,
    dimensions: dict,
    plan: FixturePlan,
) -> list[IlluminanceArea]:
    """1:1置換した場合の達成照度を領域ごとに試算。

    実際は領域ごとに灯具を分配するが、本プロトタイプは
    各領域に「面積比に応じた光束が向く」と仮定した粗い試算。
    """
    standards = ILLUMINANCE_STANDARDS.get(facility_type, {}).get(use_class, {})
    if not standards:
        raise ValueError(f"Unknown facility/class: {facility_type}/{use_class}")

    # 領域別面積を取得
    area_map = {}
    for key in standards:
        m2 = dimensions.get(f"{key}_m2") or dimensions.get(key) or 0
        area_map[key] = m2

    # 内野/外野のように複数領域がある場合、面積比ではなく
    # 「内野は外野の2倍の照度になるよう配光」と仮定して灯数配分
    total_weighted = sum(standards[k] * area_map[k] for k in standards)
    areas = []
    for key, required_lx in standards.items():
        area_m2 = area_map[key]
        # この領域に振り向けられる光束（重み付き配分）
        weight = (required_lx * area_m2) / total_weighted if total_weighted else 0
        allocated_lumens = plan.total_lumens * weight
        achieved = (allocated_lumens * UTILIZATION_FACTOR * MAINTENANCE_FACTOR) / area_m2 if area_m2 else 0
        areas.append(
            IlluminanceArea(
                name=key,
                area_m2=area_m2,
                required_lx=required_lx,
                achieved_lx_estimate=achieved,
                meets_standard=achieved >= required_lx,
            )
        )
    return areas


def calc_energy_savings(
    existing_total_watt: int,
    new_total_watt: int,
    annual_hours: int,
    electricity_unit_price_yen: float = 22.0,  # 業務用電力 円/kWh
) -> dict:
    """省エネ効果の試算。"""
    existing_kwh = existing_total_watt * annual_hours / 1000
    new_kwh = new_total_watt * annual_hours / 1000
    saved_kwh = existing_kwh - new_kwh
    saved_yen = saved_kwh * electricity_unit_price_yen
    co2_saved_kg = saved_kwh * 0.434  # 全国平均CO2排出係数
    reduction_pct = (saved_kwh / existing_kwh * 100) if existing_kwh else 0

    return {
        "existing_kwh": existing_kwh,
        "new_kwh": new_kwh,
        "saved_kwh": saved_kwh,
        "saved_yen": saved_yen,
        "co2_saved_kg": co2_saved_kg,
        "reduction_pct": reduction_pct,
    }


def format_illuminance_table(areas: list[IlluminanceArea], plan: FixturePlan) -> str:
    """照度計算結果をMarkdownテーブルに整形。"""
    AREA_NAME_JP = {
        "infield": "内野",
        "outfield": "外野",
        "court": "コート全面",
        "track": "トラック",
        "field": "フィールド",
    }
    lines = [
        f"**灯具計画**: LED {plan.led_watt_per_fixture}W × {plan.total_count}灯 "
        f"（既存灯具を1:1置換）",
        "",
        f"- 1灯あたり光束: {plan.led_lumens_per_fixture:,} lm",
        f"- 総光束: {plan.total_lumens:,} lm",
        f"- 総消費電力: {plan.total_watt:,} W ({plan.total_watt/1000:.1f} kW)",
        "",
        "**達成照度の試算**（照明率 U=0.60、保守率 M=0.75 として試算）",
        "",
        "| 領域 | 面積 (m²) | JIS基準 (lx) | 試算達成値 (lx) | 判定 |",
        "|---|---:|---:|---:|:---:|",
    ]
    for a in areas:
        mark = "✓" if a.meets_standard else "△ 要再検討"
        lines.append(
            f"| {AREA_NAME_JP.get(a.name, a.name)} | {a.area_m2:,} | "
            f"{a.required_lx} | {a.achieved_lx_estimate:.0f} | {mark} |"
        )
    lines.append("")
    lines.append("注：実設計ではDIALux等の照明シミュレーションソフトで配光・均斉度を含めた検証が必要。")
    return "\n".join(lines)


def format_economic_table(savings: dict, existing_watt: int, new_watt: int) -> str:
    """省エネ効果をMarkdownテーブルに整形。"""
    lines = [
        "| 項目 | 既存 | LED化後 |",
        "|---|---:|---:|",
        f"| 総消費電力 | {existing_watt/1000:.1f} kW | {new_watt/1000:.1f} kW |",
        f"| 年間消費電力 | {savings['existing_kwh']:,.0f} kWh | {savings['new_kwh']:,.0f} kWh |",
        "",
        "| 削減効果 | 値 |",
        "|---|---:|",
        f"| 消費電力削減量 | {savings['saved_kwh']:,.0f} kWh/年 ({savings['reduction_pct']:.1f}% 削減) |",
        f"| 年間電気代削減 | 約 {savings['saved_yen']:,.0f} 円 |",
        f"| 年間CO2削減 | 約 {savings['co2_saved_kg']:,.0f} kg-CO2 |",
    ]
    return "\n".join(lines)


def format_cost_estimate(plan: FixturePlan, scope: dict) -> str:
    """概算工事費をMarkdownテーブルに整形。"""
    fixture_cost = plan.unit_price * plan.total_count
    install_cost = plan.total_count * 45000   # 取付工事
    removal_cost = plan.total_count * 22000   # 撤去・処分

    panel_cost = 600000 if scope.get("control_panel_upgrade") else 0
    wiring_cost = {"full": 2000000, "partial": 800000, "none": 0}.get(
        scope.get("wiring_renewal", "none"), 0
    )
    misc_cost = int((fixture_cost + install_cost + removal_cost) * 0.15)

    subtotal = fixture_cost + install_cost + removal_cost + panel_cost + wiring_cost + misc_cost
    tax = int(subtotal * 0.10)
    total = subtotal + tax

    lines = [
        "| 費目 | 概算 (円) |",
        "|---|---:|",
        f"| LED投光器（{plan.led_watt_per_fixture}W × {plan.total_count}灯） | {fixture_cost:,} |",
        f"| 取付工事 | {install_cost:,} |",
        f"| 既存撤去・処分（PCB含有確認含む） | {removal_cost:,} |",
    ]
    if panel_cost:
        lines.append(f"| 制御盤改修 | {panel_cost:,} |")
    if wiring_cost:
        lines.append(f"| 配線改修（{scope.get('wiring_renewal')}） | {wiring_cost:,} |")
    lines.extend([
        f"| 諸経費（15%） | {misc_cost:,} |",
        f"| **小計** | **{subtotal:,}** |",
        f"| 消費税（10%） | {tax:,} |",
        f"| **合計** | **{total:,}** |",
    ])
    return "\n".join(lines)
