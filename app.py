# -*- coding: utf-8 -*-
"""
app.py — 릴스 자동화 관리자 대시보드 (Flask)
"""
import io
import json
import os
import threading
import zipfile
from datetime import datetime
from pathlib import Path

from dotenv import load_dotenv
from flask import Flask, jsonify, render_template, request, send_file, send_from_directory
from openai import OpenAI

load_dotenv()

app = Flask(__name__)

BASE_DIR     = Path(__file__).parent
OUTPUT_DIR   = BASE_DIR / "output"
IMG_DIR      = OUTPUT_DIR / "images"
VIDEO_DIR    = OUTPUT_DIR / "videos"
CAPTION_DIR  = OUTPUT_DIR / "captions"
ASSETS_DIR   = BASE_DIR / "assets"
PLAN_CACHE    = OUTPUT_DIR / "content_plan.json"
HISTORY_FILE  = OUTPUT_DIR / "history.json"
CHANNELS_FILE = BASE_DIR / "channels.json"

OUTPUT_DIR.mkdir(exist_ok=True)
IMG_DIR.mkdir(exist_ok=True)
VIDEO_DIR.mkdir(exist_ok=True)
CAPTION_DIR.mkdir(exist_ok=True)

CATEGORIES = [
    "시니어 라이프",
    "건강/웰니스",
    "재테크/경제상식",
    "치매·뇌건강",
    "가족/인간관계",
    "행복·공감",
    "운동/다이어트",
    "요리/생활꿀팁",
]

progress_store: dict = {}


# ── 유틸 ──────────────────────────────────
def load_history() -> list:
    if HISTORY_FILE.exists():
        with open(HISTORY_FILE, encoding="utf-8") as f:
            return json.load(f)
    return []


def save_history(record: dict):
    h = load_history()
    h.insert(0, record)
    with open(HISTORY_FILE, "w", encoding="utf-8") as f:
        json.dump(h[:100], f, ensure_ascii=False, indent=2)


def load_plan() -> list:
    if PLAN_CACHE.exists():
        with open(PLAN_CACHE, encoding="utf-8") as f:
            return json.load(f)
    return []


def _caption_path(index: int) -> Path:
    return CAPTION_DIR / f"post_{index}.txt"


def _save_captions(plan: list):
    """기획안의 instagram_caption을 captions/post_N.txt로 저장"""
    for i, item in enumerate(plan, start=1):
        caption = item.get("instagram_caption", "")
        if caption:
            _caption_path(i).write_text(caption, encoding="utf-8")


def _load_caption(index: int) -> str:
    p = _caption_path(index)
    return p.read_text(encoding="utf-8") if p.exists() else ""


def load_channels() -> dict:
    if CHANNELS_FILE.exists():
        with open(CHANNELS_FILE, encoding="utf-8") as f:
            return json.load(f)
    return {"channels": [], "schedule": {"mode": "preset", "preset_times_kst": ["09:00", "14:00", "19:00"]}}


