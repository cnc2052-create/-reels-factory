# -*- coding: utf-8 -*-
"""
폼폼 콘텐츠 파이프라인
- Claude AI 스크립트 생성
- 10가지 훅 구조 적용
- Higgsfield(힉스필드) AI 영상 생성
- Remotion 자막 오버레이 렌더링
- Notion 자동 저장
"""
import os, json, subprocess, tempfile
from pathlib import Path
from anthropic import Anthropic
from .hook_benchmarker import select_hook, fill_hook_text

client = Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY", ""))

NICHE_MAP = {
    "pompom_beauty": "beauty",
    "pompom_health": "health_fitness",
    "pompom_home": "home_living",
    "pompom_fashion": "fashion",
    "pompom_food": "food",
}

OUTPUT_DIR = Path(__file__).parent.parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


# ───────────────────────────────────────────────────────────
# 1. 스크립트 + 캡션 생성
# ───────────────────────────────────────────────────────────
def generate_script(persona: dict, product: dict, hook: dict) -> dict:
    hook_text = fill_hook_text(hook, product)
    niche = NICHE_MAP.get(persona["account_id"], "beauty")

    system = f"""당신은 {persona['name']} 인스타그램 계정 운영자입니다.
페르소나: {persona['personality']}
스타일: {persona['style']}
릴스 길이: 15~30초 / 9:16"""

    prompt = f"""제품: {product['name']} / {product['price']:,}원
바이럴 각도: {product.get('viral_angle', '')}
훅({hook['id']}번 {hook['name']}): {hook_text}

위 훅으로 시작하는 15~20초 릴스 스크립트. JSON만 응답:
{{
  "hook_text": "첫 3초 자막",
  "narration": ["나레이션1", "나레이션2", "나레이션3"],
  "scenes": [
    {{"sec": "0-3", "action": "장면설명", "caption": "자막"}},
    {{"sec": "3-8", "action": "장면설명", "caption": "자막"}},
    {{"sec": "8-15", "action": "장면설명", "caption": "자막"}},
    {{"sec": "15-20", "action": "장면설명", "caption": "자막"}}
  ],
  "caption": "인스타캡션+해시태그15개",
  "remotion_captions": ["자막1", "자막2", "자막3", "자막4"]
}}"""

    r = client.messages.create(
        model="claude-haiku-5-5", max_tokens=2000,
        system=system + "\n반드시 순수 JSON만 응답. 설명 금지.",
        messages=[{"role": "user", "content": prompt}]
    )
    # ThinkingBlock 건너뛰고 텍스트 블록만 추출
    txt = next((b.text for b in r.content if hasattr(b, "text")), "{}").strip()
    if txt.startswith("```"):
        txt = txt.split("```")[1]
        if txt.startswith("json"):
            txt = txt[4:]
    # 가장 바깥 JSON 객체만 추출
    depth, start, end = 0, 0, 0
    for i, ch in enumerate(txt):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                break
    data = json.loads(txt[start:end])
    data["hook_id"] = hook["id"]
    data["hook_name"] = hook["name"]
    data["product"] = product
    data["persona"] = persona["name"]
    return data


# ───────────────────────────────────────────────────────────
# 2. Pexels 무료 영상 소스 다운로드 (크레딧 불필요)
# API 키: https://www.pexels.com/api/ — 무료 발급
# ───────────────────────────────────────────────────────────
import requests as _req

PEXELS_API_KEY = os.getenv("PEXELS_API_KEY", "")

# 카테고리→검색 키워드 매핑
NICHE_VIDEO_KEYWORDS: dict[str, list[str]] = {
    "beauty": ["skincare routine", "beauty product", "korean skincare", "toner serum"],
    "health_fitness": ["vitamins supplements", "healthy lifestyle", "fitness nutrition"],
    "home_living": ["kitchen cooking", "home organization", "cooking meal prep"],
    "fashion": ["fashion outfit", "clothing style", "street fashion"],
    "food": ["korean food", "cooking asian food", "meal preparation"],
}


