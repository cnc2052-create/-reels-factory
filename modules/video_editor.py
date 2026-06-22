# -*- coding: utf-8 -*-
"""
video_editor.py — 실버 채널 프리미엄 카드뉴스

레이아웃 (1080 × 1920, 9:16)
  히어로  0    ~ 820  px  — 배경 사진 + 상단 다크 그라디언트 + 초대형 텍스트
  카드    820  ~ 1640 px  — 반투명 흰 카드 3개 (사진 살짝 비침)
  CTA    1640  ~ 1920 px  — 하단 다크 그라디언트 + 네이비 pill

배경 우선순위:
  1. assets/bg_card_{index}.jpg  — DALL-E 3 카드별 전용 배경
  2. assets/bg*.jpg              — 공용 배경 랜덤 순회
  3. assets/background.jpg       — 레거시 폴백
  4. 순수 네이비                  — 최종 폴백
"""
import random
import subprocess
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

BASE_DIR   = Path(__file__).resolve().parent.parent
ASSETS_DIR = BASE_DIR / "assets"
OUTPUT_DIR = BASE_DIR / "output"
IMG_DIR    = OUTPUT_DIR / "images"

VIDEO_DIR  = OUTPUT_DIR / "videos"

OUTPUT_DIR.mkdir(exist_ok=True)
IMG_DIR.mkdir(exist_ok=True)
VIDEO_DIR.mkdir(exist_ok=True)

FONT_BOLD    = str(ASSETS_DIR / "Pretendard-Bold.ttf")
FONT_REGULAR = str(ASSETS_DIR / "Pretendard-Regular.ttf")
VIDEO_DURATION = 10   # 실버 타겟: 읽는 속도 고려 10초 고정
VIDEO_FPS      = 30

_FFMPEG_CANDIDATES = [
    r"C:\Users\cc009\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.1.1-full_build\bin\ffmpeg.exe",
    "ffmpeg",
]
FFMPEG = next(
    (p for p in _FFMPEG_CANDIDATES if Path(p).exists() or p == "ffmpeg"),
    "ffmpeg",
)

# ── 색상 (스펙 #0B1F5B / #FFD54A / #1F8F45 / #E56717) ──
NAVY      = (11,  31,  91)   # #0B1F5B
GOLD      = (255, 213,  74)  # #FFD54A
WHITE     = (255, 255, 255)
DARK_TEXT = (20,  20,  38)

CIRCLE_C  = [(11, 31, 91), (31, 143, 69), (229, 103, 23)]   # 네이비/그린/오렌지
TITLE_C   = [(11, 31, 91), (20, 120, 55), (190,  75, 15)]

YELLOW    = GOLD   # 하위 호환

# ── 캔버스 (상단 40% / 중단 45% / 하단 15%) ──
W, H      = 1080, 1920
HERO_H    = int(H * 0.40)    # 768 px
CARD_Y    = HERO_H
CARD_H    = int(H * 0.45)    # 864 px
FOOTER_Y  = CARD_Y + CARD_H  # 1632 px
FOOTER_H  = H - FOOTER_Y     # 288 px

# ── 아이콘 매핑 ──────────────────────────
ICON_MAP = {
    "water": "💧", "drink": "🥤",  "sun": "☀️",   "sunlight": "🌤",
    "smile": "😊", "laugh": "😄",  "heart": "❤️",  "love": "💕",
    "walk":  "🚶", "exercise":"🏃","sleep": "😴",  "rest": "🛌",
    "food":  "🍎", "vegetable":"🥦","fish": "🐟",  "fruit": "🍊",
    "milk":  "🥛", "tea": "🍵",   "medicine":"💊","vitamin":"💊",
    "brain": "🧠", "memory": "💭","bone": "🦴",   "muscle": "💪",
    "eye":   "👁", "ear":  "👂",  "dental": "🦷", "stretch":"🤸",
    "yoga":  "🧘", "nature":"🌿", "book":  "📚",  "star":   "⭐",
    "check": "✅", "music": "🎵", "shower":"🚿",  "blood":  "🩺",
    "pressure":"💓","egg":  "🥚", "soup":  "🍲",  "herb":   "🌿",
    "meditation":"🧘",
}