def save_channels(data: dict):
    with open(CHANNELS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


# ── 라우트 ────────────────────────────────
@app.route("/")
def index():
    plan    = load_plan()
    history = load_history()
    for i, item in enumerate(plan, start=1):
        item["_has_image"]   = (IMG_DIR   / f"card_{i}.jpg").exists()
        item["_has_video"]   = (VIDEO_DIR / f"output_{i}.mp4").exists()
        item["_has_caption"] = _caption_path(i).exists()
    channels_data = load_channels()
    import time
    return render_template("index.html",
                           categories=CATEGORIES,
                           plan=plan,
                           history=history,
                           channels=channels_data.get("channels", []),
                           schedule_cfg=channels_data.get("schedule", {}),
                           now=int(time.time()))


@app.route("/output/images/<path:filename>")
def serve_image(filename):
    return send_from_directory(IMG_DIR, filename)


@app.route("/assets/<path:filename>")
def serve_assets(filename):
    return send_from_directory(ASSETS_DIR, filename)


@app.route("/output/videos/<path:filename>")
def serve_video(filename):
    return send_from_directory(VIDEO_DIR, filename)


@app.route("/output/<path:filename>")
def serve_output(filename):
    return send_from_directory(OUTPUT_DIR, filename)


@app.route("/download/video/<int:index>")
def download_video(index: int):
    filename = f"output_{index}.mp4"
    return send_from_directory(VIDEO_DIR, filename, as_attachment=True,
                               download_name=filename)


# ── API: ZIP 다운로드 ─────────────────────
@app.route("/api/download/zip", methods=["POST"])
def api_download_zip():
    body    = request.get_json() or {}
    mode    = body.get("type", "all")
    indices = body.get("indices", [])

    plan = load_plan()
    if not plan:
        return jsonify({"error": "기획안이 없습니다."}), 400

    if mode == "all":
        indices = list(range(1, len(plan) + 1))

    buf   = io.BytesIO()
    added = 0
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for i in indices:
            img = IMG_DIR   / f"card_{i}.jpg"
            vid = VIDEO_DIR / f"output_{i}.mp4"
            if img.exists():
                zf.write(img, f"images/card_{i}.jpg")
                added += 1
            if vid.exists():
                zf.write(vid, f"videos/output_{i}.mp4")
                added += 1

    if added == 0:
        return jsonify({"error": "다운로드할 파일이 없습니다."}), 404

    buf.seek(0)
    date = datetime.now().strftime("%Y%m%d")
    return send_file(buf, mimetype="application/zip", as_attachment=True,
                     download_name=f"silver_contents_{date}.zip")


# ── API: 저장 현황 ────────────────────────
@app.route("/api/storage-status")
def api_storage_status():
    plan  = load_plan()
    total = len(plan)
    imgs  = sum(1 for i in range(1, total + 1) if (IMG_DIR    / f"card_{i}.jpg").exists())
    vids  = sum(1 for i in range(1, total + 1) if (VIDEO_DIR  / f"output_{i}.mp4").exists())
    caps  = sum(1 for i in range(1, total + 1) if _caption_path(i).exists())
    return jsonify({"total": total, "images": imgs, "videos": vids, "captions": caps})


# ── API: 캡션 조회 ────────────────────────
@app.route("/api/caption/<int:index>")
def api_get_caption(index: int):
    return jsonify({"index": index, "caption": _load_caption(index)})


# ── API: 캡션 수정 ────────────────────────
@app.route("/api/caption/<int:index>", methods=["POST"])
def api_save_caption(index: int):
    body    = request.get_json() or {}
    caption = body.get("caption", "")
    _caption_path(index).write_text(caption, encoding="utf-8")
    return jsonify({"success": True})


# ════════════════════════════════════════
# DALL-E / gpt-image-1 배경 생성
# ════════════════════════════════════════
_SCENE_MAP = [
    (["수면", "잠", "불면", "숙면"],
     "Korean senior couple (65-70) in a cozy bright bedroom, soft morning sunlight, "
     "serene and well-rested expressions, warm white bedding"),
    (["물", "수분", "마시"],
     "Korean senior couple (65-70) enjoying herbal tea at a sunlit wooden table, "
     "surrounded by fresh green plants, refreshing healthy atmosphere"),
    (["햇볕", "비타민D", "산책", "걷"],
     "Active Korean senior couple (65-70) walking in a beautiful park, "
     "golden sunlight filtering through trees, vibrant and energetic"),
    (["식사", "영양", "식단", "음식", "채소"],
     "Korean senior couple enjoying a colorful healthy Korean meal, "
     "bright dining table, warm home atmosphere, fresh vegetables"),
    (["운동", "체조", "스트레칭", "근력"],
     "Korean senior couple doing gentle morning stretching in a beautiful garden, "
     "warm golden morning light, energetic and healthy"),
    (["혈압", "혈당", "당뇨", "심장"],
     "Korean senior couple at a bright home wellness setting, calm and confident, "
     "soft warm lighting, trustworthy healthy lifestyle"),
    (["뇌", "기억", "치매", "인지"],
     "Korean senior couple doing a joyful puzzle activity at a bright living room, "
     "smiling, mentally engaged and vibrant"),
    (["관절", "무릎", "허리", "척추"],
     "Korean senior couple practicing gentle yoga in a peaceful bright studio, "
     "flexible and healthy, warm natural lighting"),
    (["치아", "구강"],
     "Korean senior couple smiling confidently, bright home setting, "
     "warm cheerful morning atmosphere, healthy and radiant"),
    (["피부", "노화"],
     "Elegant Korean senior couple with radiant skin, warm golden light, "
     "luxury wellness lifestyle, beautiful and dignified"),
    (["명상", "힐링", "마음", "스트레스"],
     "Korean senior couple sitting peacefully in a beautiful garden, "
     "meditating, soft morning light, tranquil and joyful"),
    (["연금", "노후", "재정", "돈", "보험"],
     "Korean senior couple looking happy and confident at home, "
     "warm comfortable living room, secure and prosperous lifestyle"),
    (["가족", "손자", "자녀"],
     "Korean senior couple with warm family atmosphere, bright home setting, "
     "joyful and loving, golden hour natural light"),
]

_FALLBACK_SCENE = (
    "Happy and healthy Korean senior couple (65-70) in a warm bright lifestyle setting, "
    "park or sunlit home, smiling confidently, vibrant and dignified"
)

_DALLE_MASTER = """Create a premium Korean senior health infographic background image.

Luxury healthcare TV program style.

SUBJECT: A smiling Korean senior couple in their 60s. Natural Korean appearance. Warm smile. Trustworthy and friendly atmosphere. {scene}

COMPOSITION (STRICTLY CRITICAL — must follow exactly):
- Instagram Reels format, 9:16 tall vertical image
- Imagine the canvas is divided into a 2×3 grid (left/right columns, top/middle/bottom rows)
- The senior couple occupies ONLY the TOP-RIGHT cell (right half, top 35%)
  → Faces and upper bodies visible, leaning slightly right, cropped at waist or chest
- The TOP-LEFT cell must be completely EMPTY dark navy — large Korean headline text will be placed there
- The MIDDLE 60% of the image (both left and right columns) must be completely EMPTY
  → No people, no arms, no objects crossing into this zone
- The BOTTOM area must also be completely empty — clean dark background
- Think of it as a strict 3-zone layout:
    [TOP-LEFT: empty dark navy] [TOP-RIGHT: couple portrait]
    [MIDDLE: completely empty canvas]
    [BOTTOM: completely empty canvas]
- The left 50% of the top zone must stay clean and dark — reserved for text overlay
- The couple should face slightly toward the left (toward the text area)

BACKGROUND:
- Dark navy blue (#0B1F5B) fills ALL empty zones (left column top, full middle, full bottom)
- The right side of the top zone transitions naturally from the portrait into dark background
- Subtle gold accent lines or bokeh acceptable in empty zones only
- The transition from portrait to background must be smooth and natural (soft edge, vignette)

STYLE:
- Luxury healthcare campaign quality
- Korean broadcast health program thumbnail level
- Magazine quality, premium editorial design
- Professional commercial photography
- Soft natural lighting, beautiful depth of field
- Ultra realistic, ultra detailed

COLOR:
- Dark navy blue (#0B1F5B) dominant background
- Gold accent elements
- Warm natural skin tones
- Premium Korean branding style aesthetic

STRICTLY NO:
- No text of any kind
- No logo
- No watermark
- No infographic boxes
- No typography
- No numbers
- No captions
- NO person or body part in the middle or bottom 65% of the image"""


def _dalle_generate(client, prompt: str) -> bytes:
    """gpt-image-1 → dall-e-3 → dall-e-2 순 폴백. bytes 반환."""
    import base64

    try:
        resp = client.images.generate(
            model="gpt-image-1",
            prompt=prompt,
            size="1024x1536",
            n=1,
        )
        b64 = resp.data[0].b64_json
        if b64:
            return base64.b64decode(b64)
    except Exception:
        pass

    try:
        import urllib.request
        resp = client.images.generate(
            model="dall-e-3",
            prompt=prompt,
            size="1024x1792",
            quality="hd",
            n=1,
        )
        url = resp.data[0].url
        with urllib.request.urlopen(url) as r:
            return r.read()
    except Exception:
        pass

    import urllib.request
    resp = client.images.generate(
        model="dall-e-2",
        prompt=prompt[:900],
        size="1024x1024",
        n=1,
    )
    url = resp.data[0].url
    with urllib.request.urlopen(url) as r:
        return r.read()


def _build_dalle_prompt(data: dict) -> str:
    text_pool = " ".join([
        data.get("theme", ""),
        data.get("hero_big_text", "").replace("\n", " "),
        data.get("tip1_title", ""),
        data.get("tip2_title", ""),
        data.get("tip3_title", ""),
    ])
    scene = _FALLBACK_SCENE
    for keywords, scene_desc in _SCENE_MAP:
        if any(kw in text_pool for kw in keywords):
            scene = scene_desc
            break
    return _DALLE_MASTER.format(scene=scene)


# ── API: 콘텐츠 기획 ──────────────────────
@app.route("/api/generate-plan", methods=["POST"])
def api_generate_plan():
    data     = request.get_json()
    category = data.get("category", "시니어 라이프")
    count    = int(data.get("count", 20))

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY가 설정되지 않았습니다."}), 400

    client = OpenAI(api_key=api_key)

    try:
        system_prompt = (
            "당신은 대한민국 최고 수준의 실버 콘텐츠 아트디렉터입니다. "
            "50~70대 시니어를 위한 인스타그램 릴스 카드뉴스를 기획합니다. "
            "단순 정보 전달이 아닌 건강방송 썸네일 + 프리미엄 인포그래픽 수준의 "
            "후킹력 강한 콘텐츠를 만듭니다."
        )

        user_prompt = f"""
당신은 50~70대 시니어를 위한 인스타그램 릴스 "실버 채널" 카드뉴스 전문 기획자입니다.
"{category}" 카테고리로 {count}개의 카드뉴스 콘텐츠를 기획해 주세요.

[콘텐츠 비중 — 반드시 준수]
- 건강 예방: 40%
- 돈·노후: 25%
- 치매·뇌건강: 15%
- 가족·인간관계: 10%
- 행복·공감: 10%

[제목 규칙 — 반드시 후킹형으로]
금지: "오늘의 정보", "행복한 하루", "좋은 습관", "건강한 시작" 같은 일반적 제목
필수: 아래처럼 구체적이고 후킹력 강한 제목 사용
예시: "60대 이후 꼭 알아야 할 상식", "의사들이 추천하는 건강 습관",
      "치매 예방을 위한 하루 3분", "노후를 바꾸는 생활 습관",
      "연금 받을 때 꼭 확인하세요", "지금 확인해야 할 건강 신호"

[카드뉴스 레이아웃 — 1080×1920 세로형]
▸ 상단 40%: 딥네이비 배경 + 시니어 사진(우측) / 채널 레이블 / 초대형 노란 제목 / 흰 pill 서브타이틀
▸ 중단 45%: 번호 1·2·3 흰 카드 — 컬러 타이틀 + 설명(2줄) + 오른쪽 이모지
▸ 하단 15%: 네이비 pill CTA — 결론 문구 (핵심 단어 노란색 강조)

[필드 규칙 — 반드시 준수]
- hero_small_text: 채널 레이블, 최대 10자 (예: "실버를 위한", "의사들이 추천하는", "60대 이후")
- hero_big_text: 핵심 키워드 2줄, 각 줄 3~5글자, \\n으로 구분 (예: "오늘의\\n상식!", "치매\\n예방!")
- hero_sub_text: 흰 pill 서브타이틀, 최대 18자 (예: "알아두면 삶이 더 편해집니다", "지금 확인해야 합니다")
- tip1_title / tip2_title / tip3_title: 카드 제목, 최대 13글자, 끝에 ! 권장
- tip1_desc / tip2_desc / tip3_desc: 설명 최대 2줄 각 16글자, \\n으로 줄바꿈
- tip1_icon / tip2_icon / tip3_icon: 영어 소문자 아이콘명 (아래 목록에서만)
  → water, sun, smile, heart, walk, exercise, sleep, food, medicine, brain,
     bone, muscle, eye, dental, tea, stretch, yoga, nature, book, star,
     check, music, shower, blood, pressure, fish, vegetable, fruit, milk, egg
- bottom_cta: 한 줄 결론 문구, 최대 18글자 (반드시 한 줄로 들어올 길이)
- highlight_word: bottom_cta 중 노란색 강조할 핵심 단어 2~5글자
- instagram_caption: 아래 형식 엄수
  ① 후킹 첫 문장 (이모지 포함, 한 줄)
  ② 빈 줄
  ③ 본문 2~3줄 (각 줄 이모지 포함, \\n으로 줄바꿈)
  ④ 빈 줄
  ⑤ CTA 한 줄
  ⑥ 빈 줄
  ⑦ 해시태그 정확히 5개 (# 붙여서 한 줄에 나열)
  전체 150~250자. 해시태그는 반드시 5개 고정.

반드시 아래 JSON 형식으로만 출력하세요 (코드블록 없이 순수 JSON).
[중요] items 배열에 반드시 {count}개를 모두 채워서 출력하세요. 절대 중간에 끊지 마세요.

{{"items": [
  {{
    "theme": "콘텐츠 주제명",
    "hero_small_text": "실버를 위한",
    "hero_big_text": "오늘의\\n상식!",
    "hero_sub_text": "알아두면 삶이 더 편해집니다",
    "tip1_title": "물은 조금씩 자주 마시기!",
    "tip1_desc": "갈증 전에 마시면 좋아요\\n혈액순환에 도움됩니다.",
    "tip1_icon": "water",
    "tip2_title": "하루 30분 햇볕 쬐기!",
    "tip2_desc": "비타민D 생성에 도움\\n뼈 건강과 면역력 향상!",
    "tip2_icon": "sun",
    "tip3_title": "웃으면 건강해집니다!",
    "tip3_desc": "웃음은 스트레스를 줄이고\\n면역력을 높여줍니다.",
    "tip3_icon": "smile",
    "bottom_cta": "작은 습관이 건강한 내일을 만듭니다!",
    "highlight_word": "건강한 내일",
    "instagram_caption": "아래 형식을 정확히 지킬 것:\n\n후킹 첫 문장 (이모지 포함, 한 줄)\n\n본문 내용 (2~3줄, 줄바꿈 포함, 이모지 각 줄에 포함)\n\n핵심 CTA 한 줄\n\n#해시태그1 #해시태그2 #해시태그3 #해시태그4 #해시태그5\n\n규칙: 해시태그는 정확히 5개. 본문은 읽기 쉽게 줄바꿈. 이모지 자연스럽게 삽입."
  }}
]}}
"""
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user",   "content": user_prompt},
            ],
            temperature=0.85,
            max_tokens=16000,
            response_format={"type": "json_object"},
        )

        raw    = response.choices[0].message.content.strip()
        parsed = json.loads(raw)
        plan   = parsed.get("items", [])[:count]

        OUTPUT_DIR.mkdir(exist_ok=True)
        with open(PLAN_CACHE, "w", encoding="utf-8") as f:
            json.dump(plan, f, ensure_ascii=False, indent=2)

        # 캡션 파일 저장
        _save_captions(plan)

        for old in IMG_DIR.glob("card_*.jpg"):
            old.unlink(missing_ok=True)

        save_history({
            "type": "기획 생성", "category": category,
            "count": len(plan), "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })
        return jsonify({"success": True, "plan": plan, "count": len(plan)})

    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: DALL-E 배경 단일 생성 ────────────
@app.route("/api/generate-bg/<int:index>", methods=["POST"])
def api_generate_bg(index: int):
    plan = load_plan()
    if not plan or index > len(plan):
        return jsonify({"error": "기획안 없음"}), 400

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY 미설정"}), 400

    job_id = f"bg_{index}"
    progress_store[job_id] = {"status": "running", "message": "배경 생성 중…"}

    def run():
        try:
            client    = OpenAI(api_key=api_key)
            prompt    = _build_dalle_prompt(plan[index - 1])
            img_bytes = _dalle_generate(client, prompt)
            out       = ASSETS_DIR / f"bg_card_{index}.jpg"
            out.write_bytes(img_bytes)
            progress_store[job_id] = {"status": "done", "message": f"저장 완료 → {out.name}"}
            save_history({
                "type": "DALL-E 배경", "index": index,
                "theme": plan[index - 1].get("theme", ""),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
        except Exception as e:
            progress_store[job_id] = {"status": "error", "message": str(e)}

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id})


# ── API: DALL-E 배경 전체 생성 ────────────
@app.route("/api/generate-all-bgs", methods=["POST"])
def api_generate_all_bgs():
    plan = load_plan()
    if not plan:
        return jsonify({"error": "기획안 없음"}), 400

    api_key = os.getenv("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY 미설정"}), 400

    job_id = "bg_all"
    progress_store[job_id] = {"status": "running", "done": 0, "total": len(plan), "message": "준비 중…"}

    def run():
        import time
        client     = OpenAI(api_key=api_key)
        total      = len(plan)
        done_count = 0
        errors     = []
        for i, item in enumerate(plan, start=1):
            progress_store[job_id]["message"] = f"{i}/{total} 생성 중… ({item.get('theme','')})"
            try:
                prompt    = _build_dalle_prompt(item)
                img_bytes = _dalle_generate(client, prompt)
                out       = ASSETS_DIR / f"bg_card_{i}.jpg"
                out.write_bytes(img_bytes)
                done_count += 1
                progress_store[job_id].update({
                    "done": done_count,
                    "last_success": i,
                    "message": f"{done_count}/{total} 완료 ({item.get('theme','')})",
                })
            except Exception as e:
                err_msg = str(e)
                errors.append(f"[{i}] {err_msg}")
                progress_store[job_id]["message"] = f"[{i}] 오류: {err_msg[:120]}"
            time.sleep(1.5)

        if errors and done_count == 0:
            progress_store[job_id].update({"status": "error", "message": errors[0]})
        else:
            progress_store[job_id].update({
                "status": "done", "done": done_count, "errors": errors,
                "message": f"{done_count}/{total} 완료" + (f" ({len(errors)}개 실패)" if errors else ""),
            })
        save_history({
            "type": "DALL-E 전체 배경", "count": total,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id, "total": len(plan)})


# ── API: 단일 이미지 생성 ─────────────────
@app.route("/api/create-image/<int:index>", methods=["POST"])
def api_create_image(index: int):
    plan = load_plan()
    if not plan or index > len(plan):
        return jsonify({"error": "기획안이 없거나 인덱스 범위 초과"}), 400

    job_id = f"img_{index}"
    progress_store[job_id] = {"status": "running", "message": "이미지 합성 중..."}

    def run():
        try:
            import sys; sys.path.insert(0, str(BASE_DIR))
            from modules.video_editor import compose_image
            compose_image(plan[index - 1], index)
            progress_store[job_id] = {"status": "done", "message": "완료"}
        except Exception as e:
            progress_store[job_id] = {"status": "error", "message": str(e)}

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id})


