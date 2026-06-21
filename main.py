"""
main.py — 숏폼 릴스 일괄 생성 & 예약 시스템 진입점

실행 순서:
  1. GPT-4o로 20개 콘텐츠 기획 (JSON)
  2. 각 콘텐츠를 7초 MP4로 합성
  3. Buffer API로 하루 1개씩 예약 발행
"""
import json
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

# 모듈 경로 추가
sys.path.insert(0, str(Path(__file__).parent))
from modules.video_editor import build_video

load_dotenv()

TOTAL_REELS     = 20
CONTENT_CATEGORY = os.getenv("CONTENT_CATEGORY", "자기계발/동기부여")
PLAN_CACHE_PATH  = Path("output/content_plan.json")


# ──────────────────────────────────────────
# STEP 1: GPT-4o 콘텐츠 기획
# ──────────────────────────────────────────
def generate_content_plan(client: OpenAI) -> list[dict]:
    """GPT-4o로 릴스 20개 분량의 콘텐츠를 한 번에 기획한다."""

    # 캐시가 있으면 재사용 (API 비용 절감)
    if PLAN_CACHE_PATH.exists():
        print(f"캐시된 콘텐츠 기획안 사용: {PLAN_CACHE_PATH}")
        with open(PLAN_CACHE_PATH, encoding="utf-8") as f:
            return json.load(f)

    print("GPT-4o로 콘텐츠 기획 중... (약 20~40초 소요)")

    system_prompt = (
        "당신은 인스타그램 릴스 전문 콘텐츠 기획자입니다. "
        "팔로워 반응률과 도달율을 최우선으로 고려하며, "
        "한국어 사용자를 타겟으로 하는 숏폼 콘텐츠를 기획합니다."
    )

    user_prompt = f"""
인스타그램 릴스 "{CONTENT_CATEGORY}" 카테고리로 한 달 치 콘텐츠 {TOTAL_REELS}개를 기획해 주세요.

반드시 아래 JSON 배열 형식만 출력하세요 (코드 블록 없이 순수 JSON):

[
  {{
    "theme": "콘텐츠 주제 및 회차 (예: 성공하는 사람들의 아침 습관 1편)",
    "overlay_text": "배경 이미지 중앙에 표시될 임팩트 있는 2~3줄 짧은 명언/문구\\n(줄바꿈은 \\\\n으로 구분, 각 줄 최대 16자)",
    "instagram_caption": "피드 본문 캡션 (200~300자, 관련 해시태그 10개 포함)"
  }},
  ...
]

요구사항:
- overlay_text는 한 줄 최대 16자, 총 2~3줄로 제한
- instagram_caption은 훅(첫 문장)으로 시작하고 CTA로 마무리
- 각 콘텐츠는 독립적이고 시리즈 연속성도 갖도록 구성
- 해시태그는 대중적인 것 5개 + 틈새 3개 + 브랜드 2개 조합
"""

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        temperature=0.85,
        max_tokens=6000,
        response_format={"type": "json_object"},
    )

    raw = response.choices[0].message.content.strip()

    # json_object 모드는 최상위가 객체여야 하므로 배열을 감쌌을 수 있음
    parsed = json.loads(raw)
    if isinstance(parsed, dict):
        # {"contents": [...]} 형태로 올 수 있음
        content_list = next(iter(parsed.values()))
    else:
        content_list = parsed

    if len(content_list) < TOTAL_REELS:
        raise ValueError(f"GPT가 {len(content_list)}개만 생성했습니다 (목표: {TOTAL_REELS}개). 재실행해 주세요.")

    content_list = content_list[:TOTAL_REELS]

    # 캐시 저장
    PLAN_CACHE_PATH.parent.mkdir(exist_ok=True)
    with open(PLAN_CACHE_PATH, "w", encoding="utf-8") as f:
        json.dump(content_list, f, ensure_ascii=False, indent=2)
    print(f"콘텐츠 기획 완료 → {PLAN_CACHE_PATH}")

    return content_list