def fetch_free_video(niche: str, product_name: str) -> str:
    """Pexels API로 무료 영상 URL 가져오기"""
    if not PEXELS_API_KEY:
        print("[Pexels] API 키 없음 — .env에 PEXELS_API_KEY 추가 필요")
        return ""

    keywords = NICHE_VIDEO_KEYWORDS.get(niche, ["product review lifestyle"])
    import random as _rand
    query = _rand.choice(keywords)

    try:
        r = _req.get(
            "https://api.pexels.com/videos/search",
            headers={"Authorization": PEXELS_API_KEY, "Accept-Charset": "utf-8"},
            params={"query": query, "orientation": "portrait", "size": "medium", "per_page": 10},
            timeout=10,
        )
        videos = r.json().get("videos", [])
        if not videos:
            return ""
        video = _rand.choice(videos[:5])
        # HD 파일 우선 선택
        files = sorted(video.get("video_files", []), key=lambda f: f.get("width", 0), reverse=True)
        for f in files:
            if f.get("width", 0) <= 1080:
                url = f["link"]
                print(f"[Pexels] 영상 선택: {url[:60]}...")
                return url
        return files[0]["link"] if files else ""
    except Exception as e:
        print(f"[Pexels] 오류: {e}")
        return ""


def download_video(url: str, dest_path: str) -> bool:
    """영상 URL 다운로드"""
    if not url:
        return False
    try:
        r = _req.get(url, stream=True, timeout=60)
        with open(dest_path, "wb") as f:
            for chunk in r.iter_content(chunk_size=1024 * 64):
                f.write(chunk)
        print(f"[다운로드] {dest_path}")
        return True
    except Exception as e:
        print(f"[다운로드] 실패: {e}")
        return False


# ───────────────────────────────────────────────────────────
# 3. Remotion 자막 오버레이 렌더링
# ───────────────────────────────────────────────────────────
def render_with_remotion(video_path: str, script_data: dict, output_path: str) -> bool:
    """Remotion CLI로 자막 합성 — remotion/pompom-captions 컴포지션 사용"""
    remotion_dir = Path(__file__).parent.parent.parent / "remotion-pompom"
    if not remotion_dir.exists():
        print(f"[Remotion] 프로젝트 없음: {remotion_dir} — 자막 없이 원본 사용")
        return False

    captions = script_data.get("remotion_captions", [])
    product_name = script_data["product"]["name"]
    affiliate_url = script_data["product"].get("affiliate_url", "")

    props = json.dumps({
        "videoSrc": video_path,
        "captions": captions,
        "productName": product_name,
        "affiliateUrl": affiliate_url,
        "hookText": script_data.get("hook_text", ""),
        "persona": script_data.get("persona", ""),
    }, ensure_ascii=False)

    cmd = [
        "npx", "remotion", "render",
        "pompom-captions",       # 컴포지션 ID
        output_path,
        "--props", props,
        "--overwrite",
    ]

    try:
        result = subprocess.run(cmd, cwd=str(remotion_dir), capture_output=True, text=True, timeout=300)
        if result.returncode == 0:
            print(f"[Remotion] 렌더 완료: {output_path}")
            return True
        else:
            print(f"[Remotion] 오류: {result.stderr[:200]}")
            return False
    except Exception as e:
        print(f"[Remotion] 실행 실패: {e}")
        return False


# ───────────────────────────────────────────────────────────
# 4. 전체 파이프라인
# ───────────────────────────────────────────────────────────
def run_pipeline(persona: dict, product: dict, recent_hooks: list[int] | None = None) -> dict:
    niche = NICHE_MAP.get(persona["account_id"], "beauty")

    hook = select_hook(niche, product, recent_hooks)
    script_data = generate_script(persona, product, hook)

    # 출력 파일 경로
    safe_name = product["name"][:20].replace(" ", "_")
    json_path = OUTPUT_DIR / f"{persona['account_id']}_{safe_name}.json"

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(script_data, f, ensure_ascii=False, indent=2)

    # 무료 영상 소스 가져오기
    niche = NICHE_MAP.get(persona["account_id"], "beauty")
    video_url = fetch_free_video(niche, product["name"])
    video_path = ""
    if video_url:
        video_path = str(OUTPUT_DIR / f"{persona['account_id']}_{safe_name}_raw.mp4")
        download_video(video_url, video_path)

    script_data["json_path"] = str(json_path)
    script_data["raw_video_path"] = video_path
    script_data["video_source"] = "pexels_free"

    # Remotion으로 자막 합성
    if video_path:
        final_path = str(OUTPUT_DIR / f"{persona['account_id']}_{safe_name}_final.mp4")
        ok = render_with_remotion(video_path, script_data, final_path)
        script_data["final_video_path"] = final_path if ok else video_path

    return script_data
