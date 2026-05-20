"""LED化工事設計書ドラフトをClaude APIで生成する。

Usage:
    python -m src.generate inputs/sample_baseball.yaml
"""

import json
import sys
from datetime import datetime
from pathlib import Path

import anthropic
import yaml
from jinja2 import Template

from src.illuminance import (
    LAMP_TYPE_JP,
    calc_energy_savings,
    estimate_areas,
    format_cost_estimate,
    format_economic_table,
    format_illuminance_table,
    plan_fixtures,
)

ROOT = Path(__file__).parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge"
TEMPLATES_DIR = ROOT / "templates"
OUTPUTS_DIR = ROOT / "outputs"

MODEL = "claude-opus-4-7"

SYSTEM_PROMPT = """あなたは浦安市の公共工事設計を支援するアシスタントです。
スポーツ施設のLED化工事について、設計書のドラフトを日本語で作成します。

以下の参考資料を踏まえて、各セクションを書いてください。
資料に書かれていない数値や仕様を勝手に作らないこと。
不明な箇所は「※現地調査にて確認」「※発注者と協議」などと明記してください。

# 参考資料

## JIS Z 9127（屋外スポーツ施設の照明基準）

{jis_doc}

## 浦安市 標準特記仕様（雛形）

{spec_doc}

## LED投光器カタログ抜粋

{catalog_doc}
"""

USER_PROMPT = """以下の案件について、LED化工事の設計書ドラフトを作成します。
照度計算と概算費用は既に試算済みなので、文章セクションだけ書いてください。

# 案件情報（YAML）

```yaml
{input_yaml}
```

# 試算済み照度計算結果

{illuminance_table}

# 試算済み省エネ効果

{economic_table}

# 概算工事費

{cost_table}

# 求めるセクション

以下のJSON形式で、各セクションの本文（Markdown）だけを出力してください。
コードブロックや余計な前置きは不要、JSONそのものだけを返してください。

```json
{{
  "overview": "1. 工事概要 の本文。発注者・工事場所・工期・目的を簡潔に",
  "design_policy": "2. 設計方針 の本文。JIS Z 9127準拠、省エネ、既存施設運営への配慮など",
  "existing_issues": "3.2 既存設備の課題 の本文。経年劣化・効率低下・寿命到来・水銀灯の生産終了など",
  "fixture_selection": "4.2 LED灯具の選定 の本文。要求性能、IP等級、配光、メーカー指定の考え方",
  "scope": "4.3 工事範囲 の本文。撤去・新設・配線・制御盤・試験までの範囲を箇条書きで",
  "economic_narrative": "5. 省エネ・経済効果 の補足説明。投資回収年数の概算と、間接効果（高所作業車削減等）",
  "special_specifications": "6. 特記仕様 の本文。IP65以上、力率0.95以上、5年保証、PCB含有確認、廃棄物マニフェスト等を箇条書きで",
  "construction_plan": "7. 施工計画 の本文。工程概略、施設利用との調整、夜間作業の扱い、安全管理",
  "inspection": "8. 検査・試験 の本文。絶縁抵抗、接地抵抗、照度測定（JIS Z 9127準拠、複数点）、均斉度確認",
  "deliverables": "9. 提出書類 の本文。着工前・施工中・完成時に分けて箇条書きで"
}}
```
"""


def load_knowledge() -> tuple[str, str, str]:
    """RAG用の参考資料を読み込み。"""
    jis = (KNOWLEDGE_DIR / "jis_z9127.md").read_text(encoding="utf-8")
    spec = (KNOWLEDGE_DIR / "urayasu_spec.md").read_text(encoding="utf-8")
    catalog = (KNOWLEDGE_DIR / "led_floodlights.md").read_text(encoding="utf-8")
    return jis, spec, catalog