# ──────────────────────────────────────────
# STEP 2+3: 대량 생산 루프 (영상 제작 → Buffer 예약을 1개씩 처리)
# ──────────────────────────────────────────
def create_bulk_reels(content_list: list[dict]):
    """
    20개 릴스를 하나씩 순서대로 처리한다.
    영상 제작 완료 즉시 Buffer 예약까지 연결해 메모리 효율을 높인다.
    """
    from modules.buffer_publisher import schedule_post
    import time

    print(f"\n{'='*50}")
    print(f"대량 생산 루프 시작 — 총 {TOTAL_REELS}개")
    print(f"{'='*50}")

    results = []

    for index, item in enumerate(content_list, start=1):
        print(f"\n[{index:02d}/{TOTAL_REELS}] {item['theme']}")
        print(f"  번째 릴스 영상 제작 시작합니다...")

        try:
            # 실버 맞춤형 큰 자막 넣어서 이미지 합성 (Pillow)
            # + 음악 입혀서 7초 영상으로 굽기 (FFmpeg)
            video_path = build_video(item["overlay_text"], index)

            # 버퍼 API로 내일부터 하루에 1개씩 순차 예약 배포 설정
            # days_offset=index → 1일 뒤, 2일 뒤, 3일 뒤... 자동으로 날짜 분산!
            schedule_post(
                video_path=video_path,
                caption=item["instagram_caption"],
                day_offset=index,
            )

            print(f"  [{index:02d}/{TOTAL_REELS}] 완료 및 버퍼 예약 완료!")
            results.append({"index": index, "theme": item["theme"], "status": "success"})

        except Exception as e:
            print(f"  !! [{index:02d}] 실패: {e}")
            results.append({"index": index, "theme": item["theme"], "status": "error", "error": str(e)})

        # API 과부하 방지용 1초 휴식
        if index < TOTAL_REELS:
            time.sleep(1)

    # 최종 요약
    success = sum(1 for r in results if r["status"] == "success")
    print(f"\n{'='*50}")
    print(f"전체 완료: {success}/{TOTAL_REELS}개 성공")
    print(f"{'='*50}")

    # 결과 로그 저장
    log_path = Path("output/bulk_results.json")
    log_path.parent.mkdir(exist_ok=True)
    with open(log_path, "w", encoding="utf-8") as f:
        import json as _json
        _json.dump(results, f, ensure_ascii=False, indent=2)
    print(f"결과 로그 저장 → {log_path}")

    return results


# ──────────────────────────────────────────
# 메인 실행
# ──────────────────────────────────────────
def main():
    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        print("[오류] .env 파일에 OPENAI_API_KEY가 설정되지 않았습니다.")
        sys.exit(1)

    client = OpenAI(api_key=api_key)

    # 실행 모드 선택
    print("=" * 50)
    print("숏폼 릴스 자동화 시스템")
    print("=" * 50)
    print("실행 모드를 선택하세요:")
    print("  1) 전체 실행 (기획 → 영상 생성 → Buffer 예약)")
    print("  2) 기획만 (GPT 콘텐츠 생성)")
    print("  3) 영상만 생성 (캐시된 기획안 사용)")
    print("  4) Buffer 예약만 (생성된 영상 사용)")
    mode = input("번호 입력 (기본값 1): ").strip() or "1"

    if mode in ("1", "2"):
        content_list = generate_content_plan(client)
    else:
        if not PLAN_CACHE_PATH.exists():
            print("[오류] 기획안 캐시가 없습니다. 먼저 모드 1 또는 2를 실행하세요.")
            sys.exit(1)
        with open(PLAN_CACHE_PATH, encoding="utf-8") as f:
            content_list = json.load(f)

    if mode == "1":
        # 핵심: 영상 제작 + Buffer 예약을 한 루프에서 1개씩 처리
        create_bulk_reels(content_list)
    elif mode == "3":
        # 영상만 생성 (Buffer 예약 없이)
        for i, item in enumerate(content_list, start=1):
            print(f"\n[{i:02d}/{TOTAL_REELS}] {item['theme']}")
            try:
                build_video(item["overlay_text"], i)
            except Exception as e:
                print(f"  !! 실패: {e}")
    elif mode == "4":
        # 이미 생성된 영상으로 Buffer 예약만 실행
        from modules.buffer_publisher import schedule_post
        import time
        for i, item in enumerate(content_list, start=1):
            vp = Path(f"output/output_{i}.mp4")
            if not vp.exists():
                print(f"  [{i:02d}] 영상 없음, 건너뜀: {vp}")
                continue
            print(f"\n[{i:02d}/{TOTAL_REELS}] {item['theme']}")
            try:
                schedule_post(vp, item["instagram_caption"], day_offset=i)
            except Exception as e:
                print(f"  !! 실패: {e}")
            if i < TOTAL_REELS:
                time.sleep(1)

    print("\n모든 작업이 완료되었습니다.")


if __name__ == "__main__":
    main()
