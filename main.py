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
from modules.buffer_publisher import publish_all

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
# STEP 2: 영상 일괄 생성
# ──────────────────────────────────────────
def build_all_videos(content_list: list[dict]) -> list[Path]:
    from pathlib import Path as P

    print(f"\n=== 영상 생성 시작 ({TOTAL_REELS}개) ===")
    video_paths = []

    for i, content in enumerate(content_list, start=1):
        print(f"\n[{i:02d}/{TOTAL_REELS}] {content['theme']}")
        try:
            vp = build_video(content["overlay_text"], i)
            video_paths.append(vp)
        except Exception as e:
            print(f"  !! 영상 생성 실패: {e}")
            video_paths.append(None)

    success = sum(1 for v in video_paths if v is not None)
    print(f"\n영상 생성 완료: {success}/{TOTAL_REELS}개 성공")
    return video_paths


# ──────────────────────────────────────────
# STEP 3: Buffer 예약 발행
# ──────────────────────────────────────────
def schedule_all(content_list: list[dict], video_paths: list[Path]):
    valid_pairs = [
        (c, v) for c, v in zip(content_list, video_paths) if v is not None
    ]
    if not valid_pairs:
        print("발행할 영상이 없습니다.")
        return

    contents, videos = zip(*valid_pairs)
    publish_all(list(contents), list(videos))


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

    if mode in ("1", "3"):
        video_paths = build_all_videos(content_list)
    else:
        # 기존 output/*.mp4 파일 목록 로드
        from pathlib import Path as P
        video_paths = [P(f"output/output_{i}.mp4") for i in range(1, TOTAL_REELS + 1)]
        video_paths = [v if v.exists() else None for v in video_paths]

    if mode in ("1", "4"):
        schedule_all(content_list, video_paths)

    print("\n모든 작업이 완료되었습니다.")


if __name__ == "__main__":
    main()