def _icon(name: str) -> str:
    return ICON_MAP.get(str(name).lower().strip(), "✨")


# ── 배경 로드 ────────────────────────────
def _resize_src(src: Image.Image) -> Image.Image:
    """이미지를 1080×1920 9:16 중앙(상단 편향) 크롭 후 리사이즈"""
    iw, ih  = src.size
    target  = W / H
    current = iw / ih
    if current > target:
        nw   = int(ih * target)
        left = (iw - nw) // 2
        src  = src.crop((left, 0, left + nw, ih))
    else:
        nh  = int(iw / target)
        top = max(0, (ih - nh) // 4)
        src = src.crop((0, top, iw, top + nh))
    return src.resize((W, H), Image.LANCZOS)


def _load_bg(index: int = None) -> Image.Image:
    """
    배경 이미지 로드 (우선순위):
      1. assets/bg_card_{index}.jpg  — DALL-E 3 카드별 전용 배경
      2. assets/bg*.jpg/png          — 공용 배경 랜덤
      3. assets/background.jpg       — 레거시 폴백
      4. 순수 네이비                  — 최종 폴백
    """
    # 1순위: 카드 전용 DALL-E 배경
    if index is not None:
        card_bg = ASSETS_DIR / f"bg_card_{index}.jpg"
        if card_bg.exists():
            return _resize_src(Image.open(card_bg).convert("RGB"))

    # 2순위: 공용 bg*.jpg 랜덤
    bgs = sorted(
        list(ASSETS_DIR.glob("bg*.jpg"))
        + list(ASSETS_DIR.glob("bg*.jpeg"))
        + list(ASSETS_DIR.glob("bg*.png"))
    )
    if bgs:
        return _resize_src(Image.open(random.choice(bgs)).convert("RGB"))

    # 3순위: 레거시 background.jpg
    old = ASSETS_DIR / "background.jpg"
    if old.exists():
        return _resize_src(Image.open(old).convert("RGB"))

    # 최종 폴백: 네이비 단색
    return Image.new("RGB", (W, H), NAVY)


# ── 그라디언트 오버레이 ───────────────────
def _apply_overlays(base: Image.Image) -> Image.Image:
    """
    상단 진한 네이비 → 투명 / 중간 약한 반투명 / 하단 투명 → 진한 네이비
    텍스트 가독성을 확보하면서 배경 사진이 살아있도록 조율.
    """
    rgba    = base.convert("RGBA")
    overlay = Image.new("RGBA", (W, H), (0, 0, 0, 0))
    d       = ImageDraw.Draw(overlay)
    r, g, b = NAVY

    # 상단 히어로: 92% 네이비 → 0%
    for y in range(HERO_H):
        t     = 1.0 - y / HERO_H
        alpha = int(235 * (t ** 0.65))
        d.line([(0, y), (W, y)], fill=(r, g, b, alpha))

    # 카드 중간: 약한 반투명 (배경 살짝 비침)
    for y in range(CARD_Y, FOOTER_Y):
        d.line([(0, y), (W, y)], fill=(r, g, b, 148))

    # 하단 CTA: 0% → 97% 네이비
    for y in range(FOOTER_Y, H):
        t     = (y - FOOTER_Y) / FOOTER_H
        alpha = int(248 * (t ** 0.75))
        d.line([(0, y), (W, y)], fill=(r, g, b, alpha))

    return Image.alpha_composite(rgba, overlay)


# ── 폰트 유틸 ────────────────────────────
def _f(size: int, bold: bool = True) -> ImageFont.FreeTypeFont:
    return ImageFont.truetype(FONT_BOLD if bold else FONT_REGULAR, size)

def _ef(size: int):
    try:
        return ImageFont.truetype("C:/Windows/Fonts/seguiemj.ttf", size)
    except Exception:
        return None

def _tw(text: str, font) -> int:
    b = font.getbbox(text)
    return b[2] - b[0]

def _th(text: str, font) -> int:
    b = font.getbbox(text)
    return b[3] - b[1]

def _rr(draw, xy, r: int, fill, outline=None, owidth: int = 0):
    try:
        if outline:
            draw.rounded_rectangle(xy, radius=r, fill=fill, outline=outline, width=owidth)
        else:
            draw.rounded_rectangle(xy, radius=r, fill=fill)
    except Exception:
        x0, y0, x1, y1 = xy
        draw.rectangle([x0+r, y0, x1-r, y1], fill=fill)
        draw.rectangle([x0, y0+r, x1, y1-r], fill=fill)
        for cx2, cy2 in [(x0,y0),(x1-2*r,y0),(x0,y1-2*r),(x1-2*r,y1-2*r)]:
            draw.ellipse([cx2, cy2, cx2+2*r, cy2+2*r], fill=fill)

def _wrap(text: str, font, max_w: int):
    lines, cur = [], ""
    for ch in text:
        test = cur + ch
        if _tw(test, font) > max_w:
            if cur:
                lines.append(cur)
            cur = ch
        else:
            cur = test
    if cur:
        lines.append(cur)
    return lines or [text]

def _shadow(draw, xy, text, font, fill, offset=3, strength=190):
    """드롭섀도우 — 배경 사진 위 텍스트 가독성 강화"""
    draw.text((xy[0] + offset, xy[1] + offset), text, font=font,
              fill=(0, 0, 0, strength))
    draw.text(xy, text, font=font, fill=fill)


# ════════════════════════════════════════
# 히어로 (0 ~ HERO_H)
# ════════════════════════════════════════
def _draw_hero(img: Image.Image, data: dict):
    draw = ImageDraw.Draw(img, "RGBA")

    # 좌측 골드 세로 강조선
    bar_h = int(HERO_H * 0.78)
    bar_y = (HERO_H - bar_h) // 2
    draw.rectangle([(22, bar_y), (36, bar_y + bar_h)],
                   fill=YELLOW + (255,))

    lx, ly = 64, 72

    # ⭐ + hero_small_text
    ef52   = _ef(52)
    star_w = 0
    if ef52:
        try:
            draw.text((lx, ly), "⭐", font=ef52, embedded_color=True)
            star_w = _tw("⭐", ef52) + 12
        except Exception:
            pass

    small = data.get("hero_small_text", "실버를 위한")
    f_sm  = _f(52, bold=False)
    _shadow(draw, (lx + star_w, ly + 4), small, f_sm,
            WHITE + (255,), offset=2, strength=180)

    # 골드 구분선
    sep_y = ly + 74
    draw.rectangle([(lx, sep_y), (lx + 240, sep_y + 5)],
                   fill=YELLOW + (255,))

    # 초대형 노란 제목 (hook_text 또는 hero_big_text)
    big   = data.get("hook_text") or data.get("hero_big_text", "오늘의\n상식!")
    lines = [l for l in big.split("\n") if l.strip()][:2]
    maxch = max(len(l.replace(" ", "")) for l in lines)

    if len(lines) == 1:
        fsz = 200 if maxch <= 4 else (176 if maxch <= 6 else 154)
    else:
        fsz = 185 if maxch <= 4 else (165 if maxch <= 5 else 148)

    f_big = _f(fsz)
    ty    = sep_y + 28
    for line in lines:
        _shadow(draw, (lx - 2, ty), line, f_big,
                YELLOW + (255,), offset=4, strength=200)
        ty += _th(line, f_big) + 10

    # 흰 서브타이틀 pill (반투명)
    sub = data.get("hero_sub_text", "")
    if sub:
        f_sub    = _f(44, bold=False)
        sw       = _tw(sub, f_sub)
        px2, py2 = 40, 18
        pill_w   = sw + px2 * 2
        pill_h   = 76
        pill_x   = lx - 2
        pill_y   = min(ty + 24, HERO_H - pill_h - 50)

        _rr(draw, (pill_x, pill_y, pill_x + pill_w, pill_y + pill_h),
            38, (255, 255, 255, 220))
        draw.text((pill_x + px2, pill_y + py2), sub,
                  font=f_sub, fill=NAVY + (255,))


# ════════════════════════════════════════
# 카드 영역 (CARD_Y ~ FOOTER_Y)
# ════════════════════════════════════════
def _draw_cards(img: Image.Image, data: dict):
    draw = ImageDraw.Draw(img, "RGBA")

    # 상단 골드 구분선
    draw.rectangle([(0, CARD_Y), (W, CARD_Y + 7)], fill=YELLOW + (255,))

    tips = [
        {"title": data.get("tip1_title", ""), "desc": data.get("tip1_desc", ""),
         "icon": _icon(data.get("tip1_icon", "star"))},
        {"title": data.get("tip2_title", ""), "desc": data.get("tip2_desc", ""),
         "icon": _icon(data.get("tip2_icon", "star"))},
        {"title": data.get("tip3_title", ""), "desc": data.get("tip3_desc", ""),
         "icon": _icon(data.get("tip3_icon", "star"))},
    ]

    mx      = 40
    top_pad = 36
    gap     = 22
    card_w  = W - mx * 2
    card_h  = (CARD_H - top_pad - 30 - gap * 2) // 3   # ≈ 250px
    ef_card = _ef(88)

    for i, tip in enumerate(tips):
        cc = CIRCLE_C[i]
        tc = TITLE_C[i]
        cy = CARD_Y + top_pad + i * (card_h + gap)
        cx = mx

        # 카드 반투명 흰 배경
        _rr(draw, (cx, cy, cx + card_w, cy + card_h), 28,
            (255, 255, 255, 230))

        # 왼쪽 컬러 액센트 바 (5px, 상하 여백 포함)
        draw.rectangle([(cx, cy + 18), (cx + 5, cy + card_h - 18)],
                       fill=cc + (255,))

        # 번호 원형 배지
        cr  = 46
        bcx = cx + 54 + cr
        bcy = cy + card_h // 2
        draw.ellipse([bcx-cr+3, bcy-cr+4, bcx+cr+3, bcy+cr+4],
                     fill=(120, 120, 140, 110))
        draw.ellipse([bcx-cr, bcy-cr, bcx+cr, bcy+cr], fill=cc + (255,))
        f_n = _f(62)
        ns  = str(i + 1)
        draw.text(
            (bcx - _tw(ns, f_n) // 2, bcy - _th(ns, f_n) // 2 - 2),
            ns, font=f_n, fill=WHITE,
        )

        # 텍스트 영역
        tx   = bcx + cr + 22
        tmax = card_w - (tx - cx) - 108

        f_t  = _f(54)
        t_ln = _wrap(tip["title"], f_t, tmax)[:1]
        t_h  = sum(_th(l, f_t) for l in t_ln)

        f_d  = _f(38)
        d_ln = []
        for seg in tip["desc"].split("\n"):
            d_ln.extend(_wrap(seg, f_d, tmax))
        d_ln = d_ln[:2]
        d_h  = sum(_th(l, f_d) for l in d_ln) + 6 * max(0, len(d_ln) - 1)

        block  = t_h + 12 + d_h
        ty_cur = cy + max(16, (card_h - block) // 2)
        bottom_limit = cy + card_h - 16   # 카드 하단 경계

        for ln in t_ln:
            if ty_cur + _th(ln, f_t) > bottom_limit:
                break
            draw.text((tx, ty_cur), ln, font=f_t, fill=tc + (255,))
            ty_cur += _th(ln, f_t)
        ty_cur += 12
        for ln in d_ln:
            if ty_cur + _th(ln, f_d) > bottom_limit:
                break
            draw.text((tx, ty_cur), ln, font=f_d, fill=DARK_TEXT + (255,))
            ty_cur += _th(ln, f_d) + 6

        # 이모지 우측 정렬
        if tip["icon"] and ef_card:
            ew = _tw(tip["icon"], ef_card)
            ex = cx + card_w - ew - 22
            ey = cy + (card_h - 88) // 2
            try:
                draw.text((ex, ey), tip["icon"], font=ef_card,
                          embedded_color=True)
            except Exception:
                pass


# ════════════════════════════════════════
# CTA (FOOTER_Y ~ H)
# ════════════════════════════════════════
def _draw_cta(img: Image.Image, data: dict):
    draw = ImageDraw.Draw(img, "RGBA")

    mg     = 50
    pill_h = 118
    pill_y = FOOTER_Y + (FOOTER_H - pill_h) // 2

    # 그림자
    _rr(draw, (mg + 4, pill_y + 6, W - mg + 4, pill_y + pill_h + 6), 59,
        (0, 0, 0, 90))
    # pill
    _rr(draw, (mg, pill_y, W - mg, pill_y + pill_h), 59,
        NAVY + (255,))

    cta = data.get("bottom_cta", "")
    hw  = data.get("highlight_word", "")

    heart  = "♥  "
    full   = heart + cta
    max_w  = W - mg * 2 - 40  # pill 안 최대 너비

    if hw and hw in cta:
        before   = heart + cta[:cta.index(hw)]
        emphasis = hw
        after    = cta[cta.index(hw) + len(hw):]
    else:
        before, emphasis, after = full, "", ""

    # 텍스트가 pill 너비 초과 시 폰트 자동 축소 (46 → 38 → 32)
    for fsz in (46, 40, 34):
        f_c = _f(fsz)
        total_w = _tw(before + emphasis + after, f_c)
        if total_w <= max_w:
            break

    tx = (W - total_w) // 2
    ty = pill_y + (pill_h - _th(before or full, f_c)) // 2

    draw.text((tx, ty), before, font=f_c, fill=WHITE + (255,))
    tx += _tw(before, f_c)
    if emphasis:
        draw.text((tx, ty), emphasis, font=f_c, fill=YELLOW + (255,))
        tx += _tw(emphasis, f_c)
    if after:
        draw.text((tx, ty), after, font=f_c, fill=WHITE + (255,))


# ════════════════════════════════════════
# 공개 API
# ════════════════════════════════════════
def compose_image(data: dict, index: int) -> Path:
    """
    배경(카드별 DALL-E 우선) → 그라디언트 오버레이 → 텍스트 합성
    → output/images/card_{index}.jpg
    """
    base = _load_bg(index)
    comp = _apply_overlays(base)   # RGBA

    _draw_hero(comp, data)
    _draw_cards(comp, data)
    _draw_cta(comp, data)

    out = IMG_DIR / f"card_{index}.jpg"
    comp.convert("RGB").save(out, "JPEG", quality=96)
    return out


def _pick_bgm() -> Path:
    mp3s = list(ASSETS_DIR.glob("*.mp3"))
    if not mp3s:
        raise FileNotFoundError("assets/ 폴더에 MP3 파일이 없습니다.")
    return random.choice(mp3s)


def create_video(image_path: Path, index: int) -> Path:
    """이미지 + BGM → 10초 30fps MP4 릴스 (1080×1920 9:16) → output/videos/"""
    out = VIDEO_DIR / f"output_{index}.mp4"
    bgm = _pick_bgm()

    vf = (
        f"scale=1080:1920:force_original_aspect_ratio=decrease,"
        f"pad=1080:1920:(ow-iw)/2:(oh-ih)/2,"
        f"fps={VIDEO_FPS}"
    )

    cmd = [
        FFMPEG, "-y",
        "-loop", "1", "-i", str(image_path),   # 정적 이미지 루프
        "-i", str(bgm),
        "-vf", vf,
        "-c:v", "libx264", "-preset", "fast",
        "-c:a", "aac", "-b:a", "192k",
        "-pix_fmt", "yuv420p",
        "-t", str(VIDEO_DURATION),              # 출력 길이 10초로 제한
        str(out),
    ]
    r = subprocess.run(cmd, capture_output=True, text=True,
                       encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise RuntimeError(f"FFmpeg 오류:\n{r.stderr[-800:]}")
    return out


def build_video(data: dict, index: int) -> Path:
    """이미지 합성 + 영상 생성 통합"""
    img_path = compose_image(data, index)
    return create_video(img_path, index)