def _backup_outputs():
    """기존 이미지·영상을 output/archive/YYYY-MM-DD_HH-MM/ 으로 백업."""
    import shutil
    has_img = any(IMG_DIR.glob("card_*.jpg"))
    has_vid = any(VIDEO_DIR.glob("output_*.mp4"))
    if not has_img and not has_vid:
        return None

    stamp    = datetime.now().strftime("%Y-%m-%d_%H-%M")
    arch_dir = OUTPUT_DIR / "archive" / stamp
    arch_dir.mkdir(parents=True, exist_ok=True)

    if has_img:
        img_arch = arch_dir / "images"
        img_arch.mkdir(exist_ok=True)
        for f in IMG_DIR.glob("card_*.jpg"):
            import shutil as sh
            sh.copy2(f, img_arch / f.name)

    if has_vid:
        vid_arch = arch_dir / "videos"
        vid_arch.mkdir(exist_ok=True)
        for f in VIDEO_DIR.glob("output_*.mp4"):
            import shutil as sh
            sh.copy2(f, vid_arch / f.name)

    return stamp


# ── API: 전체 이미지 생성 ─────────────────
@app.route("/api/create-all-images", methods=["POST"])
def api_create_all_images():
    plan = load_plan()
    if not plan:
        return jsonify({"error": "기획안을 먼저 생성해 주세요."}), 400

    backed_up = _backup_outputs()

    job_id = "img_all"
    progress_store[job_id] = {"status": "running", "done": 0, "total": len(plan), "message": "준비 중..."}

    def run():
        import sys, time
        sys.path.insert(0, str(BASE_DIR))
        from modules.video_editor import compose_image
        total = len(plan)
        for i, item in enumerate(plan, start=1):
            try:
                compose_image(item, i)
                progress_store[job_id].update({"done": i, "message": f"{i} / {total} 이미지 생성 완료"})
            except Exception as e:
                progress_store[job_id]["message"] = f"[{i}] 오류: {e}"
            time.sleep(0.3)
        progress_store[job_id]["status"] = "done"
        save_history({
            "type": "이미지 생성", "count": total,
            "backed_up": backed_up,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id, "total": len(plan)})