def generate_ai_sections(
    input_data: dict,
    illuminance_table: str,
    economic_table: str,
    cost_table: str,
) -> dict:
    """Claude APIで文章セクションを生成。"""
    client = anthropic.Anthropic()
    jis, spec, catalog = load_knowledge()

    system_text = SYSTEM_PROMPT.format(
        jis_doc=jis, spec_doc=spec, catalog_doc=catalog
    )
    user_text = USER_PROMPT.format(
        input_yaml=yaml.dump(input_data, allow_unicode=True, sort_keys=False),
        illuminance_table=illuminance_table,
        economic_table=economic_table,
        cost_table=cost_table,
    )

    print(f"[info] Calling Claude API ({MODEL})...", file=sys.stderr)
    response = client.messages.create(
        model=MODEL,
        max_tokens=8000,
        system=[
            {
                "type": "text",
                "text": system_text,
                "cache_control": {"type": "ephemeral"},  # 参考資料を5分キャッシュ
            }
        ],
        messages=[{"role": "user", "content": user_text}],
    )

    text = next(b.text for b in response.content if b.type == "text").strip()

    # JSONを取り出す（モデルがコードブロックで囲む場合がある）
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
        text = text.strip()

    try:
        sections = json.loads(text)
    except json.JSONDecodeError as e:
        print(f"[error] JSON parse failed: {e}", file=sys.stderr)
        print(f"[error] Raw output:\n{text}", file=sys.stderr)
        raise

    cache_read = response.usage.cache_read_input_tokens or 0
    cache_create = response.usage.cache_creation_input_tokens or 0
    print(
        f"[info] tokens: in={response.usage.input_tokens} "
        f"cache_read={cache_read} cache_create={cache_create} "
        f"out={response.usage.output_tokens}",
        file=sys.stderr,
    )
    return sections


def render_document(input_data: dict, output_path: Path) -> None:
    """入力→計算→AI生成→Markdown出力 のメインフロー。"""
    facility = input_data["facility"]
    existing = input_data["existing_lighting"]
    scope = input_data.get("scope", {})

    # 1. 灯具計画（1:1置換）
    plan = plan_fixtures(
        existing_lamp_type=existing["lamp_type"],
        existing_lamp_watt=existing["lamp_watt"],
        existing_total_count=existing["total_fixtures"],
    )

    # 2. 達成照度の試算
    areas = estimate_areas(
        facility_type=facility["type"],
        use_class=facility["use_class"],
        dimensions=facility["dimensions"],
        plan=plan,
    )
    illuminance_table = format_illuminance_table(areas, plan)

    # 3. 省エネ効果
    existing_total_watt = existing["total_fixtures"] * existing["lamp_watt"]
    savings = calc_energy_savings(
        existing_total_watt=existing_total_watt,
        new_total_watt=plan.total_watt,
        annual_hours=existing["annual_usage_hours"],
    )
    economic_table = format_economic_table(savings, existing_total_watt, plan.total_watt)

    # 4. 概算工事費
    cost_table = format_cost_estimate(plan, scope)

    # 4. AIによる文章生成
    ai_sections = generate_ai_sections(
        input_data, illuminance_table, economic_table, cost_table
    )

    # 5. テンプレートに流し込み
    template_text = (TEMPLATES_DIR / "design_doc.md.j2").read_text(encoding="utf-8")
    template = Template(template_text)

    existing_view = {
        **existing,
        "lamp_type_jp": LAMP_TYPE_JP.get(existing["lamp_type"], existing["lamp_type"]),
        "total_watt_kw": existing_total_watt / 1000,
    }

    rendered = template.render(
        project=input_data["project"],
        existing=existing_view,
        ai_sections=ai_sections,
        illuminance_calc_table=illuminance_table,
        economic_effect_table=economic_table,
        cost_estimate_table=cost_table,
        generated_at=datetime.now().strftime("%Y-%m-%d %H:%M"),
    )

    output_path.write_text(rendered, encoding="utf-8")
    print(f"[ok] wrote {output_path}", file=sys.stderr)


def main() -> int:
    if len(sys.argv) < 2:
        print("Usage: python -m src.generate <input.yaml>", file=sys.stderr)
        return 1

    input_path = Path(sys.argv[1])
    input_data = yaml.safe_load(input_path.read_text(encoding="utf-8"))

    OUTPUTS_DIR.mkdir(exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_path = OUTPUTS_DIR / f"{input_path.stem}_{timestamp}.md"

    render_document(input_data, output_path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
