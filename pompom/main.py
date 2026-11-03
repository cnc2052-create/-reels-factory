# -*- coding: utf-8 -*-
"""
폼폼 PomPom — 숏폼 어필리에이트 공장
5개 AI 계정으로 올리브영/쿠팡 제휴 릴스 자동 생성·발행
영상: Pexels 무료 소스 + Remotion 자막 합성
"""
import json, os, sys
import argparse
from pathlib import Path
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from modules.content_pipeline import run_pipeline, NICHE_MAP
from modules.multi_publisher import publish_all_accounts, get_posting_schedule
from modules.auto_researcher import research_top_product
from modules.notion_saver import save_to_notion

CONFIG_PATH = Path(__file__).parent / "config" / "personas.json"
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

# 계정별 최근 사용 훅 이력 (세션 내 중복 방지)
_recent_hooks: dict[str, list[int]] = {}


def load_personas() -> list[dict]:
    with open(CONFIG_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["accounts"]


# ───────────────────────────────────────────────────────────
# generate — 제품 리서치 → 스크립트 → 영상 → 노션 저장
# ───────────────────────────────────────────────────────────
def cmd_generate(args):
    personas = load_personas()
    if args.account:
        personas = [p for p in personas if p.get("account_id") == args.account or p.get("id") == args.account]

    print(f"\n🎬 폼폼 콘텐츠 생성 — {len(personas)}개 계정\n{'='*55}")

    all_contents = {}
    for persona in personas:
        account_id = persona.get("account_id", persona.get("id", ""))
        niche = NICHE_MAP.get(account_id, "beauty")
        print(f"\n▶ [{persona['name']}] 리서치 중...")

        # 1. 제품 리서치
        product = research_top_product(niche, persona)
        if not product:
            print(f"  ⚠️ 제품 없음 — 건너뜀")
            continue

        print(f"  📦 선정: {product['name']} / {product['price']:,}원")
        print(f"  💡 바이럴 각도: {product.get('viral_angle','')}")

        # 2. 파이프라인 (스크립트 + Pexels 영상 + Remotion 합성)
        recent = _recent_hooks.get(account_id, [])
        try:
            content = run_pipeline(persona, product, recent_hooks=recent)
            _recent_hooks.setdefault(account_id, []).append(content.get("hook_id", 1))

            print(f"  🎣 훅({content['hook_id']}번): {content['hook_name']}")
            if content.get("final_video_path"):
                print(f"  🎥 영상: {content['final_video_path']}")
            elif content.get("raw_video_path"):
                print(f"  🎥 원본(자막없음): {content['raw_video_path']}")

            # 3. 노션 저장
            page_id = save_to_notion(content, account_id)
            content["notion_page_id"] = page_id

            all_contents[account_id] = content
        except Exception as e:
            print(f"  ❌ 오류: {e}")
            import traceback; traceback.print_exc()

    out_path = OUTPUT_DIR / "generated_contents.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(all_contents, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 생성 완료! → {out_path}")
    return all_contents


# ───────────────────────────────────────────────────────────
# publish — Buffer 자동 예약
# ───────────────────────────────────────────────────────────
def cmd_publish(args):
    out_path = OUTPUT_DIR / "generated_contents.json"
    if not out_path.exists():
        print("❌ 먼저 generate 명령 실행 후 사용하세요")
        return

    with open(out_path, encoding="utf-8") as f:
        contents = json.load(f)

    personas = load_personas()
    print(f"\n📤 폼폼 멀티 발행 시작\n{'='*55}")

    results = publish_all_accounts(contents, personas)
    for r in results:
        ok = "✅" if r.get("buffer", {}).get("ok") else "⚠️"
        sched = r.get("scheduled_at", "")[:16].replace("T", " ")
        print(f"{ok} [{r['persona_name']}] {r['product']} → {sched}")

    print(f"\n✅ Buffer 예약 완료!")


# ───────────────────────────────────────────────────────────
# auto — 생성 + 발행 한 번에
# ───────────────────────────────────────────────────────────
def cmd_auto(args):
    """매일 자동 실행용 — 생성 → 노션 저장 → Buffer 예약"""
    print("\n🤖 폼폼 자동화 파이프라인 시작\n")
    cmd_generate(args)
    cmd_publish(args)
    print("\n🎉 오늘 콘텐츠 완료!")


# ───────────────────────────────────────────────────────────
# schedule — 예약 현황 확인
# ───────────────────────────────────────────────────────────
def cmd_schedule(args):
    personas = load_personas()
    schedule = get_posting_schedule(personas)
    print(f"\n📅 폼폼 발행 스케줄 (향후 7일)\n{'='*55}")
    for item in schedule:
        dt = item["datetime"][:16].replace("T", " ")
        print(f"  {dt}  [{item['name']}]  {item['niche']}")


# ───────────────────────────────────────────────────────────
# status — 계정 현황
# ───────────────────────────────────────────────────────────
def cmd_status(args):
    personas = load_personas()
    print(f"\n🎭 폼폼 계정 현황\n{'='*55}")
    for p in personas:
        print(f"\n  {p.get('display_name', p['name'])}")
        print(f"    니치: {p.get('niche', '')}")
        print(f"    발행: {p.get('posting_time','')} ({', '.join(p.get('posting_days', []))})")


def main():
    parser = argparse.ArgumentParser(description="폼폼 PomPom — 숏폼 어필리에이트 공장")
    sub = parser.add_subparsers(dest="cmd")

    gen = sub.add_parser("generate", help="콘텐츠 생성 (리서치→스크립트→영상→노션)")
    gen.add_argument("--account", help="특정 계정만 (예: pompom_beauty)")

    pub = sub.add_parser("publish", help="Buffer 자동 예약 발행")
    pub.add_argument("--account", help="특정 계정만")

    auto = sub.add_parser("auto", help="생성+발행 원스톱 (매일 자동 실행)")
    auto.add_argument("--account", help="특정 계정만")

    sub.add_parser("schedule", help="발행 스케줄 확인")
    sub.add_parser("status", help="계정 현황 확인")

    args = parser.parse_args()
    if not hasattr(args, "account"):
        args.account = None

    dispatch = {
        "generate": cmd_generate,
        "publish": cmd_publish,
        "auto": cmd_auto,
        "schedule": cmd_schedule,
        "status": cmd_status,
    }
    fn = dispatch.get(args.cmd)
    if fn:
        fn(args)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