# ── API: 단일 영상 생성 ───────────────────
@app.route("/api/create-video", methods=["POST"])
def api_create_video():
    data  = request.get_json()
    index = int(data.get("index", 1))
    plan  = load_plan()
    if not plan or index > len(plan):
        return jsonify({"error": "기획안 없음"}), 400

    job_id = f"video_{index}"
    progress_store[job_id] = {"status": "running", "message": "영상 생성 중..."}

    def run():
        try:
            import sys; sys.path.insert(0, str(BASE_DIR))
            from modules.video_editor import build_video
            build_video(plan[index - 1], index)
            progress_store[job_id] = {"status": "done", "message": "완료"}
            save_history({
                "type": "영상 생성", "theme": plan[index-1].get("theme",""),
                "index": index, "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
        except Exception as e:
            progress_store[job_id] = {"status": "error", "message": str(e)}

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id})


# ── API: 전체 영상 생성 ───────────────────
@app.route("/api/create-all-videos", methods=["POST"])
def api_create_all_videos():
    plan = load_plan()
    if not plan:
        return jsonify({"error": "기획안 없음"}), 400

    job_id = "video_all"
    progress_store[job_id] = {"status": "running", "done": 0, "total": len(plan), "message": "준비 중..."}

    def run():
        import sys, time
        sys.path.insert(0, str(BASE_DIR))
        from modules.video_editor import build_video
        total = len(plan)
        for i, item in enumerate(plan, start=1):
            try:
                build_video(item, i)
                progress_store[job_id].update({
                    "done": i,
                    "message": f"{i} / {total} 영상 완료",
                })
            except Exception as e:
                progress_store[job_id]["message"] = f"[{i}] 오류: {e}"
            time.sleep(0.5)
        progress_store[job_id]["status"] = "done"
        save_history({
            "type": "전체 영상 생성", "count": total,
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
        })

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id, "total": len(plan)})


# ── API: 채널 설정 조회/저장 ──────────────
@app.route("/api/channels")
def api_get_channels():
    return jsonify(load_channels())


@app.route("/api/channels", methods=["POST"])
def api_save_channels():
    data = request.get_json() or {}
    save_channels(data)
    return jsonify({"success": True})


# ── API: Buffer 단일 포스트 즉시 예약 ──────
@app.route("/api/schedule-buffer/<int:index>", methods=["POST"])
def api_schedule_buffer_single(index: int):
    plan = load_plan()
    if not plan or index < 1 or index > len(plan):
        return jsonify({"error": "유효하지 않은 인덱스"}), 400

    body       = request.get_json() or {}
    platforms  = body.get("platforms", ["instagram"])
    channel_id = body.get("channel_id", "")
    times_kst  = body.get("times_kst", ["09:00", "14:00", "19:00"])

    channels_data = load_channels()
    channel = next(
        (c for c in channels_data.get("channels", []) if c["id"] == channel_id),
        channels_data.get("channels", [{}])[0] if channels_data.get("channels") else {}
    )

    item       = plan[index - 1]
    video_path = VIDEO_DIR / f"output_{index}.mp4"
    if not video_path.exists():
        return jsonify({"error": f"영상 파일 없음: output_{index}.mp4"}), 400

    import sys
    sys.path.insert(0, str(BASE_DIR))
    from modules.buffer_publisher import publish_all

    try:
        results = publish_all(
            content_list=[item],
            video_paths=[video_path],
            caption_dir=CAPTION_DIR,
            channel=channel,
            platforms=platforms,
            times_kst=times_kst,
        )
        return jsonify({"success": True, "result": results[0]})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ── API: Buffer 멀티플랫폼 예약 ───────────
@app.route("/api/schedule-buffer", methods=["POST"])
def api_schedule_buffer():
    plan = load_plan()
    if not plan:
        return jsonify({"error": "기획안 없음"}), 400

    body         = request.get_json() or {}
    platforms    = body.get("platforms", ["instagram", "tiktok", "youtube"])
    channel_id   = body.get("channel_id", "")
    times_kst    = body.get("times_kst", ["09:00", "14:00", "19:00"])

    # 채널 찾기
    channels_data = load_channels()
    channel = next(
        (c for c in channels_data.get("channels", []) if c["id"] == channel_id),
        channels_data.get("channels", [{}])[0] if channels_data.get("channels") else {}
    )

    total  = len(plan)
    job_id = "buffer_all"
    progress_store[job_id] = {
        "status":    "running",
        "done":      0,
        "total":     total,
        "message":   "준비 중…",
        "platforms": {p: {"done": 0, "error": 0} for p in platforms},
    }

    def run():
        import sys, time
        sys.path.insert(0, str(BASE_DIR))
        from modules.buffer_publisher import publish_all

        video_paths = [VIDEO_DIR / f"output_{i}.mp4" for i in range(1, total + 1)]

        def on_progress(record):
            i    = record["index"]
            pmap = record.get("platforms", {})
            for p, r in pmap.items():
                if r["status"] == "success":
                    progress_store[job_id]["platforms"][p]["done"] += 1
                elif r["status"] == "error":
                    progress_store[job_id]["platforms"][p]["error"] += 1
            progress_store[job_id].update({
                "done":    i,
                "message": f"{i}/{total} 예약 처리 완료 — {record.get('theme','')}",
            })

        try:
            results = publish_all(
                content_list=plan,
                video_paths=video_paths,
                caption_dir=CAPTION_DIR,
                channel=channel,
                platforms=platforms,
                times_kst=times_kst,
                on_progress=on_progress,
            )
            progress_store[job_id]["status"] = "done"
            progress_store[job_id]["message"] = f"전체 {total}개 예약 완료"
            save_history({
                "type":      "Buffer 멀티플랫폼 예약",
                "count":     total,
                "platforms": platforms,
                "channel":   channel.get("name", ""),
                "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M"),
            })
        except Exception as e:
            progress_store[job_id].update({"status": "error", "message": str(e)})

    threading.Thread(target=run, daemon=True).start()
    return jsonify({"success": True, "job_id": job_id, "total": total})


# ── API: 진행 상태 ────────────────────────
@app.route("/api/progress/<job_id>")
def api_progress(job_id):
    return jsonify(progress_store.get(job_id, {"status": "unknown"}))


@app.route("/api/plan")
def api_plan():
    return jsonify(load_plan())


@app.route("/api/history")
def api_history():
    return jsonify(load_history())


if __name__ == "__main__":
    print("=" * 45)
    print("  실버 자동화 시스템 시작")
    print("  http://localhost:5000")
    print("=" * 45)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
